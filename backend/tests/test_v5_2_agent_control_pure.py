from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
import json

import pytest

from app.modules.agent_control.comparison import compare_evaluations
from app.modules.agent_control.contracts import (
    ComparisonVerdict,
    EvaluationDetail,
    EvaluationStatus,
    EvaluationSummary,
    FailureCategory,
)
from app.modules.agent_control.metric_catalog import EVALUATION_METRICS, report_metric_names
from app.modules.agent_control.trace import (
    TraceCheckpointInput,
    TraceEventInput,
    TraceModelCallInput,
    TraceRunInput,
    TraceToolCallInput,
    project_run_trace,
)
from app.modules.agent_control.triage import triage_evaluation_failure, triage_run_failure


NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
PRIVATE_EVENT_SECRET = "sk-" + "private"
TRIAGE_SECRET = "sk-" + "abcdefgh"
BASE_METRICS = {
    "case_pass_rate": 1.0,
    "mean_source_recall": 1.0,
    "citation_completeness": 1.0,
    "immutable_evidence_identity_rate": 1.0,
    "unauthorized_action_rate": 0.0,
    "recovery_scenario_pass_rate": 1.0,
    "multi_hop_agent_lift_pp": 58.33,
    "fusion_recall_at_10": 1.0,
    "fusion_ndcg_at_10": 0.99,
}


def test_metric_catalog_is_the_complete_comparison_and_report_vocabulary() -> None:
    assert set(EVALUATION_METRICS) == set(BASE_METRICS)
    assert set(report_metric_names("metrics")) | set(report_metric_names("fusion")) == set(BASE_METRICS)
    assert EVALUATION_METRICS["unauthorized_action_rate"].direction == "lower"
    assert EVALUATION_METRICS["multi_hop_agent_lift_pp"].report_source == "metrics"


def _summary(
    identifier: str,
    *,
    dataset: str = "a" * 64,
    policy_fingerprint: str = "1" * 64,
) -> EvaluationSummary:
    return EvaluationSummary(
        id=identifier,
        label=identifier,
        status=EvaluationStatus.PASSED,
        mode="deterministic_recording",
        policy_fingerprint=policy_fingerprint,
        dataset_sha256=dataset,
        case_count=60,
        case_pass_rate=1.0,
        external_provider_calls=0,
        failure_case_count=0,
        created_at=NOW,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=5),
    )


def _detail(identifier: str, *, metrics: dict[str, float] | None = None, dataset: str = "a" * 64) -> EvaluationDetail:
    return EvaluationDetail(
        summary=_summary(identifier, dataset=dataset),
        schema_version=2,
        evaluator_sha256="b" * 64,
        dataset_name="fixed",
        category_counts={"single_hop": 12},
        metrics={**BASE_METRICS, **(metrics or {})},
        hard_gates={"all_cases_pass": True},
        cases=(),
        failure_case_ids=(),
        provider_boundary="zero external provider calls",
        triage=triage_evaluation_failure(status="passed"),
    )


def test_trace_projection_redacts_every_private_payload_and_never_exposes_tool_arguments() -> None:
    run = TraceRunInput(
        id="run-1",
        trace_id="trace-1",
        goal="api_key=" + "sk-" + "goal-secret-value",
        requested_mode="force_agent",
        effective_mode="force_agent",
        status="completed",
        phase="persist_artifact",
        provider_mode="demo",
        created_at=NOW,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=3),
        active_elapsed_ms=3_000,
        budget_limits={"max_steps": 8},
        budget_usage={"steps": 5},
    )
    events = (
        TraceEventInput(
            sequence=1,
            run_version=1,
            event_type="run.opened",
            visibility="public",
            payload={
                "goal": "safe goal",
                "api_key": "public-secret",
                "status": "queued",
                "reason": "password=" + "public-reason-secret C:\\Users\\private\\file.txt",
            },
            trace_id="trace-1",
            created_at=NOW,
        ),
        TraceEventInput(
            sequence=2,
            run_version=2,
            event_type="model.started",
            visibility="private",
            payload={
                "prompt": "private prompt",
                "api_key": PRIVATE_EVENT_SECRET,
                "selection": {
                    "policy_id": "api_key=" + PRIVATE_EVENT_SECRET,
                    "policy_version": 99,
                },
            },
            trace_id="trace-1",
            created_at=NOW + timedelta(seconds=1),
        ),
        TraceEventInput(
            sequence=3,
            run_version=3,
            event_type="run.completed",
            visibility="public",
            payload={"status": "completed"},
            trace_id="trace-1",
            created_at=NOW + timedelta(seconds=3),
        ),
    )
    trace = project_run_trace(
        run,
        events=events,
        tool_calls=(
            TraceToolCallInput(
                id="tool-1",
                tool_name="search_evidence",
                tool_version="1",
                effect="read_evidence",
                status="completed",
                arguments_digest="c" * 64,
                error_code=None,
                started_at=NOW,
                finished_at=NOW + timedelta(milliseconds=50),
            ),
        ),
        model_calls=(
            TraceModelCallInput(
                id="model-1",
                operation="route",
                provider="recording",
                model="evaluation-agent-v1",
                status="completed",
                input_tokens=10,
                output_tokens=5,
                cost_micros=0,
                latency_ms=20,
                retries=0,
                usage_estimated=True,
                error_code=None,
            ),
        ),
        checkpoints=(TraceCheckpointInput(checksum="d" * 64, run_version=3),),
    )

    rendered = json.dumps(asdict(trace), ensure_ascii=False, default=str)
    assert "private prompt" not in rendered
    assert PRIVATE_EVENT_SECRET not in rendered
    assert "goal-secret-value" not in rendered
    assert trace.goal == "[redacted]"
    assert "public-secret" not in rendered
    assert "public-reason-secret" not in rendered
    assert "C:\\Users\\private" not in rendered
    assert "reason=[redacted]" in trace.events[0].facts
    assert trace.events[1].redacted is True
    assert trace.events[1].facts == ()
    assert trace.replay.stored_state_matches is True
    assert trace.replay.sequence_contiguous is True
    assert trace.replay.trace_id_consistent is True
    assert trace.tool_calls[0].duration_ms == 50
    assert trace.policies[0].policy_id == "tool:search_evidence"
    assert all(item.source != "model.started" for item in trace.policies)
    assert trace.replay.digest == project_run_trace(run, events=events).replay.digest


