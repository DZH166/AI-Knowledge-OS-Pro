from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
import json
from threading import Barrier

import pytest
from sqlalchemy import select

from app.core.errors import ServiceError
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationStudy, OptimizationTrial
from app.modules.agent_policy_optimizer.contracts import (
    ConvertRecommendation, ExecuteTrial, NextRound, RecoverOptimizations, StudyCommand,
)
from tests.test_v5_4a_optimizer_sql import (
    NOW, _command, _optimizer, _recording_executor,
)
from tests import test_v5_4a_optimizer_sql as fixtures

optimizer_factory = fixtures.optimizer_factory


def create(optimizer, request_id, **overrides):
    return optimizer.submit(StudyCommand(**{**_command(request_id), **overrides}))["study_id"]


def finish(optimizer, factory, study_id):
    with factory() as session:
        ids = session.scalars(select(OptimizationTrial.id).where(
            OptimizationTrial.study_id == study_id, OptimizationTrial.status == "pending"
        ).order_by(OptimizationTrial.ordinal)).all()
    for index, trial_id in enumerate(ids):
        optimizer.execute(ExecuteTrial(trial_id, "worker"), _recording_executor(agent_p95=300.0-index*80))
    return ids


def test_recovery_and_execution_share_a_hard_evaluation_budget(optimizer_factory):
    optimizer = _optimizer(optimizer_factory, lease_seconds=5)
    study_id = create(optimizer, "budget", max_candidates=1, max_evaluations=1)
    optimizer.start(study_id)
    trial_id = optimizer.list_trials(study_id, limit=10)["items"][0]["id"]

    class InterruptedExecutor:
        def run(self, *_):
            raise KeyboardInterrupt("simulate process termination before writeback")

    with pytest.raises(KeyboardInterrupt):
        optimizer.execute(ExecuteTrial(trial_id, "same-worker"), InterruptedExecutor())
    assert optimizer.recover(RecoverOptimizations(NOW + timedelta(seconds=10))) == 0
    executor = _recording_executor()
    optimizer.execute(ExecuteTrial(trial_id, "same-worker"), executor)
    assert executor.calls == []
    assert optimizer.inspect_study(study_id)["budget_usage"]["started_evaluations"] == 1
    assert optimizer.inspect_study(study_id)["status"] != "running"


def test_deadline_stops_pending_work_without_premature_completion(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "deadline-after-start", deadline_at=NOW+timedelta(seconds=1))
    optimizer.start(study_id)
    from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer
    optimizer = SqlAgentPolicyOptimizer(optimizer_factory, clock=lambda: NOW+timedelta(seconds=2))
    trial_id = optimizer.list_trials(study_id, limit=10)["items"][0]["id"]
    executor = _recording_executor()
    optimizer.execute(ExecuteTrial(trial_id, "worker"), executor)
    assert executor.calls == []
    assert all(item["status"] == "cancelled" for item in optimizer.list_trials(study_id, limit=10)["items"])


def test_concurrent_start_and_next_round_have_one_writer(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "concurrent", max_candidates=9, max_evaluations=9)
    barrier = Barrier(2)

    def start(_):
        barrier.wait()
        return optimizer.start(study_id)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(start, range(2)))
    assert sum(item["created"] for item in results) == 3
    finish(optimizer, optimizer_factory, study_id)
    barrier = Barrier(2)

    def next_round(index):
        barrier.wait()
        try:
            return optimizer.start_next_round(NextRound(study_id, f"round-{index}"))
        except ServiceError as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(next_round, range(2)))
    assert sum(isinstance(item, dict) for item in results) == 1
    trials = optimizer.list_trials(study_id, limit=100)["items"]
    assert len(trials) == 6
    assert len({item["config_sha256"] for item in trials}) == 6


def test_warm_start_is_frozen_when_child_is_created(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    parent = create(optimizer, "parent", max_candidates=9, max_evaluations=9)
    optimizer.start(parent)
    finish(optimizer, optimizer_factory, parent)
    child_a = create(optimizer, "child-a", warm_start_study_id=parent)
    child_b = create(optimizer, "child-b", warm_start_study_id=parent)
    optimizer.start(child_a)
    optimizer.start_next_round(NextRound(parent, "parent-next"))
    finish(optimizer, optimizer_factory, parent)
    optimizer.start(child_b)
    def fingerprints(study):
        return [item["config_sha256"] for item in optimizer.list_trials(study, limit=100)["items"]]
    assert fingerprints(child_a) == fingerprints(child_b)


def test_two_conversions_commit_exactly_one_policy_and_event(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "conversion")
    optimizer.start(study_id)
    finish(optimizer, optimizer_factory, study_id)
    trial_id = optimizer.inspect_recommendation(study_id)["candidates"][0]["trial_id"]
    barrier = Barrier(2)

    def convert(index):
        barrier.wait()
        return optimizer.convert_to_draft(ConvertRecommendation(study_id, trial_id, f"convert-{index}"))

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(convert, range(2)))
    assert len({item["policy_id"] for item in results}) == 1
    assert sorted(item["replayed"] for item in results) == [False, True]
    with optimizer_factory() as session:
        assert len(session.scalars(select(AgentPolicyVersion).where(AgentPolicyVersion.status == "draft")).all()) == 1
    assert sum(event["event_type"] == "draft_converted" for event in optimizer.inspect_events(study_id)["items"]) == 1


