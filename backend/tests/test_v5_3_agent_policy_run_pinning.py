from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, create_database_engine
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_evidence import AgentArtifact
from app.models.agent_policy import AgentPolicyVersion
from app.models.agent_run import AgentRun
from app.models.knowledge_space import KnowledgeSpace
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy.contracts import (
    ActivatePolicy,
    CreatePolicy,
    GetActivePolicy,
    GetPolicy,
)
from app.modules.agent_policy.service import SqlAgentPolicy
from app.modules.agent_control.report import REQUIRED_HARD_GATES
from app.modules.agent_control.contracts import GetRunTrace
from app.modules.agent_control.service import SqlAgentControl
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    ContinueRun,
    DeliverableSpec,
    GetRun,
    OpenRun,
    PermissionPolicy,
    RunMode,
    ScopeSelector,
)
from app.modules.evidence_agent.service import SqlEvidenceAgent


DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def run_policy_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'run-policy.db').as_posix()}")
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
        session.add(KnowledgeSpace(id=1, name="Policy runs", description="pinning"))
    try:
        yield factory
    finally:
        engine.dispose()


def _open(request_id: str) -> OpenRun:
    return OpenRun(
        request_id=request_id,
        space_id=1,
        goal="Explain the pinned policy",
        scope=ScopeSelector(),
        deliverable=DeliverableSpec(kind="answer", title="Pinned policy"),
        mode=RunMode.FORCE_AGENT,
        budget=BudgetLimits(),
        permissions=PermissionPolicy(),
        provider_mode="demo",
    )


def _activate_candidate(factory, policy: SqlAgentPolicy):
    candidate = policy.submit(
        CreatePolicy(
            request_id="create-pinned-candidate",
            label="Pinned candidate",
            base_policy_id=DEFAULT_POLICY_ID,
            config=replace(RetrievalPolicyConfig(), factual_top_k=12, neighbor_before=2),
        )
    )
    detail = policy.inspect(GetPolicy(candidate.policy_id))
    with factory.begin() as session:
        session.add(
            AgentEvaluation(
                id="evaluation-pinned-candidate",
                request_id="request-evaluation-pinned-candidate",
                request_payload_hash="a" * 64,
                label="Pinned candidate evaluation",
                mode="deterministic_recording",
                status="passed",
                policy_fingerprint=detail.config_sha256,
                policy_version_id=detail.id,
                policy_snapshot_json=canonical_policy_json(detail.config),
                schema_version=2,
                dataset_name="v5_fixed_evidence_cases",
                dataset_path="evaluation/v5/cases.jsonl",
                dataset_sha256="b" * 64,
                evaluator_sha256="c" * 64,
                report_sha256="d" * 64,
                case_count=60,
                case_pass_rate_millis=1000,
                external_provider_calls=0,
                failure_case_count=0,
                category_counts_json="{}",
                metrics_json="{}",
                hard_gates_json=json.dumps(
                    {gate: True for gate in sorted(REQUIRED_HARD_GATES)},
                    separators=(",", ":"),
                ),
                failure_case_ids_json="[]",
                report_json="{}",
                provider_boundary="not a real-model quality benchmark",
                attempt=1,
            )
        )
    policy.submit(
        ActivatePolicy(
            request_id="activate-pinned-candidate",
            policy_id=detail.id,
            expected_active_policy_id=DEFAULT_POLICY_ID,
            evaluation_id="evaluation-pinned-candidate",
        )
    )
    return detail


def test_new_runs_pin_active_policy_and_idempotent_replay_keeps_original_snapshot(
    run_policy_factory,
) -> None:
    policy = SqlAgentPolicy(run_policy_factory)
    agent = SqlEvidenceAgent(
        run_policy_factory,
        active_policy=lambda: policy.inspect(GetActivePolicy()),
    )

    before = agent.submit(_open("run-before-policy-change"))
    before_view = agent.inspect(GetRun(before.run_id))
    assert before_view.decision_policy.id == DEFAULT_POLICY_ID
    assert before_view.decision_policy.version == 1
    assert before_view.decision_policy.config_sha256 == policy_fingerprint(RetrievalPolicyConfig())

    candidate = _activate_candidate(run_policy_factory, policy)
    after = agent.submit(_open("run-after-policy-change"))
    after_view = agent.inspect(GetRun(after.run_id))
    assert after_view.decision_policy.id == candidate.id
    assert after_view.decision_policy.version == 2
    assert after_view.decision_policy.config_sha256 == candidate.config_sha256
    trace = SqlAgentControl(run_policy_factory).inspect(GetRunTrace(after.run_id))
    assert any(
        item.policy_id == candidate.id
        and item.version == "2"
        and item.source == "run_snapshot"
        and item.config_sha256 == candidate.config_sha256
        for item in trace.policies
    )

    replay = agent.submit(_open("run-before-policy-change"))
    assert replay.run_id == before.run_id
    assert replay.replayed is True
    assert agent.inspect(GetRun(replay.run_id)).decision_policy.id == DEFAULT_POLICY_ID


def test_continuation_inherits_parent_policy_after_active_policy_changes(run_policy_factory) -> None:
    policy = SqlAgentPolicy(run_policy_factory)
    agent = SqlEvidenceAgent(
        run_policy_factory,
        active_policy=lambda: policy.inspect(GetActivePolicy()),
    )
    parent = agent.submit(_open("parent-before-policy-change"))

    with run_policy_factory.begin() as session:
        run = session.get(AgentRun, parent.run_id)
        run.status = "insufficient_evidence"
        run.termination_reason = "requirements_uncovered"
        run.final_artifact_id = "gap-policy-parent"
        session.add(
            AgentArtifact(
                id="gap-policy-parent",
                producing_run_id=run.id,
                kind="evidence_gap_report",
                title="Evidence gaps",
                body_markdown="Missing evidence",
                structured_payload_json=json.dumps({"gaps": ["Find the missing policy evidence"]}),
                status="final",
                schema_version=1,
            )
        )

    _activate_candidate(run_policy_factory, policy)
    continued = agent.submit(
        ContinueRun(
            request_id="continue-parent-policy",
            source_run_id=parent.run_id,
            gap_artifact_id="gap-policy-parent",
            gap_ordinals=(1,),
        )
    )
    parent_view = agent.inspect(GetRun(parent.run_id))
    child_view = agent.inspect(GetRun(continued.run_id))
    assert policy.inspect(GetActivePolicy()).id != parent_view.decision_policy.id
    assert child_view.decision_policy == parent_view.decision_policy


def test_legacy_agent_without_policy_port_remains_readable(run_policy_factory) -> None:
    legacy_agent = SqlEvidenceAgent(run_policy_factory)
    opened = legacy_agent.submit(_open("legacy-policy-port"))
    assert legacy_agent.inspect(GetRun(opened.run_id)).decision_policy is None
