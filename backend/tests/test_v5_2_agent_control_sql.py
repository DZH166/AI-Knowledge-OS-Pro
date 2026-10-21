from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from threading import Event, Lock
import time

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_event import AgentCheckpoint, AgentEvent
from app.models.agent_run import AgentModelCall, AgentRun, AgentToolCall
from app.models.knowledge_space import KnowledgeSpace
from app.models.outbox import OutboxMessage
from app.modules.agent_control.contracts import (
    CompareEvaluations,
    ComparisonVerdict,
    EvaluationStatus,
    ExecuteEvaluation,
    GetEvaluation,
    GetRunTrace,
    ListEvaluations,
    RecoverEvaluations,
    StartEvaluation,
)
from app.modules.agent_control.executor import EvaluationExecutionError
from app.modules.agent_control.report import EXPECTED_CATEGORY_COUNTS, EvaluationReportError, validate_evaluation_report
from app.modules.agent_control.service import SqlAgentControl


NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)
HARD_GATES = {
    "60_case_matrix": True,
    "active_revision_precision": True,
    "all_cases_pass": True,
    "citation_complete": True,
    "immutable_identity_complete": True,
    "locator_validity": True,
    "multi_hop_lift_at_least_10pp": True,
    "quick_has_no_plan": True,
    "recovery_matrix_pass": True,
    "unauthorized_action_rate_zero": True,
}


@pytest.fixture()
def control_factory(tmp_path: Path):
    database_path = tmp_path / "agent-control.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


class RecordingExecutor:
    def __init__(self, report=None, error: Exception | None = None) -> None:
        self.report = report if report is not None else evaluation_report()
        self.error = error
        self.calls: list[str] = []

    def run(self, evaluation_id: str):
        self.calls.append(evaluation_id)
        if self.error is not None:
            raise self.error
        return self.report


class SlowRecordingExecutor(RecordingExecutor):
    def __init__(self, delay_seconds: float = 0.1) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds
        self._lock = Lock()

    def run(self, evaluation_id: str):
        with self._lock:
            self.calls.append(evaluation_id)
        time.sleep(self.delay_seconds)
        return self.report