def test_trace_projection_fails_integrity_for_gaps_trace_mismatch_and_terminal_mismatch() -> None:
    run = TraceRunInput(
        id="run-2",
        trace_id="trace-2",
        goal="Mismatch",
        requested_mode="auto",
        effective_mode="force_quick",
        status="failed",
        phase="retrieve",
        provider_mode="demo",
        created_at=NOW,
        started_at=NOW,
        finished_at=NOW,
        active_elapsed_ms=0,
        budget_limits={},
        budget_usage={},
    )
    trace = project_run_trace(
        run,
        events=(
            TraceEventInput(
                sequence=2,
                run_version=1,
                event_type="run.completed",
                visibility="public",
                payload={},
                trace_id="wrong-trace",
                created_at=NOW,
            ),
        ),
    )
    assert trace.replay.sequence_contiguous is False
    assert trace.replay.trace_id_consistent is False
    assert trace.replay.stored_state_matches is False
    assert set(trace.warnings) == {
        "event_sequence_not_contiguous",
        "trace_id_mismatch",
        "replayed_terminal_state_mismatch",
    }


@pytest.mark.parametrize(
    ("status", "event_type"),
    [
        ("completed", "run.completed"),
        ("insufficient_evidence", "run.insufficient_evidence"),
        ("cancelled", "run.cancelled"),
        ("failed", "run.failed"),
    ],
)
def test_trace_projection_replays_every_legal_terminal_state(status: str, event_type: str) -> None:
    run = TraceRunInput(
        id=f"run-{status}",
        trace_id=f"trace-{status}",
        goal="Terminal replay",
        requested_mode="auto",
        effective_mode="force_quick",
        status=status,
        phase="persist_artifact",
        provider_mode="demo",
        created_at=NOW,
        started_at=NOW,
        finished_at=NOW,
        active_elapsed_ms=0,
        budget_limits={},
        budget_usage={},
    )
    trace = project_run_trace(
        run,
        events=(
            TraceEventInput(
                sequence=1,
                run_version=1,
                event_type=event_type,
                visibility="public",
                payload={"status": status},
                trace_id=run.trace_id,
                created_at=NOW,
            ),
        ),
    )
    assert trace.replay.replayed_terminal_state == status
    assert trace.replay.stored_state_matches is True


def test_comparison_detects_regression_improvement_and_incompatible_dataset() -> None:
    left = _detail("left", metrics={"case_pass_rate": 1.0, "unauthorized_action_rate": 0.0})
    right = replace(
        _detail("right", metrics={"case_pass_rate": 0.9, "unauthorized_action_rate": 0.1}),
        hard_gates={"all_cases_pass": False},
        failure_case_ids=("case-9",),
    )
    regression = compare_evaluations(left, right)
    assert regression.compatible is True
    assert regression.verdict is ComparisonVerdict.REGRESSED
    assert regression.new_failure_case_ids == ("case-9",)
    deltas = {item.metric: item for item in regression.metric_deltas}
    assert deltas["case_pass_rate"].regressed is True
    assert deltas["unauthorized_action_rate"].regressed is True
    assert deltas["citation_completeness"].regressed is False
    assert regression.gate_changes[0].gate == "all_cases_pass"

    improvement = compare_evaluations(right, left)
    assert improvement.verdict is ComparisonVerdict.IMPROVED
    assert improvement.resolved_failure_case_ids == ("case-9",)

    incompatible = compare_evaluations(left, _detail("other", dataset="e" * 64))
    assert incompatible.compatible is False
    assert incompatible.verdict is ComparisonVerdict.INCOMPARABLE
    assert incompatible.metric_deltas == ()
    assert incompatible.incompatibility_reasons == ("dataset_digest_mismatch",)


