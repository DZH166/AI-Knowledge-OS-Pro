from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.core.errors import ServiceError
from app.db.session import Base
from app.models.agent_run import AgentGate, AgentRun
from app.models.knowledge_space import KnowledgeSpace
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    DeliverableSpec,
    OpenRun,
    PermissionPolicy,
    RunMode,
    RunStatus,
    ScopeSelector,
    SignalKind,
    SignalRun,
)
from app.modules.evidence_agent.service import SqlEvidenceAgent


@pytest.fixture()
def human_loop_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="human loop"))
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _open(agent: SqlEvidenceAgent):
    return agent.submit(
        OpenRun(
            request_id="open-human-loop",
            space_id=1,
            goal="需要扩大证据范围",
            scope=ScopeSelector(),
            deliverable=DeliverableSpec(),
            mode=RunMode.FORCE_AGENT,
            budget=BudgetLimits(),
            permissions=PermissionPolicy(read_only=True),
            provider_mode="recording",
        )
    )


def test_approval_is_single_use_and_bound_to_exact_proposal_digest(human_loop_factory) -> None:
    agent = SqlEvidenceAgent(human_loop_factory)
    opened = _open(agent)
    with human_loop_factory.begin() as session:
        run = session.get(AgentRun, opened.run_id)
        assert run is not None
        gate = AgentGate(
            id="gate-exact",
            run_id=run.id,
            kind="scope_approval",
            status="open",
            prompt="允许把检索范围扩大到全部当前来源吗？",
            response_schema_json='{"type":"boolean"}',
            arguments_digest="a" * 64,
            policy_reason="scope_expansion",
        )
        session.add(gate)
        run.status = RunStatus.AWAITING_APPROVAL.value
        run.pending_gate_id = gate.id

    with pytest.raises(ServiceError) as stale:
        agent.submit(
            SignalRun(
                request_id="approve-wrong-digest",
                run_id=opened.run_id,
                expected_version=1,
                signal=SignalKind.APPROVE,
                proposal_digest="b" * 64,
            )
        )
    assert stale.value.code == "STALE_APPROVAL"

    approved = agent.submit(
        SignalRun(
            request_id="approve-exact-digest",
            run_id=opened.run_id,
            expected_version=1,
            signal=SignalKind.APPROVE,
            proposal_digest="a" * 64,
        )
    )
    replay = agent.submit(
        SignalRun(
            request_id="approve-exact-digest",
            run_id=opened.run_id,
            expected_version=1,
            signal=SignalKind.APPROVE,
            proposal_digest="a" * 64,
        )
    )

    assert approved.status is RunStatus.QUEUED
    assert replay.replayed is True
    with human_loop_factory() as session:
        run = session.get(AgentRun, opened.run_id)
        gate = session.get(AgentGate, "gate-exact")
        assert run is not None and gate is not None
        assert run.pending_gate_id is None
        assert gate.status == "approved"
        assert gate.resolved_at is not None


def test_cancelling_a_waiting_run_closes_its_open_gate(human_loop_factory) -> None:
    agent = SqlEvidenceAgent(human_loop_factory)
    opened = _open(agent)
    with human_loop_factory.begin() as session:
        run = session.get(AgentRun, opened.run_id)
        assert run is not None
        gate = AgentGate(
            id="gate-cancel",
            run_id=run.id,
            kind="clarification",
            status="open",
            prompt="补充需要核验的时间范围。",
            response_schema_json='{"type":"string"}',
            policy_reason="ambiguous_scope",
        )
        session.add(gate)
        run.status = RunStatus.AWAITING_INPUT.value
        run.pending_gate_id = gate.id

    cancelled = agent.submit(
        SignalRun(
            request_id="cancel-waiting-run",
            run_id=opened.run_id,
            expected_version=1,
            signal=SignalKind.CANCEL,
        )
    )

    assert cancelled.status is RunStatus.CANCELLED
    with human_loop_factory() as session:
        run = session.get(AgentRun, opened.run_id)
        gate = session.get(AgentGate, "gate-cancel")
        assert run is not None and gate is not None
        assert run.pending_gate_id is None
        assert gate.status == "cancelled"
        assert gate.resolved_at is not None
