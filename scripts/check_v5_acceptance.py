from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "docs" / "v5_agentic_rag" / "evaluation_report.json"
DEFAULT_DATASET = ROOT / "evaluation" / "v5" / "cases.jsonl"
EVALUATOR_RELATIVE_PATH = Path("scripts/evaluate_agentic_rag.py")
EXPECTED_CATEGORIES = {
    "cancel_recovery": 6,
    "cross_modal": 8,
    "insufficient_evidence": 8,
    "multi_hop": 12,
    "prompt_injection": 6,
    "single_hop": 12,
    "version_conflict": 8,
}
REQUIRED_ARMS = {"dense", "sparse", "fusion", "rerank"}
REQUIRED_EXPERIMENTS = {
    "v4_9_single_shot_proxy",
    "retrieval_only",
    "evidence_agent",
}
EXPECTED_AGENT_PIPELINE = (
    "EvidenceIndex.stage/upsert/activate -> HybridAgentSearch -> "
    "EvidenceAgent.submit -> AgentRunner.advance_one + Hybrid evaluation arms"
)
REQUIRED_IMPLEMENTATION_FILES = (
    "backend/alembic/versions/0007_v5_evidence_index.py",
    "backend/alembic/versions/0008_v5_agent_runtime.py",
    "backend/app/api/routes_agent_runs.py",
    "backend/app/api/routes_evidence.py",
    "backend/app/modules/evidence_agent/controller.py",
    "backend/app/modules/evidence_agent/service.py",
    "backend/app/modules/evidence_index/sql.py",
    "backend/app/modules/evidence_index/reconciler.py",
    "backend/app/services/agent_model.py",
    "backend/app/services/outbox_dispatcher.py",
    "backend/app/tasks/agent_tasks.py",
    "backend/app/tasks/evidence_index_tasks.py",
    "frontend/app/workbench/page.tsx",
    "frontend/app/runs/[runId]/page.tsx",
    "frontend/app/artifacts/[artifactId]/page.tsx",
    "frontend/app/library/page.tsx",
    "frontend/modules/evidence-agent/evidence-agent.ts",
    "frontend/modules/evidence-agent/http-sse-adapter.ts",
    "frontend/modules/evidence-agent/run-controller.ts",
    "frontend/e2e/v5-evidence-agent.spec.ts",
    "evaluation/v5/cases.jsonl",
    "scripts/evaluate_agentic_rag.py",
    "scripts/reconcile_evidence_index.py",
    "docs/v5_agentic_rag/spec.md",
    "docs/v5_agentic_rag/plan.md",
    "docs/v5_agentic_rag/task.md",
    "docs/v5_agentic_rag/checklist.md",
)
RETRIEVAL_METRICS = {
    "recall_at_k",
    "mrr",
    "ndcg_at_k",
    "active_revision_precision",
    "locator_validity",
}


def portable_text_sha256(path: Path) -> str:
    """Hash text content without treating checkout line endings as tampering."""

    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256(normalized).hexdigest()


