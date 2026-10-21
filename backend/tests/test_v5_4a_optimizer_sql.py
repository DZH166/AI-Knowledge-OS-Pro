from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationStudy as OptimizationStudyRow
from app.models.optimizer import OptimizationTrial as OptimizationTrialRow
from app.models.outbox import OutboxMessage
from app.models.workbench import OptimizationStudyEvent
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy_optimizer.contracts import (
    RecoverOptimizations,
    ScoreWeights,
    SearchSpace,
    SearchSpaceBound,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer

from tests.test_v5_2_agent_control_sql import evaluation_report

NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)
DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"
SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(4, 16),
    comparative_top_k=SearchSpaceBound(6, 20),
    temporal_top_k=SearchSpaceBound(4, 18),
    minimum_score_millis=SearchSpaceBound(0, 200),
    max_hits_per_source=SearchSpaceBound(1, 6),
    neighbor_before=SearchSpaceBound(0, 2),
    neighbor_after=SearchSpaceBound(0, 2),
)
WEIGHTS = ScoreWeights(quality_weight_permille=700, cost_weight_permille=300)


@pytest.fixture()
def optimizer_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'optimizer.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = RetrievalPolicyConfig()
    with factory.begin() as session:
        session.add(
            AgentPolicyVersion(
                id=DEFAULT_POLICY_ID,
                policy_key="default-research",
                version=1,
                label="Balanced evidence retrieval",
                status="active",
                config_schema_version=1,
                config_json=canonical_policy_json(config),
                config_sha256=policy_fingerprint(config),
                base_policy_id=None,
                created_by="system:test",
                has_been_active=1,
            )
        )
    try:
        yield factory
    finally:
        engine.dispose()


def _optimizer(factory, *, lease_seconds: int = 900) -> SqlAgentPolicyOptimizer:
    return SqlAgentPolicyOptimizer(
        factory,
        clock=lambda: NOW,
        lease_seconds=lease_seconds,
    )


def _command(
    request_id: str = "study-request-1",
    *,
    max_candidates: int = 4,
    max_evaluations: int = 6,
    label: str = "Optimizer study",
) -> dict:
    return dict(
        request_id=request_id,
        label=label,
        base_policy_id=DEFAULT_POLICY_ID,
        objective=StudyObjective.BALANCED,
        max_candidates=max_candidates,
        max_evaluations=max_evaluations,
        search_space=SPACE,
        weights=WEIGHTS,
        seed=42,
    )


def _start_study(optimizer: SqlAgentPolicyOptimizer, **overrides) -> str:
    command = _command(**overrides) if overrides else _command()
    receipt = optimizer.submit(_study_command(**command))
    optimizer.start(receipt["study_id"])
    return receipt["study_id"]


def _study_command(**kwargs):
    from app.modules.agent_policy_optimizer.contracts import StudyCommand

    return StudyCommand(**kwargs)


