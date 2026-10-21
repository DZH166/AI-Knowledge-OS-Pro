from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationTrial as TrialRow
from app.models.optimizer import OptimizationStudy as StudyRow
from app.models.workbench import OptimizationStudyEvent
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy_optimizer.contracts import (
    ExportComparison,
    StudyCommand,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer
from app.modules.agent_policy_optimizer.templates import STUDY_TEMPLATES
from app.modules.agent_policy_optimizer.report_export import render_comparison_markdown
from app.modules.agent_control.contracts import GetRunTrace
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_run_share.contracts import CreateShareLink, GetSharedRunTrace, RevokeShareLink
from app.modules.agent_run_share.service import SqlAgentRunShare

from tests.test_v5_4a_optimizer_sql import (
    NOW,
    SPACE,
    WEIGHTS,
    _execute_command,
    _recording_executor,
    DEFAULT_POLICY_ID,
)


@pytest.fixture()
def workbench_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'workbench.db').as_posix()}")
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


def _completed_study(factory, optimizer, *, request_id: str = "wb-study-1") -> tuple[str, list[str]]:
    receipt = optimizer.submit(
        StudyCommand(
            request_id=request_id,
            label="Workbench study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=3,
            max_evaluations=6,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=42,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with factory() as session:
        trial_ids = session.scalars(
            select(TrialRow.id).where(TrialRow.study_id == study_id).order_by(TrialRow.ordinal)
        ).all()
    for trial_id in trial_ids:
        optimizer.execute(_execute_command(trial_id), _recording_executor())
    return study_id, list(trial_ids)


def test_overview_aggregates_rounds_trials_frontier_recommendation_actions(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    study_id, trial_ids = _completed_study(workbench_factory, optimizer)
    optimizer.inspect_recommendation(study_id)

    overview = optimizer.inspect_overview(study_id)
    assert overview["study"]["id"] == study_id
    assert overview["study"]["status"] == "completed"
    assert len(overview["trials"]) == 3
    assert [item["ordinal"] for item in overview["trials"]] == [1, 2, 3]
    assert all(item["metrics"] for item in overview["trials"])
    assert overview["frontier"], "completed study must have a frontier"
    assert all(item["trial_id"] in {t["id"] for t in overview["trials"]} for item in overview["frontier"])
    assert overview["recommendation"], "recommendation summary must exist after inspect_recommendation"
    assert all(item["rationale_first_line"] for item in overview["recommendation"])
    actions = {item["action"] for item in overview["actions"]}
    assert "next-round" in actions
    assert "start" not in actions
    assert "convert-draft" in actions


def test_overview_actions_reflect_pending_state(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    receipt = optimizer.submit(
        StudyCommand(
            request_id="wb-pending",
            label="Pending study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=4,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=1,
        )
    )
    overview = optimizer.inspect_overview(receipt["study_id"])
    actions = {item["action"] for item in overview["actions"]}
    assert "start" in actions
    assert "next-round" not in actions
    optimizer.start(receipt["study_id"])
    running_actions = {item["action"] for item in optimizer.inspect_overview(receipt["study_id"])["actions"]}
    assert "recover" in running_actions


def test_templates_catalog_and_from_template(workbench_factory) -> None:
    assert set(STUDY_TEMPLATES) == {"quality_first", "balanced", "cost_first"}
    for template in STUDY_TEMPLATES.values():
        assert template.objective in {"quality_first", "balanced", "cost_first"}
        assert template.max_candidates == 4
        assert template.max_evaluations == 8

    optimizer = _optimizer(workbench_factory)
    receipt = optimizer.create_from_template(
        request_id="tpl-1",
        label="From template",
        base_policy_id=DEFAULT_POLICY_ID,
        template_key="quality_first",
        seed=None,
        max_candidates=None,
        max_evaluations=None,
        warm_start_study_id=None,
    )
    study_id = receipt["study_id"]
    from app.models.optimizer import OptimizationStudy as OptimizationStudyRow

    with workbench_factory() as session:
        study = session.get(OptimizationStudyRow, study_id)
        assert study.objective == "quality_first"
        assert study.seed == 42
        assert json.loads(study.weights_json)["quality_weight_permille"] == 700

    replay = optimizer.create_from_template(
        request_id="tpl-1",
        label="From template",
        base_policy_id=DEFAULT_POLICY_ID,
        template_key="quality_first",
        seed=None,
        max_candidates=None,
        max_evaluations=None,
        warm_start_study_id=None,
    )
    assert replay["study_id"] == study_id
    assert replay["replayed"] is True


def test_from_template_rejects_unknown_template(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    with pytest.raises(ServiceError) as unknown:
        optimizer.create_from_template(
            request_id="tpl-x",
            label="Bad",
            base_policy_id=DEFAULT_POLICY_ID,
            template_key="nope",
            seed=None,
            max_candidates=None,
            max_evaluations=None,
            warm_start_study_id=None,
        )
    assert unknown.value.code == "OPTIMIZER_TEMPLATE_NOT_FOUND"
    with pytest.raises(ServiceError) as expanded:
        optimizer.create_from_template(
            request_id="tpl-expanded",
            label="Expanded",
            base_policy_id=DEFAULT_POLICY_ID,
            template_key="balanced",
            seed=None,
            max_candidates=5,
            max_evaluations=None,
            warm_start_study_id=None,
        )
    assert expanded.value.code == "OPTIMIZER_TEMPLATE_OVERRIDE_EXPANDS_BUDGET"


def test_events_record_lifecycle_in_order(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    study_id, trial_ids = _completed_study(workbench_factory, optimizer, request_id="wb-events")
    optimizer.inspect_recommendation(study_id)
    events = optimizer.inspect_events(study_id)
    types = [item["event_type"] for item in events["items"]]
    assert "study_created" in types
    assert "study_started" in types
    assert types.count("trial_created") == 3
    assert types.count("trial_completed") == 3
    assert "recommendation_updated" in types
    assert "study_completed" in types
    created_at = [item["created_at"] for item in events["items"]]
    assert created_at == sorted(created_at)


def test_events_redact_secret_reasons(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    receipt = optimizer.submit(
        StudyCommand(
            request_id="wb-reason",
            label="Reason study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=4,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=3,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    from app.modules.agent_policy_optimizer.contracts import FailStudy

    optimizer.fail_study(FailStudy(study_id=study_id, reason="password=hunter2hunter2"))
    events = optimizer.inspect_events(study_id)
    rendered = json.dumps(events)
    assert "hunter2hunter2" not in rendered
    assert "[redacted]" in rendered or "password" not in rendered
    types = [item["event_type"] for item in events["items"]]
    assert "study_failed" in types
    assert types.count("trial_cancelled") == 2


def test_event_cursor_uses_timestamp_then_id_without_skipping(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    receipt = optimizer.submit(
        StudyCommand(
            request_id="wb-cursor",
            label="Cursor study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=1,
            max_evaluations=1,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=1,
        )
    )
    study_id = receipt["study_id"]
    with workbench_factory.begin() as session:
        study = session.get(StudyRow, study_id)
        session.add_all(
            [
                OptimizationStudyEvent(
                    id="f" * 36,
                    study_id=study_id,
                    event_type="round_started",
                    round_no=study.round_no,
                    payload_json="{}",
                    created_at=NOW + timedelta(seconds=1),
                ),
                OptimizationStudyEvent(
                    id="a" * 36,
                    study_id=study_id,
                    event_type="recommendation_updated",
                    round_no=study.round_no,
                    payload_json="{}",
                    created_at=NOW + timedelta(seconds=2),
                ),
            ]
        )

    page = optimizer.inspect_events(study_id, after="f" * 36)

    assert [item["id"] for item in page["items"]] == ["a" * 36]


def test_export_comparison_is_deterministic_and_complete(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    study_id, trial_ids = _completed_study(workbench_factory, optimizer, request_id="wb-export")
    export = optimizer.export_comparison(
        ExportComparison(study_id=study_id, trial_ids=tuple(trial_ids[:2]), include_categories=True)
    )
    from hashlib import sha256

    assert export["sha256"] == sha256(export["markdown"].encode("utf-8")).hexdigest()
    markdown = export["markdown"]
    assert "# Retrieval optimizer comparison report" in markdown
    assert "case_pass_rate" in markdown
    assert "delta vs trial 1" in markdown
    assert "Hard gates" in markdown
    assert "Gate changes" in markdown
    assert "New failures" in markdown
    assert "Resolved failures" in markdown
    assert "## Categories" in markdown  # include_categories=True
    assert "wins" in markdown and "ties" in markdown and "losses" in markdown
    replay = optimizer.export_comparison(
        ExportComparison(study_id=study_id, trial_ids=tuple(trial_ids[:2]), include_categories=True)
    )
    assert replay["markdown"] == export["markdown"]


def test_export_rejects_wrong_trial_counts(workbench_factory) -> None:
    optimizer = _optimizer(workbench_factory)
    study_id, trial_ids = _completed_study(workbench_factory, optimizer, request_id="wb-export-2")
    with pytest.raises(ServiceError) as too_few:
        optimizer.export_comparison(
            ExportComparison(study_id=study_id, trial_ids=(trial_ids[0],), include_categories=False)
        )
    assert too_few.value.code == "OPTIMIZER_EXPORT_TRIALS_INVALID"
    with pytest.raises(ServiceError) as too_many:
        optimizer.export_comparison(
            ExportComparison(
                study_id=study_id,
                trial_ids=tuple(trial_ids[:2]) + ("trial-fake", "trial-fake2", "trial-fake3"),
                include_categories=False,
            )
        )
    assert too_many.value.code == "OPTIMIZER_EXPORT_TRIALS_INVALID"


def test_export_markdown_pure_function_deterministic() -> None:

    columns = ("trial A", "trial B")
    metric_rows = [
        {
            "metric": "case_pass_rate",
            "direction": "higher",
            "values": (1.0, 0.9),
            "deltas": (-0.1,),
            "best": "trial A",
        },
    ]
    gate_rows = [
        {"gate": "all_cases_pass", "values": (True, False), "changed": True},
    ]
    category_rows = [
        {
            "category": "multi_hop",
            "pass_rates": (1.0, 0.5),
            "wins": 0,
            "ties": 6,
            "losses": 6,
            "verdict": "regressed",
        }
    ]
    failure_rows = [
        {"trial": "trial B", "failed_case_ids": ("multi_hop-01",)},
    ]
    first = render_comparison_markdown(
        title="Comparison",
        columns=columns,
        metric_rows=metric_rows,
        gate_rows=gate_rows,
        category_rows=category_rows,
        failure_rows=failure_rows,
    )
    second = render_comparison_markdown(
        title="Comparison",
        columns=columns,
        metric_rows=metric_rows,
        gate_rows=gate_rows,
        category_rows=category_rows,
        failure_rows=failure_rows,
    )
    assert first == second
    assert "\r\n" not in first
    for needle in ("multi_hop-01", "case_pass_rate", "all_cases_pass", "regressed"):
        assert needle in first


def _agent_run(factory, run_id: str) -> None:
    from app.models.agent_run import AgentRun
    from app.models.knowledge_space import KnowledgeSpace

    with factory.begin() as session:
        session.add(KnowledgeSpace(id=99, name="Workbench", description="share tests"))
    with factory.begin() as session:
        session.add(
            AgentRun(
                space_id=99,
                id=run_id,
                scope_snapshot_json="{}",
                scope_digest="d" * 64,
                deliverable_json="{}",
                trace_id=f"trace-{run_id}",
                goal="Workbench share test",
                requested_mode="force_quick",
                status="completed",
                phase="done",
                provider_mode="demo",
                version=1,
                execution_epoch=0,
                active_elapsed_ms=0,
                budget_limits_json="{}",
                budget_usage_json="{}",
            )
        )


def test_share_link_lifecycle(workbench_factory, tmp_path: Path) -> None:
    _agent_run(workbench_factory, "run-share-1")
    share = SqlAgentRunShare(
        workbench_factory,
        clock=lambda: NOW,
        token_factory=lambda: "a" * 64,
        trace_reader=lambda run_id: SqlAgentControl(workbench_factory).inspect(GetRunTrace(run_id)),
    )
    receipt = share.submit(CreateShareLink(run_id="run-share-1", expires_in_days=7))
    assert len(receipt.token) == 64
    trace = share.inspect(GetSharedRunTrace(token="a" * 64, now=NOW + timedelta(days=1)))
    assert trace.run_id == "run-share-1"
    share.submit(RevokeShareLink(token="a" * 64))
    with pytest.raises(ServiceError) as revoked:
        share.inspect(GetSharedRunTrace(token="a" * 64, now=NOW + timedelta(days=1)))
    assert revoked.value.status_code == 404
    with pytest.raises(ServiceError) as missing:
        share.inspect(GetSharedRunTrace(token="b" * 64, now=NOW))
    assert missing.value.status_code == 404


def test_share_link_expires(workbench_factory) -> None:
    _agent_run(workbench_factory, "run-share-2")
    share = SqlAgentRunShare(
        workbench_factory,
        clock=lambda: NOW,
        token_factory=lambda: "c" * 64,
        trace_reader=lambda run_id: SqlAgentControl(workbench_factory).inspect(GetRunTrace(run_id)),
    )
    share.submit(CreateShareLink(run_id="run-share-2", expires_in_days=1))
    with pytest.raises(ServiceError) as expired:
        share.inspect(GetSharedRunTrace(token="c" * 64, now=NOW + timedelta(days=2)))
    assert expired.value.status_code == 404