class BlockingExecutor(RecordingExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()

    def run(self, evaluation_id: str):
        self.calls.append(evaluation_id)
        self.started.set()
        assert self.release.wait(timeout=5)
        return self.report


def evaluation_report(*, failed_case_id: str | None = None) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for category, count in EXPECTED_CATEGORY_COUNTS.items():
        for ordinal in range(1, count + 1):
            case_id = f"{category}-{ordinal:02d}"
            passed = case_id != failed_case_id
            cases.append(
                {
                    "id": case_id,
                    "category": category,
                    "passed": passed,
                    "expected_status": "completed",
                    "actual_status": "completed" if passed else "failed",
                    "source_recall": 1.0 if passed else 0.0,
                    "supported_claims": 1 if passed else 0,
                    "latency_ms": 10.0,
                }
            )
    failures = [item["id"] for item in cases if not item["passed"]]
    hard_gates = {**HARD_GATES, "all_cases_pass": not failures}
    return {
        "schema_version": 2,
        "status": "passed" if not failures else "failed",
        "mode": "deterministic_recording",
        "provenance": {
            "evaluator_sha256": "e" * 64,
            "external_provider_calls": 0,
            "claim_boundary": "This is deterministic architecture evidence; it is not a real-model quality benchmark.",
        },
        "dataset": {
            "name": "v5_fixed_evidence_cases",
            "path": "evaluation/v5/cases.jsonl",
            "sha256": "d" * 64,
            "case_count": 60,
            "category_counts": EXPECTED_CATEGORY_COUNTS,
        },
        "retrieval": {"arms": {"fusion": {"recall_at_k": 1.0, "ndcg_at_k": 0.99}}},
        "metrics": {
            "case_pass_rate": (60 - len(failures)) / 60,
            "mean_source_recall": 1.0 if not failures else 0.98,
            "citation_completeness": 1.0,
            "immutable_evidence_identity_rate": 1.0,
            "unauthorized_action_rate": 0.0,
            "recovery_scenario_pass_rate": 1.0,
            "multi_hop_agent_lift_pp": 58.33,
            "failure_case_ids": failures,
        },
        "hard_gates": hard_gates,
        "cases": cases,
    }


def test_start_is_idempotent_atomic_and_rejects_changed_payload(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW)
    first = control.submit(StartEvaluation(request_id="request-1", label="Fixed baseline"))
    replay = control.submit(StartEvaluation(request_id="request-1", label="Fixed baseline"))
    assert first.evaluation_id == replay.evaluation_id
    assert replay.replayed is True

    with control_factory() as session:
        assert session.query(AgentEvaluation).count() == 1
        messages = session.scalars(select(OutboxMessage)).all()
        assert len(messages) == 1
        assert messages[0].topic == "agent.evaluate"
        assert json.loads(messages[0].payload_json) == {"evaluation_id": first.evaluation_id}

    with pytest.raises(ServiceError) as exc_info:
        control.submit(StartEvaluation(request_id="request-1", label="Changed label"))
    assert exc_info.value.code == "EVALUATION_IDEMPOTENCY_CONFLICT"


def test_concurrent_duplicate_start_converges_to_one_evaluation(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW)

    def submit(_index: int):
        return control.submit(StartEvaluation(request_id="request-concurrent", label="Concurrent"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = tuple(pool.map(submit, range(2)))
    assert len({item.evaluation_id for item in receipts}) == 1
    assert sorted(item.replayed for item in receipts) == [False, True]
    with control_factory() as session:
        assert session.query(AgentEvaluation).count() == 1
        assert session.query(OutboxMessage).count() == 1


def test_start_rolls_back_evaluation_when_outbox_flush_fails(control_factory) -> None:
    def fail_outbox(session, _flush_context, _instances) -> None:
        if any(isinstance(item, OutboxMessage) for item in session.new):
            raise RuntimeError("injected outbox write failure")

    event.listen(control_factory.class_, "before_flush", fail_outbox)
    try:
        with pytest.raises(RuntimeError, match="injected outbox write failure"):
            SqlAgentControl(control_factory).submit(
                StartEvaluation(request_id="request-outbox-failure", label="Atomic")
            )
    finally:
        event.remove(control_factory.class_, "before_flush", fail_outbox)
    with control_factory() as session:
        assert session.query(AgentEvaluation).count() == 0
        assert session.query(OutboxMessage).count() == 0


def test_execute_claims_once_persists_immutable_report_and_lists_summary(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW)
    receipt = control.submit(StartEvaluation(request_id="request-pass", label="Passing evaluation"))
    executor = RecordingExecutor()
    detail = control.execute(
        ExecuteEvaluation(evaluation_id=receipt.evaluation_id, worker_id="worker-1"),
        executor,
    )
    assert detail.summary.status is EvaluationStatus.PASSED
    assert detail.summary.case_count == 60
    assert detail.summary.case_pass_rate == 1.0
    assert detail.summary.external_provider_calls == 0
    assert len(detail.cases) == 60
    assert detail.failure_case_ids == ()
    assert executor.calls == [receipt.evaluation_id]

    replay = control.execute(
        ExecuteEvaluation(evaluation_id=receipt.evaluation_id, worker_id="worker-2"),
        executor,
    )
    assert replay.summary.status is EvaluationStatus.PASSED
    assert executor.calls == [receipt.evaluation_id]
    catalog = control.inspect(ListEvaluations(status=EvaluationStatus.PASSED, limit=1))
    assert catalog.items == (detail.summary,)

    with control_factory() as session:
        stored = session.get(AgentEvaluation, receipt.evaluation_id)
        assert stored is not None
        assert stored.attempt == 1
        assert stored.report_sha256 is not None
        original_digest = stored.report_sha256
    control.execute(ExecuteEvaluation(receipt.evaluation_id, "worker-3"), RecordingExecutor(evaluation_report(failed_case_id="single_hop-01")))
    with control_factory() as session:
        assert session.get(AgentEvaluation, receipt.evaluation_id).report_sha256 == original_digest


def test_concurrent_execute_calls_invoke_the_executor_only_once(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW)
    receipt = control.submit(StartEvaluation(request_id="request-execute-race", label="Race"))
    executor = SlowRecordingExecutor()

    def execute(worker: str):
        return control.execute(ExecuteEvaluation(receipt.evaluation_id, worker), executor)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(execute, ("worker-a", "worker-b")))
    assert executor.calls == [receipt.evaluation_id]
    assert EvaluationStatus.PASSED in {item.summary.status for item in results}
    assert control.inspect(GetEvaluation(receipt.evaluation_id)).summary.status is EvaluationStatus.PASSED


def test_execute_records_dishonest_report_and_secret_executor_error_without_leaking(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW)
    dishonest = evaluation_report()
    dishonest["provenance"] = {**dishonest["provenance"], "external_provider_calls": 1}
    receipt = control.submit(StartEvaluation(request_id="request-dishonest", label="Dishonest"))
    detail = control.execute(
        ExecuteEvaluation(receipt.evaluation_id, "worker-1"),
        RecordingExecutor(dishonest),
    )
    assert detail.summary.status is EvaluationStatus.FAILED
    assert detail.error_code == "EVALUATION_REPORT_DISHONEST"
    assert detail.triage.category.value == "malformed_report"

    failed = control.submit(StartEvaluation(request_id="request-executor", label="Executor failure"))
    detail = control.execute(
        ExecuteEvaluation(failed.evaluation_id, "worker-1"),
        RecordingExecutor(error=EvaluationExecutionError("EVALUATION_TIMEOUT", "api_key=sk-supersecretvalue")),
    )
    assert detail.error_code == "EVALUATION_TIMEOUT"
    assert detail.error_message == "[redacted]"
    assert "sk-supersecretvalue" not in json.dumps(asdict(detail), ensure_ascii=False, default=str)


def test_stale_running_recovery_is_idempotent_and_does_not_reexecute_snapshot(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW, lease_seconds=30)
    receipt = control.submit(StartEvaluation(request_id="request-stale", label="Stale"))
    with control_factory.begin() as session:
        evaluation = session.get(AgentEvaluation, receipt.evaluation_id)
        evaluation.status = EvaluationStatus.RUNNING.value
        evaluation.lease_owner = "dead-worker"
        evaluation.lease_expires_at = NOW - timedelta(seconds=1)
        evaluation.attempt = 1

    assert control.recover(RecoverEvaluations(now=NOW)) == 1
    assert control.recover(RecoverEvaluations(now=NOW)) == 0
    detail = control.inspect(GetEvaluation(receipt.evaluation_id))
    assert detail.summary.status is EvaluationStatus.FAILED
    assert detail.error_code == "EVALUATION_WORKER_INTERRUPTED"
    executor = RecordingExecutor()
    control.execute(ExecuteEvaluation(receipt.evaluation_id, "worker-new"), executor)
    assert executor.calls == []

    rerun = control.submit(StartEvaluation(request_id="request-stale-rerun", label="Stale rerun"))
    assert rerun.evaluation_id != receipt.evaluation_id


def test_late_executor_result_cannot_overwrite_an_expired_recovered_lease(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW, lease_seconds=1)
    receipt = control.submit(StartEvaluation(request_id="request-late-result", label="Late"))
    executor = BlockingExecutor()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            control.execute,
            ExecuteEvaluation(receipt.evaluation_id, "old-worker"),
            executor,
        )
        assert executor.started.wait(timeout=5)
        assert control.recover(RecoverEvaluations(now=NOW + timedelta(seconds=2))) == 1
        executor.release.set()
        result = future.result(timeout=5)

    assert result.summary.status is EvaluationStatus.FAILED
    assert result.error_code == "EVALUATION_WORKER_INTERRUPTED"
    with control_factory() as session:
        stored = session.get(AgentEvaluation, receipt.evaluation_id)
        assert stored.report_json is None
        assert stored.report_sha256 is None


def test_sql_comparison_uses_terminal_validated_snapshots(control_factory) -> None:
    control = SqlAgentControl(control_factory, clock=lambda: NOW)
    left = control.submit(StartEvaluation(request_id="compare-left", label="Left"))
    right = control.submit(StartEvaluation(request_id="compare-right", label="Right"))
    control.execute(ExecuteEvaluation(left.evaluation_id, "worker"), RecordingExecutor())
    control.execute(
        ExecuteEvaluation(right.evaluation_id, "worker"),
        RecordingExecutor(evaluation_report(failed_case_id="single_hop-01")),
    )
    comparison = control.inspect(CompareEvaluations(left.evaluation_id, right.evaluation_id))
    assert comparison.verdict is ComparisonVerdict.REGRESSED
    assert comparison.new_failure_case_ids == ("single_hop-01",)
    assert any(item.metric == "case_pass_rate" and item.regressed for item in comparison.metric_deltas)


def test_run_trace_query_reads_persisted_facts_and_redacts_private_payloads(control_factory) -> None:
    with control_factory.begin() as session:
        space = KnowledgeSpace(name="Trace", description="V5.2")
        session.add(space)
        session.flush()
        run = AgentRun(
            id="trace-run",
            space_id=space.id,
            goal="Explain trace",
            requested_mode="force_agent",
            effective_mode="force_agent",
            status="completed",
            phase="persist_artifact",
            version=3,
            execution_epoch=0,
            scope_snapshot_json="{}",
            scope_digest="a" * 64,
            deliverable_json="{}",
            policy_snapshot_json="{}",
            budget_limits_json='{"max_steps":8}',
            budget_usage_json='{"steps":3}',
            provider_mode="demo",
            trace_id="trace-id",
            active_elapsed_ms=100,
            created_at=NOW,
            started_at=NOW,
            finished_at=NOW + timedelta(seconds=1),
        )
        session.add(run)
        session.flush()
        session.add_all(
            (
                AgentEvent(
                    event_id="event-1",
                    run_id=run.id,
                    run_sequence=1,
                    run_version=1,
                    event_type="run.opened",
                    payload_json='{"status":"queued"}',
                    schema_version=1,
                    visibility="public",
                    trace_id=run.trace_id,
                    created_at=NOW,
                ),
                AgentEvent(
                    event_id="event-2",
                    run_id=run.id,
                    run_sequence=2,
                    run_version=2,
                    event_type="model.started",
                    payload_json='{"prompt":"private", "api_key":"sk-hidden-secret"}',
                    schema_version=1,
                    visibility="private",
                    trace_id=run.trace_id,
                    created_at=NOW + timedelta(milliseconds=100),
                ),
                AgentEvent(
                    event_id="event-3",
                    run_id=run.id,
                    run_sequence=3,
                    run_version=3,
                    event_type="run.completed",
                    payload_json='{"status":"completed"}',
                    schema_version=1,
                    visibility="public",
                    trace_id=run.trace_id,
                    created_at=NOW + timedelta(seconds=1),
                ),
                AgentToolCall(
                    id="tool-trace",
                    run_id=run.id,
                    invocation_key="tool-trace",
                    tool_name="search_evidence",
                    tool_version="1",
                    effect="read_evidence",
                    arguments_json='{"query":"secret evidence"}',
                    arguments_digest="b" * 64,
                    status="completed",
                    execution_epoch=0,
                    started_at=NOW,
                    finished_at=NOW + timedelta(milliseconds=20),
                ),
                AgentModelCall(
                    id="model-trace",
                    run_id=run.id,
                    invocation_key="model-trace",
                    operation="route",
                    provider="recording",
                    model="evaluation-agent-v1",
                    schema_version=1,
                    status="completed",
                    input_tokens=5,
                    output_tokens=2,
                    cost_micros=0,
                    latency_ms=10,
                    retries=0,
                    usage_estimated=1,
                    execution_epoch=0,
                ),
                AgentCheckpoint(
                    id="checkpoint-trace",
                    run_id=run.id,
                    run_version=3,
                    last_event_cursor=3,
                    state_schema_version=1,
                    checksum="c" * 64,
                    state_json='{"private":"state"}',
                    execution_epoch=0,
                    scope_digest=run.scope_digest,
                ),
            )
        )

    trace = SqlAgentControl(control_factory).inspect(GetRunTrace("trace-run"))
    rendered = json.dumps(asdict(trace), ensure_ascii=False, default=str)
    assert trace.replay.stored_state_matches is True
    assert trace.replay.redacted_event_count == 1
    assert trace.tool_calls[0].arguments_digest == "b" * 64
    assert '"prompt"' not in rendered
    assert '"state_json"' not in rendered
    assert "sk-hidden-secret" not in rendered
    assert "secret evidence" not in rendered


@pytest.mark.parametrize(
    "mutator",
    [
        lambda report: report.update({"mode": "real"}),
        lambda report: report["dataset"].update({"path": "C:/Users/private/arbitrary.jsonl"}),
        lambda report: report["metrics"].pop("citation_completeness"),
        lambda report: report["metrics"].update({"mean_source_recall": float("nan")}),
        lambda report: report["retrieval"]["arms"]["fusion"].update({"recall_at_k": float("inf")}),
        lambda report: report["cases"][0].update({"latency_ms": float("-inf")}),
        lambda report: report["cases"].__setitem__(1, {**report["cases"][1], "id": report["cases"][0]["id"]}),
        lambda report: report["provenance"].update({"claim_boundary": "real model benchmark"}),
    ],
)
def test_report_validator_rejects_dishonest_or_malformed_snapshots(mutator) -> None:
    report = evaluation_report()
    mutator(report)
    with pytest.raises(EvaluationReportError):
        validate_evaluation_report(report)