def _read_dataset(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid dataset JSON at line {line_number}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Dataset line {line_number} is not an object.")
        cases.append(payload)
    return cases


def _portable_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def validate_acceptance(
    report_path: Path,
    *,
    dataset_path: Path = DEFAULT_DATASET,
    root: Path = ROOT,
) -> dict[str, Any]:
    report_path = report_path.resolve()
    dataset_path = dataset_path.resolve()
    root = root.resolve()
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        cases = _read_dataset(dataset_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "schema_version": 1,
            "status": "failed",
            "checked_at": datetime.now(UTC).isoformat(),
            "checks": {"inputs_readable": False},
            "failures": [str(exc)],
        }

    case_ids = [str(item.get("id", "")) for item in cases]
    category_counts = dict(sorted(Counter(str(item.get("category", "")) for item in cases).items()))
    report_case_ids = [str(item.get("id", "")) for item in report.get("cases", [])]
    arms = report.get("retrieval", {}).get("arms", {})
    experiments = report.get("experiments", {})
    metrics = report.get("metrics", {})
    model_usage = metrics.get("model_usage", {})
    hard_gates = report.get("hard_gates", {})
    rerank = arms.get("rerank", {})
    provenance = report.get("provenance", {})
    agent_search = provenance.get("agent_search", "")
    agent_search_calls = provenance.get("agent_search_calls", {})
    evaluator_path = root / EVALUATOR_RELATIVE_PATH
    evaluator_digest = portable_text_sha256(evaluator_path) if evaluator_path.is_file() else None

    checks = {
        "inputs_readable": True,
        "report_schema": report.get("schema_version") == 2,
        "deterministic_mode_labeled": report.get("mode") == "deterministic_recording",
        "external_calls_zero": report.get("provenance", {}).get("external_provider_calls") == 0,
        "benchmark_boundary_declared": "not a real-model quality benchmark"
        in provenance.get("claim_boundary", ""),
        "agent_search_pipeline": report.get("pipeline") == EXPECTED_AGENT_PIPELINE
        and isinstance(agent_search, str)
        and "HybridAgentSearch" in agent_search
        and "pinned-scope RRF" in agent_search,
        "agent_search_executed": isinstance(agent_search_calls, dict)
        and isinstance(agent_search_calls.get("embedding_queries"), int)
        and agent_search_calls.get("embedding_queries", 0) > 0
        and isinstance(agent_search_calls.get("vector_searches"), int)
        and agent_search_calls.get("vector_searches", 0)
        >= agent_search_calls.get("embedding_queries", 0),
        "evaluator_digest_matches": evaluator_digest is not None
        and provenance.get("evaluator_sha256") == evaluator_digest,
        "cost_measurement_honest": model_usage.get("cost_measurement")
        in {"reported", "estimated", "unknown", "partial_unknown"}
        and isinstance(model_usage.get("reported_cost_calls"), int)
        and isinstance(model_usage.get("estimated_cost_calls"), int)
        and isinstance(model_usage.get("unknown_cost_calls"), int)
        and model_usage.get("reported_cost_calls", 0)
        + model_usage.get("estimated_cost_calls", 0)
        + model_usage.get("unknown_cost_calls", 0)
        == model_usage.get("calls"),
        "dataset_has_60_unique_cases": len(cases) == 60 and len(set(case_ids)) == 60,
        "dataset_categories": category_counts == EXPECTED_CATEGORIES,
        "dataset_digest_matches": report.get("dataset", {}).get("sha256")
        == portable_text_sha256(dataset_path),
        "report_case_matrix_matches": report_case_ids == case_ids,
        "all_report_cases_pass": len(report_case_ids) == 60
        and all(bool(item.get("passed")) for item in report.get("cases", [])),
        "retrieval_arms_complete": set(arms) == REQUIRED_ARMS
        and all(RETRIEVAL_METRICS.issubset(arm) for arm in arms.values()),
        "active_revision_precision": bool(arms)
        and all(arm.get("active_revision_precision") == 1.0 for arm in arms.values()),
        "locator_validity": bool(arms)
        and all(arm.get("locator_validity") == 1.0 for arm in arms.values()),
        "rerank_boundary_honest": rerank.get("provider")
        == "deterministic_feature_overlap_recording"
        and rerank.get("production_configured") is False
        and rerank.get("evaluation_adapter") is True,
        "experiments_complete": set(experiments) == REQUIRED_EXPERIMENTS,
        "legacy_proxy_labeled": experiments.get("v4_9_single_shot_proxy", {}).get("label")
        == "proxy_not_historical_runtime",
        "multi_hop_lift_gate": float(metrics.get("multi_hop_agent_lift_pp", -1)) >= 10.0,
        "citation_completeness": metrics.get("citation_completeness") == 1.0,
        "immutable_identity": metrics.get("immutable_evidence_identity_rate") == 1.0,
        "unauthorized_action_rate": metrics.get("unauthorized_action_rate") == 0.0,
        "quick_path_has_no_plan": metrics.get("quick_plan_event_count") == 0,
        "recovery_matrix": metrics.get("recovery_scenario_pass_rate") == 1.0,
        "evaluation_hard_gates": bool(hard_gates) and all(hard_gates.values()),
        "required_implementation_files": all((root / path).is_file() for path in REQUIRED_IMPLEMENTATION_FILES),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema_version": 1,
        "status": "passed" if not failures else "failed",
        "checked_at": datetime.now(UTC).isoformat(),
        "report": _portable_path(report_path, root),
        "dataset": _portable_path(dataset_path, root),
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the V5 fixed evaluation and implementation acceptance evidence."
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    result = validate_acceptance(args.report, dataset_path=args.dataset, root=ROOT)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