def test_submit_is_idempotent_and_rejects_changed_payload(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    first = optimizer.submit(_study_command(**_command()))
    replay = optimizer.submit(_study_command(**_command()))
    assert first["study_id"] == replay["study_id"]
    assert replay["replayed"] is True
    with optimizer_factory() as session:
        assert session.query(OptimizationStudyRow).count() == 1
        assert session.query(OutboxMessage).count() == 0  # nothing queued before start

    with pytest.raises(ServiceError) as conflict:
        optimizer.submit(_study_command(**_command(label="Different")))
    assert conflict.value.code == "OPTIMIZER_IDEMPOTENCY_CONFLICT"

    with pytest.raises(ServiceError) as missing_policy:
        optimizer.submit(_study_command(**{**_command(), "request_id": "study-request-new", "base_policy_id": "policy-missing"}))
    assert missing_policy.value.code == "OPTIMIZER_POLICY_NOT_FOUND"


def test_deadline_is_idempotent_and_timezone_safe(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    payload = _command(request_id="deadline-study")
    first_deadline = NOW - timedelta(minutes=1)
    receipt = optimizer.submit(_study_command(**payload, deadline_at=first_deadline))

    with pytest.raises(ServiceError) as conflict:
        optimizer.submit(
            _study_command(**payload, deadline_at=NOW + timedelta(minutes=1))
        )
    assert conflict.value.code == "OPTIMIZER_IDEMPOTENCY_CONFLICT"

    started = optimizer.start(receipt["study_id"])
    assert started == {"study_id": receipt["study_id"], "status": "completed", "created": 0}
    with optimizer_factory() as session:
        event_types = session.scalars(
            select(OptimizationStudyEvent.event_type)
            .where(OptimizationStudyEvent.study_id == receipt["study_id"])
            .order_by(OptimizationStudyEvent.created_at, OptimizationStudyEvent.id)
        ).all()
    assert event_types == ["study_created", "study_completed"]


def test_start_creates_budgeted_trials_with_outbox_messages_atomically(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, max_candidates=4, max_evaluations=3)
    with optimizer_factory() as session:
        trials = session.scalars(
            select(OptimizationTrialRow).where(OptimizationTrialRow.study_id == study_id).order_by(OptimizationTrialRow.ordinal)
        ).all()
        assert [item.ordinal for item in trials] == [1, 2, 3]
        assert trials[0].is_baseline == 1
        assert all(item.status == "pending" for item in trials)
        assert len({item.config_sha256 for item in trials}) == 3
        messages = session.scalars(select(OutboxMessage).where(OutboxMessage.topic == "agent.optimize.trial")).all()
        assert len(messages) == 3
        study = session.get(OptimizationStudyRow, study_id)
        assert study.status == "running"
        assert json.loads(study.budget_usage_json) == {"created_trials": 3, "started_evaluations": 0}


def test_start_reports_exhausted_search_space_without_partial_state(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    base = RetrievalPolicyConfig()
    fixed_space = SearchSpace(
        **{
            field: SearchSpaceBound(getattr(base, field), getattr(base, field))
            for field in (
                "factual_top_k",
                "comparative_top_k",
                "temporal_top_k",
                "minimum_score_millis",
                "max_hits_per_source",
                "neighbor_before",
                "neighbor_after",
            )
        }
    )
    receipt = optimizer.submit(
        _study_command(
            **{
                **_command(request_id="exhausted-search"),
                "search_space": fixed_space,
            }
        )
    )
    with pytest.raises(ServiceError) as exhausted:
        optimizer.start(receipt["study_id"])
    assert exhausted.value.code == "OPTIMIZER_SEARCH_SPACE_EXHAUSTED"
    with optimizer_factory() as session:
        study = session.get(OptimizationStudyRow, receipt["study_id"])
        assert study.status == "pending"
        assert session.query(OptimizationTrialRow).count() == 0
        assert session.query(OutboxMessage).count() == 0


def test_execute_completes_trial_with_fenced_write_and_zero_provider_calls(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    detail = optimizer.execute(
        _execute_command(trial_id),
        _recording_executor(),
    )
    assert detail["status"] == "completed"
    assert detail["external_provider_calls"] == 0
    assert detail["metrics"]["latency_ms"] > 0
    with optimizer_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        assert trial.status == "completed"
        assert trial.score_millis is not None
        evaluation = session.get(AgentEvaluation, trial.evaluation_id)
        assert evaluation.status == "passed"
        assert evaluation.external_provider_calls == 0
        assert evaluation.policy_fingerprint == trial.config_sha256
        assert json.loads(evaluation.metrics_json)["latency_ms"]["agent_p95"] > 0


def test_scores_are_recomputed_over_full_completed_set(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, max_candidates=3, max_evaluations=3)
    with optimizer_factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id)
            .where(OptimizationTrialRow.study_id == study_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()
    first = optimizer.execute(_execute_command(trial_ids[0]), _recording_executor(agent_p95=300.0))
    assert first["score_millis"] == 500  # single completed trial -> degenerate 0.5
    second = optimizer.execute(_execute_command(trial_ids[1]), _recording_executor(agent_p95=100.0))
    assert second["score_millis"] != 500
    with optimizer_factory() as session:
        scores = {
            row.id: row.score_millis
            for row in session.scalars(
                select(OptimizationTrialRow).where(OptimizationTrialRow.study_id == study_id)
            )
        }
    assert scores[trial_ids[0]] != 500  # rescored against the full completed set
    assert scores[trial_ids[1]] == scores[trial_ids[0]] or scores[trial_ids[1]] is not None


def test_completed_trials_never_rerun(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    executor = _recording_executor()
    optimizer.execute(_execute_command(trial_id), executor)
    assert executor.calls == [trial_id]
    optimizer.execute(_execute_command(trial_id), executor)
    assert executor.calls == [trial_id]


def test_concurrent_execute_single_winner(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)

    def run(_index: int):
        return optimizer.execute(_execute_command(trial_id), _recording_executor())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(run, range(2)))
    # Both callers converge on the durable state, but exactly one worker
    # executed the evaluation and exactly one evaluation row exists.
    evaluation_ids = {item.get("evaluation_id") for item in results if item.get("evaluation_id")}
    assert len(evaluation_ids) == 1
    with optimizer_factory() as session:
        assert session.query(AgentEvaluation).count() == 1
        trial = session.get(OptimizationTrialRow, trial_id)
        assert trial.status == "completed"
        assert trial.attempt == 1


def test_late_worker_result_is_rejected_by_fence(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    first = optimizer.execute(_execute_command(trial_id), _recording_executor())
    assert first["status"] == "completed"
    finished_at = _trial_finished_at(optimizer_factory, trial_id)
    stale = optimizer.write_back(
        trial_id=trial_id,
        worker_id="stale-worker",
        report=evaluation_report(),
        completed_at=NOW + timedelta(seconds=1),
    )
    assert stale is False
    assert _trial_finished_at(optimizer_factory, trial_id) == finished_at


def test_cancelled_study_creates_no_new_trials(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, max_candidates=8, max_evaluations=8)
    optimizer.cancel(study_id)
    before = _trial_count(optimizer_factory)
    optimizer.start(study_id)  # re-drive must not create anything new
    with optimizer_factory() as session:
        study = session.get(OptimizationStudyRow, study_id)
        assert study.status == "cancelled"
        assert study.cancelled_at is not None
    assert _trial_count(optimizer_factory) == before
    assert _outbox_count(optimizer_factory) == before  # no fresh dispatch rows


def test_cancel_after_trials_marks_pending_trials_cancelled(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, max_candidates=4, max_evaluations=4)
    with optimizer_factory() as session:
        session.get(OptimizationStudyRow, study_id).status = "running"
    optimizer.cancel(study_id)
    with optimizer_factory() as session:
        statuses = {
            item.status for item in session.scalars(
                select(OptimizationTrialRow).where(OptimizationTrialRow.study_id == study_id)
            )
        }
    assert statuses == {"cancelled"}


def test_fingerprint_mismatched_report_fails_trial(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    executor = _recording_executor(reported_fingerprint="9" * 64)
    result = optimizer.execute(_execute_command(trial_id), executor)
    assert result["status"] == "failed"
    with optimizer_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        assert trial.failure_code == "OPTIMIZER_TRIAL_FINGERPRINT_MISMATCH"
        assert session.query(AgentEvaluation).count() == 0


def test_missing_report_fingerprint_cannot_complete_or_qualify_trial(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, request_id="missing-fingerprint-study")
    trial_id = _pending_trial_id(optimizer_factory, study_id)

    class MissingFingerprintExecutor:
        def run(self, _trial_id, _policy_snapshot):
            report = evaluation_report()
            report["metrics"]["latency_ms"] = {
                "quick_p50": 10.0,
                "quick_p95": 12.0,
                "agent_p50": 100.0,
                "agent_p95": 180.0,
            }
            return report

    detail = optimizer.execute(_execute_command(trial_id), MissingFingerprintExecutor())

    assert detail["status"] == "failed"
    assert detail["failure_code"] == "OPTIMIZER_TRIAL_FINGERPRINT_MISMATCH"
    assert all(item["trial_id"] != trial_id for item in optimizer.inspect_pareto(study_id)["items"])


def test_cancel_leaves_running_trial_to_finish(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    session = optimizer_factory()
    trial_row = session.get(OptimizationTrialRow, trial_id)
    trial_row.status = "running"
    trial_row.lease_owner = "worker:test"
    session.commit()
    session.close()
    optimizer.cancel(study_id)
    with optimizer_factory() as session:
        assert session.get(OptimizationTrialRow, trial_id).status == "running"

    session2 = optimizer_factory()
    running = session2.get(OptimizationTrialRow, trial_id)
    from tests.test_v5_2_agent_control_sql import evaluation_report as _report

    report = _report()
    report["provenance"]["retrieval_policy_sha256"] = running.config_sha256
    report["metrics"]["latency_ms"] = {
        "quick_p50": 10.0, "quick_p95": 12.0, "agent_p50": 100.0, "agent_p95": 180.0,
    }
    completed = optimizer.write_back(
        trial_id=trial_id,
        worker_id="worker:test",
        report=report,
        completed_at=NOW,
    )
    assert completed is True
    with optimizer_factory() as session:
        assert session.get(OptimizationTrialRow, trial_id).status == "completed"


def test_cancelled_running_trials_cannot_create_new_recommendations(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, request_id="cancelled-recommendation")
    with optimizer_factory.begin() as session:
        trials = session.scalars(
            select(OptimizationTrialRow)
            .where(OptimizationTrialRow.study_id == study_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()
        running = [(trial.id, trial.config_sha256) for trial in trials[:2]]
        for index, trial in enumerate(trials[:2], start=1):
            trial.status = "running"
            trial.lease_owner = f"worker:{index}"
    optimizer.cancel(study_id)

    for index, (trial_id, fingerprint) in enumerate(running, start=1):
        report = evaluation_report()
        report["provenance"]["retrieval_policy_sha256"] = fingerprint
        report["metrics"]["latency_ms"] = {
            "quick_p50": 10.0,
            "quick_p95": 12.0,
            "agent_p50": 100.0,
            "agent_p95": 100.0 + index,
        }
        assert optimizer.write_back(
            trial_id=trial_id,
            worker_id=f"worker:{index}",
            report=report,
            completed_at=NOW,
        )

    assert optimizer.inspect_recommendation(study_id)["candidates"] == []
    with optimizer_factory() as session:
        assert all(
            trial.recommendation_rank is None
            for trial in session.scalars(
                select(OptimizationTrialRow).where(OptimizationTrialRow.study_id == study_id)
            )
        )


def test_recovery_terminalizes_pending_trial_with_dead_letter(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(
        optimizer,
        request_id="dead-letter-study",
        max_candidates=1,
        max_evaluations=1,
    )
    with optimizer_factory.begin() as session:
        trial = session.scalar(
            select(OptimizationTrialRow).where(OptimizationTrialRow.study_id == study_id)
        )
        message = session.scalar(
            select(OutboxMessage).where(OutboxMessage.aggregate_id == trial.id)
        )
        message.status = "dead_letter"
        message.last_error = "Redis unavailable after maximum attempts"
        trial_id = trial.id

    assert optimizer.recover(RecoverOptimizations(now=NOW)) == 0
    with optimizer_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        study = session.get(OptimizationStudyRow, study_id)
        assert trial.status == "failed"
        assert trial.failure_code == "OPTIMIZER_DISPATCH_DEAD_LETTER"
        assert study.status == "failed"


def test_budget_exhaustion_stops_trial_creation(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, max_candidates=2, max_evaluations=1)
    with optimizer_factory() as session:
        assert session.query(OptimizationTrialRow).count() == 1
        study = session.get(OptimizationStudyRow, study_id)
        assert study.status == "running"
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    optimizer.execute(_execute_command(trial_id), _recording_executor())
    with optimizer_factory() as session:
        study = session.get(OptimizationStudyRow, study_id)
        assert study.status == "completed"  # evaluation budget used up


def test_recovery_takeover_does_not_overwrite_completed_results(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory, lease_seconds=30)
    study_id = _start_study(optimizer)
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    optimizer.execute(_execute_command(trial_id), _recording_executor())
    with optimizer_factory() as session:
        session.get(OptimizationTrialRow, trial_id).lease_expires_at = NOW - timedelta(seconds=1)
    optimizer.recover(_recover_command(NOW))
    with optimizer_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        assert trial.status == "completed"

    stale_running = _insert_running_trial(optimizer_factory, study_id, ordinal=9)
    recovered = optimizer.recover(_recover_command(NOW + timedelta(seconds=60)))
    assert recovered >= 1
    with optimizer_factory() as session:
        assert session.get(OptimizationTrialRow, stale_running).status == "pending"


def test_recovery_requeues_published_outbox_for_expired_trial(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory, lease_seconds=5)
    study_id = _start_study(optimizer, request_id="recover-published-study")
    trial_id = _pending_trial_id(optimizer_factory, study_id)
    with optimizer_factory.begin() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        trial.status = "running"
        trial.lease_owner = "worker:crashed"
        trial.lease_expires_at = NOW - timedelta(seconds=1)
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.aggregate_id == trial_id))
        assert message is not None
        message.status = "published"
        message.published_at = NOW - timedelta(seconds=2)

    recovered = optimizer.recover(RecoverOptimizations(now=NOW))

    assert recovered == 1
    with optimizer_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.aggregate_id == trial_id))
        assert trial.status == "pending"
        assert message.status == "pending"
        assert message.published_at is None


def test_inspect_reports_pareto_and_recommendation(optimizer_factory) -> None:
    optimizer = _optimizer(optimizer_factory)
    study_id = _start_study(optimizer, max_candidates=3, max_evaluations=3)
    with optimizer_factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id)
            .where(OptimizationTrialRow.study_id == study_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()
    for trial_id in trial_ids:
        optimizer.execute(_execute_command(trial_id), _recording_executor())
    study = optimizer.inspect_study(study_id)
    assert study["status"] == "completed"
    frontier = optimizer.inspect_pareto(study_id)
    assert len(frontier["items"]) >= 1
    assert all(item["eligible"] for item in frontier["items"])
    recommendation = optimizer.inspect_recommendation(study_id)
    assert len(recommendation["candidates"]) >= 1
    assert recommendation["candidates"][0]["rationale"]


def _pending_trial_id(factory, study_id: str) -> str:
    with factory() as session:
        return session.scalars(
            select(OptimizationTrialRow.id)
            .where(OptimizationTrialRow.study_id == study_id, OptimizationTrialRow.status == "pending")
            .order_by(OptimizationTrialRow.ordinal)
            .limit(1)
        ).one()


def _execute_command(trial_id: str):
    from app.modules.agent_policy_optimizer.contracts import ExecuteTrial

    return ExecuteTrial(trial_id=trial_id, worker_id="optimizer-worker")


def _recover_command(now: datetime):
    from app.modules.agent_policy_optimizer.contracts import RecoverOptimizations

    return RecoverOptimizations(now=now)


def _trial_count(factory) -> int:
    with factory() as session:
        return session.query(OptimizationTrialRow).count()


def _outbox_count(factory) -> int:
    with factory() as session:
        return session.query(OutboxMessage).count()


def _trial_finished_at(factory, trial_id: str) -> object:
    with factory() as session:
        return session.get(OptimizationTrialRow, trial_id).finished_at


def _insert_running_trial(factory, study_id: str, *, ordinal: int) -> str:
    from app.modules.agent_policy.config import RetrievalPolicyConfig as Config

    config = Config(factual_top_k=5)
    with factory.begin() as session:
        row = OptimizationTrialRow(
            id=f"trial-stale-{ordinal}",
            study_id=study_id,
            ordinal=ordinal,
            status="running",
            config_sha256=policy_fingerprint(config),
            config_json=canonical_policy_json(config),
            is_baseline=0,
            dominated=0,
            attempt=1,
            lease_owner="gone-worker",
            lease_expires_at=NOW - timedelta(seconds=5),
        )
        session.add(row)
        return row.id


class _RecordingExecutor:
    def __init__(
        self,
        reported_fingerprint: str | None = None,
        agent_p95: float | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.reported_fingerprint = reported_fingerprint
        self.agent_p95 = agent_p95

    def run(self, trial_id: str, policy_snapshot):
        self.calls.append(trial_id)
        report = evaluation_report()
        if policy_snapshot is not None:
            report["provenance"]["retrieval_policy_sha256"] = (
                self.reported_fingerprint
                if self.reported_fingerprint is not None
                else policy_snapshot.config_sha256
            )
            report["metrics"]["latency_ms"] = {
                "quick_p50": 10.0,
                "quick_p95": 12.0,
                "agent_p50": 100.0 + len(policy_snapshot.config_json) % 7,
                "agent_p95": self.agent_p95 or 180.0 + len(policy_snapshot.config_json) % 11,
            }
        return report


def _recording_executor(
    reported_fingerprint: str | None = None,
    agent_p95: float | None = None,
) -> _RecordingExecutor:
    return _RecordingExecutor(
        reported_fingerprint=reported_fingerprint,
        agent_p95=agent_p95,
    )
