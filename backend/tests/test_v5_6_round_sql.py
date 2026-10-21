from __future__ import annotations

import json
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
from app.modules.agent_policy_optimizer.contracts import (
    NextRound,
    StudyCommand,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer

from tests.test_v5_4a_optimizer_sql import (
    NOW,
    SPACE,
    WEIGHTS,
    _execute_command,
    _recording_executor,
)
from tests.test_v5_2_agent_control_sql import evaluation_report

BASELINE_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def round_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'round.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = RetrievalPolicyConfig()
    with factory.begin() as session:
        session.add(
            AgentPolicyVersion(
                id=BASELINE_ID,
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


def _command(request_id: str, **overrides) -> StudyCommand:
    values = dict(
        request_id=request_id,
        label="Bayesian study",
        base_policy_id=BASELINE_ID,
        objective=StudyObjective.BALANCED,
        max_candidates=3,
        max_evaluations=9,
        search_space=SPACE,
        weights=WEIGHTS,
        seed=42,
    )
    values.update(overrides)
    return StudyCommand(**values)


def _run_study_to_completion(factory, optimizer, study_id: str) -> list[str]:
    optimizer.start(study_id)
    with factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id)
            .where(OptimizationTrialRow.study_id == study_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()
    for trial_id in trial_ids:
        optimizer.execute(_execute_command(trial_id), _recording_executor())
    return trial_ids


def test_next_round_appends_guided_trials_and_returns_running(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("round-study-1", max_candidates=6))
    study_id = receipt["study_id"]
    first_trial_ids = _run_study_to_completion(round_factory, optimizer, study_id)
    with round_factory() as session:
        assert session.get(OptimizationStudyRow, study_id).status == "completed"

    result = optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-1"))
    assert result["round_no"] == 2
    assert result["created"] >= 1
    with round_factory() as session:
        study = session.get(OptimizationStudyRow, study_id)
        assert study.status == "running"
        assert study.round_no == 2
        ordinals = session.scalars(
            select(OptimizationTrialRow.ordinal).where(OptimizationTrialRow.study_id == study_id)
        ).all()
        assert sorted(ordinals) == list(range(1, len(ordinals) + 1))
        assert len(ordinals) > len(first_trial_ids)


def test_next_round_is_idempotent_on_request_id(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("round-study-2", max_candidates=6))
    study_id = receipt["study_id"]
    _run_study_to_completion(round_factory, optimizer, study_id)
    first = optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-same"))
    replay = optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-same"))
    assert replay["round_no"] == first["round_no"]
    assert replay["replayed"] is True
    with round_factory() as session:
        counts = session.query(OptimizationTrialRow).filter_by(study_id=study_id).count()
        assert counts == 6  # max_candidates is the cumulative Study budget.
        # A replayed request must not create any additional trials.
        assert replay["created"] == first["created"]


def test_historical_round_request_replays_its_original_receipt(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("round-history", max_candidates=9, max_evaluations=9))
    study_id = receipt["study_id"]
    _run_study_to_completion(round_factory, optimizer, study_id)

    round_two = optimizer.start_next_round(NextRound(study_id=study_id, request_id="round-history-2"))
    with round_factory() as session:
        pending = session.scalars(
            select(OptimizationTrialRow.id).where(
                OptimizationTrialRow.study_id == study_id,
                OptimizationTrialRow.status == "pending",
            )
        ).all()
    for trial_id in pending:
        optimizer.execute(_execute_command(trial_id), _recording_executor())
    optimizer.start_next_round(NextRound(study_id=study_id, request_id="round-history-3"))

    replay = optimizer.start_next_round(NextRound(study_id=study_id, request_id="round-history-2"))

    assert replay == {**round_two, "replayed": True}


def test_next_round_rejects_non_completed_study(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("round-study-3"))
    study_id = receipt["study_id"]
    with pytest.raises(ServiceError) as pending:
        optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-early"))
    assert pending.value.code == "OPTIMIZER_STUDY_NOT_COMPLETED"
    optimizer.start(study_id)
    with pytest.raises(ServiceError) as running:
        optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-running"))
    assert running.value.code == "OPTIMIZER_STUDY_NOT_COMPLETED"


def test_next_round_respects_total_budget(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("round-study-4", max_candidates=4, max_evaluations=4))
    study_id = receipt["study_id"]
    _run_study_to_completion(round_factory, optimizer, study_id)
    final_round = optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-final"))
    assert final_round["created"] == 1
    with round_factory() as session:
        final_trial_ids = session.scalars(
            select(OptimizationTrialRow.id).where(
                OptimizationTrialRow.study_id == study_id,
                OptimizationTrialRow.status == "pending",
            )
        ).all()
    for trial_id in final_trial_ids:
        optimizer.execute(_execute_command(trial_id), _recording_executor())
    with pytest.raises(ServiceError) as exhausted:
        optimizer.start_next_round(NextRound(study_id=study_id, request_id="next-over"))
    assert exhausted.value.code == "OPTIMIZER_BUDGET_EXHAUSTED"


def test_warm_start_inherits_observations(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    first = optimizer.submit(_command("warm-base"))
    parent_id = first["study_id"]
    _run_study_to_completion(round_factory, optimizer, parent_id)

    child = optimizer.submit(
        _command(
            "warm-child",
            max_candidates=2,
            max_evaluations=6,
            warm_start_study_id=parent_id,
        )
    )
    child_id = child["study_id"]
    with round_factory() as session:
        study = session.get(OptimizationStudyRow, child_id)
        assert study.warm_start_study_id == parent_id
    optimizer.start(child_id)
    with round_factory() as session:
        trials = session.scalars(
            select(OptimizationTrialRow)
            .where(OptimizationTrialRow.study_id == child_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()
    assert len(trials) == 2
    assert trials[0].is_baseline == 1
    assert trials[0].config_json == canonical_policy_json(RetrievalPolicyConfig())
    for trial in trials:
        assert trial.round_no == 2
    # Warm-start observations must actually change the candidate sequence:
    # a same-seed pure-random generation must produce a different sequence.
    from app.modules.agent_policy_optimizer.candidate_generation import generate_candidates

    random_candidates = generate_candidates(
        RetrievalPolicyConfig(), SPACE, max_candidates=2, seed=42
    )
    random_json = [canonical_policy_json(item.config) for item in random_candidates]
    warm_json = [trial.config_json for trial in trials]
    assert warm_json != random_json


def test_warm_start_missing_study_rejected(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    with pytest.raises(ServiceError) as missing:
        optimizer.submit(_command("warm-missing", warm_start_study_id="study-none"))
    assert missing.value.code == "OPTIMIZER_WARM_START_NOT_FOUND"


def test_category_stats_persisted_on_completion(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("category-study"))
    study_id = receipt["study_id"]
    trial_ids = _run_study_to_completion(round_factory, optimizer, study_id)
    with round_factory() as session:
        for trial_id in trial_ids:
            trial = session.get(OptimizationTrialRow, trial_id)
            assert trial.category_stats_json is not None
            payload = json.loads(trial.category_stats_json)
            assert set(payload["categories"]) == {
                "cancel_recovery", "cross_modal", "insufficient_evidence",
                "multi_hop", "prompt_injection", "single_hop", "version_conflict",
            }
            assert len(payload["cases"]) == 60


def test_category_comparison_preserves_exact_case_identity(round_factory) -> None:
    optimizer = _optimizer(round_factory)
    receipt = optimizer.submit(_command("category-case-identity", max_candidates=2, max_evaluations=2))
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with round_factory() as session:
        trial_ids = session.scalars(
            select(OptimizationTrialRow.id)
            .where(OptimizationTrialRow.study_id == study_id)
            .order_by(OptimizationTrialRow.ordinal)
        ).all()

    class CaseExecutor:
        def __init__(self, failed_case_id: str) -> None:
            self.failed_case_id = failed_case_id

        def run(self, _trial_id, snapshot):
            report = evaluation_report(failed_case_id=self.failed_case_id)
            report["provenance"]["retrieval_policy_sha256"] = snapshot.config_sha256
            report["metrics"]["latency_ms"] = {
                "quick_p50": 10.0,
                "quick_p95": 12.0,
                "agent_p50": 100.0,
                "agent_p95": 180.0,
            }
            return report

    optimizer.execute(_execute_command(trial_ids[0]), CaseExecutor("single_hop-01"))
    optimizer.execute(_execute_command(trial_ids[1]), CaseExecutor("single_hop-02"))
    comparison = optimizer.inspect_categories(study_id, trial_ids[1])
    single_hop = next(item for item in comparison["items"] if item["category"] == "single_hop")

    assert single_hop["wins"] == 1
    assert single_hop["losses"] == 1
    assert single_hop["ties"] == 10
    assert single_hop["verdict"] == "tied"
