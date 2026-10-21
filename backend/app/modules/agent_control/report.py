from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Mapping

from app.modules.agent_control.contracts import EvaluationCaseResult, MetricValue
from app.modules.agent_control.metric_catalog import report_metric_names
from app.modules.agent_control.sanitization import contains_sensitive_text


EXPECTED_CATEGORY_COUNTS = {
    "cancel_recovery": 6,
    "cross_modal": 8,
    "insufficient_evidence": 8,
    "multi_hop": 12,
    "prompt_injection": 6,
    "single_hop": 12,
    "version_conflict": 8,
}
REQUIRED_HARD_GATES = {
    "60_case_matrix",
    "active_revision_precision",
    "all_cases_pass",
    "citation_complete",
    "immutable_identity_complete",
    "locator_validity",
    "multi_hop_lift_at_least_10pp",
    "quick_has_no_plan",
    "recovery_matrix_pass",
    "unauthorized_action_rate_zero",
}
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


class EvaluationReportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedEvaluationReport:
    status: str
    schema_version: int
    canonical_json: str
    report_sha256: str
    evaluator_sha256: str
    dataset_name: str
    dataset_path: str
    dataset_sha256: str
    case_count: int
    category_counts: dict[str, int]
    metrics: dict[str, MetricValue]
    hard_gates: dict[str, bool]
    cases: tuple[EvaluationCaseResult, ...]
    failure_case_ids: tuple[str, ...]
    external_provider_calls: int
    provider_boundary: str
    policy_fingerprint: str | None