def test_incomplete_gates_never_enter_the_frontier(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "incomplete-gates")
    optimizer.start(study_id)
    ids = finish(optimizer, optimizer_factory, study_id)
    from app.models.agent_evaluation import AgentEvaluation

    with optimizer_factory.begin() as session:
        trial = session.get(OptimizationTrial, ids[0])
        session.get(AgentEvaluation, trial.evaluation_id).hard_gates_json = json.dumps({"all_cases_pass": True})
    assert ids[0] not in {item["trial_id"] for item in optimizer.inspect_pareto(study_id)["items"]}


def test_workbench_hides_cached_recommendations_after_baseline_report_corruption(optimizer_factory):
    from app.models.agent_evaluation import AgentEvaluation

    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "stale-overview")
    optimizer.start(study_id)
    finish(optimizer, optimizer_factory, study_id)
    assert optimizer.inspect_recommendation(study_id)["candidates"]
    assert optimizer.inspect_overview(study_id)["recommendation"]

    with optimizer_factory.begin() as session:
        baseline = session.scalar(
            select(OptimizationTrial).where(
                OptimizationTrial.study_id == study_id,
                OptimizationTrial.ordinal == 1,
            )
        )
        assert baseline is not None
        session.get(AgentEvaluation, baseline.evaluation_id).report_json = "{}"

    assert optimizer.inspect_recommendation(study_id)["candidates"] == []
    overview = optimizer.inspect_overview(study_id)
    assert overview["recommendation"] == []
    assert not any(item["action"] == "convert-draft" for item in overview["actions"])
    assert all(item["recommendation_rank"] is None for item in overview["trials"])


def test_retry_action_is_unavailable_when_budget_is_exhausted(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "retry-budget", max_candidates=2, max_evaluations=2)
    optimizer.start(study_id)
    with optimizer_factory.begin() as session:
        study = session.get(OptimizationStudy, study_id)
        study.budget_usage_json = '{"created_trials":2,"started_evaluations":2}'
        trials = session.scalars(select(OptimizationTrial).where(OptimizationTrial.study_id == study_id)).all()
        trials[0].status = "failed"
        trials[1].status = "running"
    actions = optimizer.inspect_overview(study_id)["actions"]
    assert not next(item for item in actions if item["action"] == "retry")["available"]


@pytest.mark.parametrize("contradiction", ["case", "citation", "latency"])
def test_report_validation_rejects_contradictory_success(contradiction):
    from app.modules.agent_control.report import EvaluationReportError, validate_evaluation_report
    from tests.test_v5_2_agent_control_sql import evaluation_report

    report = evaluation_report()
    if contradiction == "case":
        report["cases"][0]["actual_status"] = "failed"
    elif contradiction == "citation":
        report["metrics"]["citation_completeness"] = 0.0
    else:
        report["cases"][0]["latency_ms"] = -1.0
    with pytest.raises(EvaluationReportError):
        validate_evaluation_report(report)


def test_offset_deadlines_and_legacy_sqlite_rows_use_the_same_instant(optimizer_factory):
    optimizer = _optimizer(optimizer_factory)
    deadline = (NOW-timedelta(hours=1)).astimezone(timezone(timedelta(hours=8)))
    command = StudyCommand(**{**_command("offset-deadline"), "deadline_at": deadline})
    receipt = optimizer.submit(command)
    assert optimizer.submit(command)["replayed"]
    with optimizer_factory.begin() as session:
        study = session.get(OptimizationStudy, receipt["study_id"])
        # Actual old SQLite representation: wall time lost tz, budget JSON did not.
        study.deadline_at = deadline.replace(tzinfo=None)
        budget = json.loads(study.budget_json)
        budget["deadline_at"] = deadline.isoformat()
        study.budget_json = json.dumps(budget)
    assert optimizer.submit(command)["replayed"]
    assert optimizer.start(receipt["study_id"])["created"] == 0
    assert optimizer.inspect_study(receipt["study_id"])["status"] == "completed"


def test_legacy_category_aggregates_recover_exact_report_facts(optimizer_factory):
    from app.schemas.optimizer_schema import TrialReceiptSchema

    optimizer = _optimizer(optimizer_factory)
    study_id = create(optimizer, "legacy-category")
    optimizer.start(study_id)
    ids = finish(optimizer, optimizer_factory, study_id)
    expected = optimizer.inspect_recommendation(study_id)
    with optimizer_factory.begin() as session:
        for trial in session.scalars(select(OptimizationTrial).where(OptimizationTrial.study_id == study_id)):
            trial.category_stats_json = json.dumps(json.loads(trial.category_stats_json)["categories"])
    result = TrialReceiptSchema(**optimizer.inspect_trial(ids[0]))
    assert len(result.category_stats.cases) == 60
    assert len(optimizer.inspect_categories(study_id, ids[1])["items"]) == 7
    assert optimizer.inspect_recommendation(study_id) == expected
