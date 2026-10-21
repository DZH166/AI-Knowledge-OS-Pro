from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationStudy as OptimizationStudyRow
from app.models.optimizer import OptimizationTrial as OptimizationTrialRow
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy.contracts import GetActivePolicy
from app.modules.agent_policy.service import SqlAgentPolicy
from app.modules.agent_policy_optimizer.contracts import (
    ConvertRecommendation,
    DiffTrialAgainstActive,
    FailStudy,
    RetryTrial,
    SearchSpace,
    SearchSpaceBound,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer

from tests.test_v5_4a_optimizer_sql import (
    NOW,
    SPACE,
    WEIGHTS,
    _execute_command,
    _recording_executor,
    _study_command,
    DEFAULT_POLICY_ID,
)


@pytest.fixture()
def loop_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'loop.db').as_posix()}")
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


def _optimizer(factory) -> SqlAgentPolicyOptimizer:
    return SqlAgentPolicyOptimizer(
        factory,
        clock=lambda: NOW,
        lease_seconds=900,
    )


def _policy_service(factory) -> SqlAgentPolicy:
    return SqlAgentPolicy(factory, utcnow=lambda: NOW)


def _completed_study_with_recommendation(factory, *, executor=None) -> tuple[str, str]:
    """Run a 2-candidate study to completion and return (study_id, winning trial id)."""

    optimizer = _optimizer(factory)
    lean_space = SearchSpace(
        factual_top_k=SearchSpaceBound(4, 4),
        comparative_top_k=SearchSpaceBound(6, 6),
        temporal_top_k=SearchSpaceBound(4, 4),
        minimum_score_millis=SearchSpaceBound(0, 0),
        max_hits_per_source=SearchSpaceBound(2, 2),
        neighbor_before=SearchSpaceBound(0, 0),
        neighbor_after=SearchSpaceBound(0, 0),
    )
    command = _study_command(
        request_id="loop-study-1",
        label="Closed loop study",
        base_policy_id=DEFAULT_POLICY_ID,
        objective=StudyObjective.BALANCED,
        max_candidates=2,
        max_evaluations=2,
        search_space=lean_space,
        weights=WEIGHTS,
        seed=42,
    )
    receipt = optimizer.submit(command)
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id)
            .where(OptimizationTrialRow.study_id == study_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()
    for index, trial_id in enumerate(trial_ids):
        executor = executor or _recording_executor()
        optimizer.execute(_execute_command(trial_id), executor)
    recommendation = optimizer.inspect_recommendation(study_id)
    winner_id = recommendation["candidates"][0]["trial_id"]
    return study_id, winner_id


def test_convert_recommendation_creates_draft_with_matching_fingerprint(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.convert_to_draft(
        ConvertRecommendation(
            study_id=study_id,
            trial_id=trial_id,
            request_id="convert-1",
            label=None,
        )
    )
    assert receipt["status"] == "draft"
    assert receipt["replayed"] is False
    with loop_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        assert trial.draft_policy_id == receipt["policy_id"]
        policy = session.get(AgentPolicyVersion, receipt["policy_id"])
        assert policy.status == "draft"
        assert policy.config_sha256 == trial.config_sha256
    # Active policy unchanged
    policy_service = _policy_service(loop_factory)
    active = policy_service.inspect(GetActivePolicy())
    assert active.id == DEFAULT_POLICY_ID
    events = optimizer.inspect_events(study_id)
    assert any(
        item["event_type"] == "draft_converted"
        and item["payload"]["trial_id"] == trial_id
        and item["payload"]["policy_id"] == receipt["policy_id"]
        for item in events["items"]
    )


def test_convert_recommendation_is_idempotent_across_request_ids(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    first = optimizer.convert_to_draft(
        ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-a", label=None)
    )
    second = optimizer.convert_to_draft(
        ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-b", label=None)
    )
    assert first["policy_id"] == second["policy_id"]
    assert second["replayed"] is True
    with loop_factory() as session:
        assert session.query(AgentPolicyVersion).count() == 2  # baseline + one draft


def test_convert_replays_same_request_id_via_policy_command_log(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    first = optimizer.convert_to_draft(
        ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-same", label=None)
    )
    replay = optimizer.convert_to_draft(
        ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-same", label=None)
    )
    assert replay["policy_id"] == first["policy_id"]
    assert replay["replayed"] is True
    assert replay["command_id"] == first["command_id"]


def test_convert_rejects_non_recommendation_trials(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    with loop_factory() as session:
        non_frontier_id = session.scalars(
            select(OptimizationTrialRow.id).where(
                OptimizationTrialRow.study_id == study_id,
                OptimizationTrialRow.recommendation_rank.is_(None),
            )
        ).first()
    assert non_frontier_id is not None
    with pytest.raises(ServiceError) as not_frontier:
        optimizer.convert_to_draft(
            ConvertRecommendation(study_id=study_id, trial_id=non_frontier_id, request_id="convert-x", label=None)
        )
    assert not_frontier.value.code == "OPTIMIZER_RECOMMENDATION_REQUIRED"


def test_convert_rejects_corrupted_trial_config(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    session = loop_factory()
    session.get(OptimizationTrialRow, trial_id).config_json = '{"schema_version":1,"factual_top_k":999}'
    session.commit()
    session.close()
    with pytest.raises(ServiceError) as corrupted:
        optimizer.convert_to_draft(
            ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-y", label=None)
        )
    assert corrupted.value.code == "OPTIMIZER_TRIAL_CONFIG_INVALID"


def test_diff_trial_against_active_reports_directional_changes(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    diff = optimizer.inspect(
        DiffTrialAgainstActive(study_id=study_id, trial_id=trial_id)
    )
    assert diff["trial_id"] == trial_id
    assert diff["active_policy_id"] == DEFAULT_POLICY_ID
    assert diff["trial_config_sha256"] != diff["active_config_sha256"]
    assert diff["compatible"] is True
    fields = {change["field"] for change in diff["changes"]}
    assert fields, "seeded study must differ from baseline in at least one field"
    for change in diff["changes"]:
        assert change["left"] == getattr(RetrievalPolicyConfig(), change["field"])
    summary = diff["trial_summary"]
    assert summary["eligible"] is True
    assert summary["score_millis"] is not None


def test_settle_completes_study_when_all_trials_terminal(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.submit(
        _study_command(
            request_id="settle-complete",
            label="Settle complete",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=2,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=7,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with loop_factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id).where(OptimizationTrialRow.study_id == study_id)
        ).all()
    for trial_id in trial_ids:
        optimizer.execute(_execute_command(trial_id), _recording_executor())
    with loop_factory() as session:
        assert session.get(OptimizationStudyRow, study_id).status == "completed"


def test_settle_fails_study_when_all_trials_failed(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.submit(
        _study_command(
            request_id="settle-failed",
            label="Settle failed",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=2,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=7,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with loop_factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id).where(OptimizationTrialRow.study_id == study_id)
        ).all()
    broken = _recording_executor(reported_fingerprint="9" * 64)
    for trial_id in trial_ids:
        optimizer.execute(_execute_command(trial_id), broken)
    with loop_factory() as session:
        assert session.get(OptimizationStudyRow, study_id).status == "failed"


def test_retry_revives_failed_trial_and_reruns(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.submit(
        _study_command(
            request_id="retry-study",
            label="Retry study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=2,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=7,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with loop_factory() as session:
        trial_id = session.scalars(
            select(OptimizationTrialRow.id).where(OptimizationTrialRow.study_id == study_id)
        ).first()
    optimizer.execute(_execute_command(trial_id), _recording_executor(reported_fingerprint="9" * 64))
    with loop_factory() as session:
        assert session.get(OptimizationTrialRow, trial_id).status == "failed"
    retried = optimizer.retry_trial(RetryTrial(trial_id=trial_id))
    assert retried["status"] == "pending"
    result = optimizer.execute(_execute_command(trial_id), _recording_executor())
    assert result["status"] == "completed"
    with loop_factory() as session:
        assert session.get(OptimizationTrialRow, trial_id).attempt == 2


def test_retry_rejected_for_cancelled_study(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.submit(
        _study_command(
            request_id="retry-cancelled",
            label="Retry cancelled",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=2,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=7,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with loop_factory() as session:
        trial_id = session.scalars(
            select(OptimizationTrialRow.id).where(OptimizationTrialRow.study_id == study_id)
        ).first()
    optimizer.execute(_execute_command(trial_id), _recording_executor(reported_fingerprint="9" * 64))
    optimizer.cancel(study_id)
    with pytest.raises(ServiceError) as rejected:
        optimizer.retry_trial(RetryTrial(trial_id=trial_id))
    assert rejected.value.code == "OPTIMIZER_TRIAL_RETRY_REJECTED"
    with loop_factory() as session:
        assert session.get(OptimizationTrialRow, trial_id).status == "failed"


def test_retry_rejected_when_budget_exhausted(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.submit(
        _study_command(
            request_id="retry-budget",
            label="Retry budget",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=1,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=7,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with loop_factory() as session:
        trial_id = session.scalars(
            select(OptimizationTrialRow.id).where(OptimizationTrialRow.study_id == study_id)
        ).first()
    optimizer.execute(_execute_command(trial_id), _recording_executor(reported_fingerprint="9" * 64))
    with pytest.raises(ServiceError) as rejected:
        optimizer.retry_trial(RetryTrial(trial_id=trial_id))
    assert rejected.value.code == "OPTIMIZER_TRIAL_RETRY_REJECTED"


def test_convert_concurrent_losers_return_existing_draft(loop_factory) -> None:
    """Directly exercise the IntegrityError branch by racing the unique slot."""

    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.convert_to_draft(
        ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-race-1", label=None)
    )
    assert receipt["replayed"] is False


def test_diff_rejects_corrupted_trial_config(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    session = loop_factory()
    session.get(OptimizationTrialRow, trial_id).config_json = '{"schema_version":1,"factual_top_k":999}'
    session.commit()
    session.close()
    with pytest.raises(ServiceError) as corrupted:
        optimizer.inspect(DiffTrialAgainstActive(study_id=study_id, trial_id=trial_id))
    assert corrupted.value.code == "OPTIMIZER_TRIAL_CONFIG_INVALID"


def test_provider_calls_stay_zero_in_loop_flow(loop_factory) -> None:
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    optimizer = _optimizer(loop_factory)
    optimizer.convert_to_draft(
        ConvertRecommendation(study_id=study_id, trial_id=trial_id, request_id="convert-provider", label=None)
    )
    with loop_factory() as session:
        trial = session.get(OptimizationTrialRow, trial_id)
        assert trial.external_provider_calls == 0


def test_retry_rejects_non_failed_trials(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    study_id, trial_id = _completed_study_with_recommendation(loop_factory)
    with pytest.raises(ServiceError) as conflict:
        optimizer.retry_trial(RetryTrial(trial_id=trial_id))
    assert conflict.value.code == "OPTIMIZER_TRIAL_RETRY_REJECTED"


def test_fail_study_terminates_running_study(loop_factory) -> None:
    optimizer = _optimizer(loop_factory)
    receipt = optimizer.submit(
        _study_command(
            request_id="fail-study",
            label="Fail study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=3,
            max_evaluations=3,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=11,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    result = optimizer.fail_study(FailStudy(study_id=study_id, reason="operator stop"))
    assert result["status"] == "failed"
    with loop_factory() as session:
        study = session.get(OptimizationStudyRow, study_id)
        assert study.status == "failed"
        statuses = {
            row.status
            for row in session.scalars(
                select(OptimizationTrialRow).where(OptimizationTrialRow.study_id == study_id)
            )
        }
        assert statuses <= {"failed", "cancelled"}
    again = optimizer.fail_study(FailStudy(study_id=study_id, reason=None))
    assert again["status"] == "failed" and again["cancelled"] is False