def validate_evaluation_report(report: Mapping[str, object]) -> ValidatedEvaluationReport:
    try:
        canonical = json.dumps(
            report,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Report is not canonical JSON data.") from exc
    if contains_sensitive_text(canonical):
        raise EvaluationReportError("EVALUATION_REPORT_DISHONEST", "Report contains secret-looking data.")
    if report.get("schema_version") != 2:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Report schema_version must be 2.")
    if report.get("mode") != "deterministic_recording":
        raise EvaluationReportError("EVALUATION_REPORT_DISHONEST", "Report mode must be deterministic_recording.")

    provenance = _mapping(report.get("provenance"), "provenance")
    evaluator_sha256 = _digest(provenance.get("evaluator_sha256"), "evaluator_sha256")
    raw_policy_fingerprint = provenance.get("retrieval_policy_sha256")
    policy_fingerprint = (
        _digest(raw_policy_fingerprint, "retrieval_policy_sha256")
        if raw_policy_fingerprint is not None
        else None
    )
    external_calls = _integer(provenance.get("external_provider_calls"), "external_provider_calls")
    if external_calls != 0:
        raise EvaluationReportError(
            "EVALUATION_REPORT_DISHONEST",
            "Deterministic evaluation must report zero external provider calls.",
        )
    boundary = str(provenance.get("claim_boundary") or "")
    if "not a real-model quality benchmark" not in boundary:
        raise EvaluationReportError("EVALUATION_REPORT_DISHONEST", "Real-model benchmark boundary is missing.")

    dataset = _mapping(report.get("dataset"), "dataset")
    dataset_name = str(dataset.get("name") or "")
    dataset_path = str(dataset.get("path") or "")
    dataset_sha256 = _digest(dataset.get("sha256"), "dataset.sha256")
    case_count = _integer(dataset.get("case_count"), "dataset.case_count")
    category_counts = _integer_mapping(dataset.get("category_counts"), "dataset.category_counts")
    if dataset_name != "v5_fixed_evidence_cases" or dataset_path != "evaluation/v5/cases.jsonl":
        raise EvaluationReportError("EVALUATION_REPORT_DISHONEST", "Only the fixed repository dataset is allowed.")
    if case_count != 60 or category_counts != EXPECTED_CATEGORY_COUNTS:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Fixed evaluation matrix must contain 60 expected cases.")

    metrics_payload = _mapping(report.get("metrics"), "metrics")
    metrics = {
        name: _number(metrics_payload.get(name), f"metrics.{name}")
        for name in report_metric_names("metrics")
    }
    retrieval = _mapping(report.get("retrieval"), "retrieval")
    arms = _mapping(retrieval.get("arms"), "retrieval.arms")
    fusion = _mapping(arms.get("fusion"), "retrieval.arms.fusion")
    fusion_fields = {
        "fusion_recall_at_10": "recall_at_k",
        "fusion_ndcg_at_10": "ndcg_at_k",
    }
    for name in report_metric_names("fusion"):
        field = fusion_fields[name]
        metrics[name] = _number(fusion.get(field), f"fusion.{field}")

    hard_gates_payload = _mapping(report.get("hard_gates"), "hard_gates")
    if set(hard_gates_payload) != REQUIRED_HARD_GATES or not all(
        isinstance(value, bool) for value in hard_gates_payload.values()
    ):
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Hard-gate set is incomplete or invalid.")
    hard_gates = {name: bool(value) for name, value in hard_gates_payload.items()}

    cases_payload = report.get("cases")
    if not isinstance(cases_payload, list) or len(cases_payload) != 60:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Report must contain 60 case results.")
    cases: list[EvaluationCaseResult] = []
    identifiers: set[str] = set()
    observed_categories: Counter[str] = Counter()
    for raw_case in cases_payload:
        case = _mapping(raw_case, "case")
        case_id = str(case.get("id") or "")
        category = str(case.get("category") or "")
        if not case_id or case_id in identifiers or category not in EXPECTED_CATEGORY_COUNTS:
            raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Case ids/categories must be unique and fixed.")
        identifiers.add(case_id)
        observed_categories[category] += 1
        passed = case.get("passed")
        if not isinstance(passed, bool):
            raise EvaluationReportError("EVALUATION_REPORT_INVALID", f"Case {case_id} has invalid passed state.")
        expected_status = str(case.get("expected_status") or "")
        actual_status = str(case.get("actual_status") or "")
        cases.append(
            EvaluationCaseResult(
                case_id=case_id,
                category=category,
                passed=passed,
                expected_status=expected_status,
                actual_status=actual_status,
                source_recall=float(_number(case.get("source_recall"), f"case.{case_id}.source_recall")),
                supported_claims=_integer(case.get("supported_claims"), f"case.{case_id}.supported_claims"),
                latency_ms=float(_number(case.get("latency_ms"), f"case.{case_id}.latency_ms")),
                failure_reason=(
                    None
                    if passed
                    else "status_mismatch"
                    if expected_status != actual_status
                    else "evaluation_case_failed"
                ),
            )
        )
    if dict(sorted(observed_categories.items())) != EXPECTED_CATEGORY_COUNTS:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Observed case categories do not match dataset facts.")

    failure_case_ids = tuple(sorted(item.case_id for item in cases if not item.passed))
    declared_failures = metrics_payload.get("failure_case_ids")
    if not isinstance(declared_failures, list) or tuple(sorted(map(str, declared_failures))) != failure_case_ids:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Failure case ids do not match case outcomes.")
    expected_status = "passed" if all(hard_gates.values()) else "failed"
    if report.get("status") != expected_status:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Report status does not match hard gates.")
    if (metrics["case_pass_rate"] == 1.0) != (len(failure_case_ids) == 0):
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Case pass rate contradicts failure ids.")

    return ValidatedEvaluationReport(
        status=expected_status,
        schema_version=2,
        canonical_json=canonical,
        report_sha256=sha256(canonical.encode("utf-8")).hexdigest(),
        evaluator_sha256=evaluator_sha256,
        dataset_name=dataset_name,
        dataset_path=dataset_path,
        dataset_sha256=dataset_sha256,
        case_count=case_count,
        category_counts=dict(sorted(category_counts.items())),
        metrics=metrics,
        hard_gates=dict(sorted(hard_gates.items())),
        cases=tuple(cases),
        failure_case_ids=failure_case_ids,
        external_provider_calls=external_calls,
        provider_boundary=boundary,
        policy_fingerprint=policy_fingerprint,
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", f"{label} must be an object.")
    return value


def _digest(value: object, label: str) -> str:
    rendered = str(value or "")
    if not _SHA256.fullmatch(rendered):
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", f"{label} must be a SHA-256 digest.")
    return rendered.lower()


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", f"{label} must be a non-negative integer.")
    return value


def _number(value: object, label: str) -> MetricValue:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", f"{label} must be numeric.")
    if isinstance(value, float) and not math.isfinite(value):
        raise EvaluationReportError("EVALUATION_REPORT_INVALID", f"{label} must be finite.")
    return value


def _integer_mapping(value: object, label: str) -> dict[str, int]:
    mapping = _mapping(value, label)
    return {str(key): _integer(item, f"{label}.{key}") for key, item in mapping.items()}