def test_comparison_refuses_missing_metrics_or_mismatched_gate_sets() -> None:
    left = _detail("left")
    missing_metric = replace(_detail("missing"), metrics={"case_pass_rate": 1.0})
    result = compare_evaluations(left, missing_metric)
    assert result.verdict is ComparisonVerdict.INCOMPARABLE
    assert any(reason.startswith("missing_metric:") for reason in result.incompatibility_reasons)

    mismatched_gates = replace(_detail("gates"), hard_gates={"different_gate": True})
    result = compare_evaluations(left, mismatched_gates)
    assert result.verdict is ComparisonVerdict.INCOMPARABLE
    assert "hard_gate_set_mismatch" in result.incompatibility_reasons


def test_comparison_discloses_policy_change_without_blocking_a_valid_ab_test() -> None:
    left = _detail("left")
    right = replace(
        _detail("right"),
        summary=_summary("right", policy_fingerprint="f" * 64),
    )
    result = compare_evaluations(left, right)
    assert result.compatible is True
    assert result.policy_changed is True
    assert result.left_policy_fingerprint == "1" * 64
    assert result.right_policy_fingerprint == "f" * 64


def test_triage_supporting_facts_redact_secret_looking_values() -> None:
    result = triage_run_failure(
        status="failed",
        termination_reason="worker_interrupted api_key=" + TRIAGE_SECRET + " C:\\Users\\private\\log.txt",
    )
    rendered = json.dumps(asdict(result), ensure_ascii=False)
    assert TRIAGE_SECRET not in rendered
    assert "C:\\Users\\private" not in rendered
    assert "[redacted]" in rendered


@pytest.mark.parametrize(
    "secret",
    [
        "ghp_" + "abcdefghijklmnopqrstuvwxyz123456",
        "xoxb-" + "123456789012345678901234",
        "AKIA" + "1234567890ABCDEF",
        "AIza" + "abcdefghijklmnopqrstuvwxyz1234567890",
        "-----BEGIN " + "PRIVATE KEY-----",
    ],
)
def test_public_safe_field_values_still_redact_common_secret_shapes(secret: str) -> None:
    run = TraceRunInput(
        id="secret-run",
        trace_id="secret-trace",
        goal="secret fixture",
        requested_mode="auto",
        effective_mode=None,
        status="running",
        phase="route",
        provider_mode="demo",
        created_at=NOW,
        started_at=NOW,
        finished_at=None,
        active_elapsed_ms=0,
        budget_limits={},
        budget_usage={},
    )
    trace = project_run_trace(
        run,
        events=(
            TraceEventInput(
                sequence=1,
                run_version=1,
                event_type="run.status_changed",
                visibility="public",
                payload={"reason": secret},
                trace_id="secret-trace",
                created_at=NOW,
            ),
        ),
    )
    assert trace.events[0].facts == ("reason=[redacted]",)


@pytest.mark.parametrize(
    ("status", "reason", "tool_errors", "dead_letter", "category"),
    [
        ("failed", "agent_dispatch_dead_letter", (), False, FailureCategory.DISPATCH_FAILED),
        ("failed", "worker_interrupted", (), False, FailureCategory.WORKER_INTERRUPTED),
        ("insufficient_evidence", "requirements_uncovered", (), False, FailureCategory.EVIDENCE_INSUFFICIENT),
        ("failed", None, ("TOOL_TIMEOUT",), False, FailureCategory.TOOL_FAILED),
        ("cancelled", None, (), False, FailureCategory.USER_CANCELLED),
        ("failed", None, (), False, FailureCategory.UNKNOWN),
        ("completed", None, (), False, FailureCategory.NONE),
    ],
)
def test_run_failure_triage_is_bounded_and_explicit(
    status: str,
    reason: str | None,
    tool_errors: tuple[str, ...],
    dead_letter: bool,
    category: FailureCategory,
) -> None:
    assert triage_run_failure(
        status=status,
        termination_reason=reason,
        tool_error_codes=tool_errors,
        dispatch_dead_letter=dead_letter,
    ).category is category


@pytest.mark.parametrize(
    ("status", "code", "hard_gate_failed", "category"),
    [
        ("failed", "EVALUATION_DISPATCH_DEAD_LETTER", False, FailureCategory.DISPATCH_FAILED),
        ("failed", "EVALUATION_WORKER_INTERRUPTED", False, FailureCategory.WORKER_INTERRUPTED),
        ("failed", "EVALUATION_TIMEOUT", False, FailureCategory.EXECUTOR_TIMEOUT),
        ("failed", "EVALUATION_REPORT_INVALID", False, FailureCategory.MALFORMED_REPORT),
        ("failed", None, True, FailureCategory.EVALUATION_GATE_FAILED),
        ("passed", None, False, FailureCategory.NONE),
    ],
)
def test_evaluation_failure_triage_is_bounded_and_explicit(
    status: str,
    code: str | None,
    hard_gate_failed: bool,
    category: FailureCategory,
) -> None:
    assert triage_evaluation_failure(
        status=status,
        error_code=code,
        hard_gate_failed=hard_gate_failed,
    ).category is category
