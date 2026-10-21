from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from threading import Event, Thread
from typing import Callable

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ServiceError
from app.db.session import Base
from app.models.agent_evidence import AgentArtifact, AgentEvidence, RequirementEvidence
from app.models.agent_run import (
    AgentGate,
    AgentModelCall,
    AgentPlan,
    AgentRequirement,
    AgentRun,
    AgentToolCall,
)
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import MultimodalChunk, Source
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    DeliverableSpec,
    GetArtifact,
    GetEvidence,
    GetRun,
    OpenRun,
    PermissionPolicy,
    RunMode,
    RunStatus,
    ScopeSelector,
    SignalKind,
    SignalRun,
)
from app.modules.evidence_agent.budget import BudgetController, BudgetExceeded, BudgetUsage
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_index import EvidenceHit, EvidenceSearchResult, PinnedEvidenceRef
from app.modules.evidence_index import (
    ActivateRevision,
    ChunkDraft,
    GetRevision,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    VerifiedPoint,
)
from app.services.agent_model import (
    AgentModelResult,
    AgentModelUsage,
    AssessModelInput,
    ClaimProposal,
    PlanDecision,
    PlanModelInput,
    RecordingAgentModel,
    RequirementProposal,
    RouteDecision,
    SufficiencyDecision,
    SynthesisDecision,
    StructuredAgentModel,
)
from app.services.llm_service import LLMService
from app.services.providers import LLMProvider, LLMResult


class _RecordingProvider(LLMProvider):
    name = "recording"

    def __init__(self, responses: list[LLMResult]) -> None:
        self.responses = list(responses)
        self.calls = 0

    @property
    def model(self) -> str:
        return "recording-structured-v1"

    def is_configured(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.generate(system_prompt=system_prompt, user_prompt=user_prompt).text

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        self.calls += 1
        return self.responses.pop(0)


class _SelectingAgentModel(RecordingAgentModel):
    def __init__(
        self,
        *,
        plans: tuple[AgentModelResult[PlanDecision], ...],
        syntheses: tuple[AgentModelResult[SynthesisDecision], ...] = (),
        select: Callable[[AssessModelInput], list[dict[str, object]]],
    ) -> None:
        super().__init__(plans=plans, syntheses=syntheses)
        self._select = select

    def assess(
        self,
        request: AssessModelInput,
        *,
        allow_repair: bool = True,
    ) -> AgentModelResult[SufficiencyDecision]:
        del allow_repair
        self._record("assess", request)
        return AgentModelResult(
            value=SufficiencyDecision(
                decision="answer",
                reason="selected claim-level support from the supplied candidates",
                evidence_selections=self._select(request),
            ),
            usage=AgentModelUsage(input_tokens=10, output_tokens=4),
            provider="recording",
            model="recording-agent-v1",
        )


def _result(text: str, *, input_tokens: int, output_tokens: int) -> LLMResult:
    return LLMResult(
        text=text,
        provider="recording",
        model="recording-structured-v1",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=4,
        cost_micros=9,
        estimated_usage=False,
    )


def test_structured_agent_model_validates_and_repairs_a_plan_at_most_once() -> None:
    provider = _RecordingProvider(
        [
            _result(
                '{"requirements":[{"text":"比较成本"}],"scope":{"revision_ids":[999]},'
                '"budget":{"max_steps":999}}',
                input_tokens=11,
                output_tokens=2,
            ),
            _result(
                '{"requirements":[{"text":"比较成本","kind":"factual","priority":"must"},'
                '{"text":"比较延迟","kind":"factual","priority":"must"}],"rationale":"two axes"}',
                input_tokens=13,
                output_tokens=17,
            ),
        ]
    )
    model = StructuredAgentModel(LLMService(provider))

    generated = model.plan(PlanModelInput(goal="比较两个方案", max_requirements=4))

    assert [item.text for item in generated.value.requirements] == ["比较成本", "比较延迟"]
    assert generated.usage.input_tokens == 24
    assert generated.usage.output_tokens == 19
    assert generated.usage.repair_attempts == 1
    assert provider.calls == 2


def test_sufficiency_clarification_requires_a_bounded_question_and_target() -> None:
    with pytest.raises(ValidationError):
        SufficiencyDecision(
            decision="request_clarification",
            reason="missing target",
            clarification_question="Which period?",
        )
    with pytest.raises(ValidationError):
        SufficiencyDecision(
            decision="request_clarification",
            reason="question too long",
            target_requirement_ordinal=1,
            clarification_question="x" * 501,
        )


def test_sufficiency_support_selection_is_answer_only_and_unique() -> None:
    selection = {
        "requirement_ordinal": 1,
        "supporting_evidence_ids": ["evidence-1"],
    }
    with pytest.raises(ValidationError):
        SufficiencyDecision(
            decision="insufficient_evidence",
            reason="cannot promote evidence",
            evidence_selections=[selection],
        )
    with pytest.raises(ValidationError):
        SufficiencyDecision(
            decision="answer",
            reason="duplicate requirement",
            evidence_selections=[selection, selection],
        )
    with pytest.raises(ValidationError):
        SufficiencyDecision(
            decision="answer",
            reason="duplicate evidence",
            evidence_selections=[
                {
                    "requirement_ordinal": 1,
                    "supporting_evidence_ids": ["evidence-1", "evidence-1"],
                }
            ],
        )


@pytest.fixture()
def agent_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Agent model", description="test"))
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _open(
    *,
    request_id: str,
    mode: RunMode,
    goal: str = "精确事实",
    budget: BudgetLimits | None = None,
    permissions: PermissionPolicy | None = None,
) -> OpenRun:
    return OpenRun(
        request_id=request_id,
        space_id=1,
        goal=goal,
        scope=ScopeSelector(),
        deliverable=DeliverableSpec(kind="answer"),
        mode=mode,
        budget=budget or BudgetLimits(max_steps=8, max_tool_calls=4, max_model_calls=4),
        permissions=permissions or PermissionPolicy(read_only=True),
        provider_mode="recording",
    )


def _drain(agent: SqlEvidenceAgent, runner: AgentRunner, run_id: str):
    terminal = {
        RunStatus.COMPLETED,
        RunStatus.INSUFFICIENT_EVIDENCE,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    }
    for _ in range(20):
        view = agent.inspect(GetRun(run_id))
        if view.status in terminal:
            return view
        result = runner.advance_one(
            run_id,
            expected_version=view.version,
            execution_epoch=view.execution_epoch,
        )
        assert result.applied is True
    raise AssertionError("Run did not reach a terminal state.")


async def _public_frames(agent: SqlEvidenceAgent, run_id: str):
    return [frame async for frame in agent.follow(run_id, cursor=0)]


async def _public_frames_until(agent: SqlEvidenceAgent, run_id: str, event_type: str):
    frames = []
    async for frame in agent.follow(run_id, cursor=0):
        frames.append(frame)
        if frame.event_type == event_type:
            return frames
    raise AssertionError(f"Run ended before public event {event_type!r} was observed.")


def _index_source(agent_session_factory, *, title: str, content: str) -> None:
    with agent_session_factory() as session:
        source = Source(
            space_id=1,
            source_type="document",
            title=title,
            file_size=len(content),
            status="uploaded",
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        evidence_index = SqlEvidenceIndex(session)
        staged = evidence_index.command(
            StageRevision(
                command_id=f"stage-model-{title}",
                draft=RevisionDraft(
                    source_id=source.id,
                    content_hash=sha256(content.encode()).hexdigest(),
                    index_version="v5-agent-model-test",
                    collection_name="v5-agent-model-test",
                    chunks=(
                        ChunkDraft(
                            chunk_index=0,
                            modality="text",
                            content=content,
                            locator={"kind": "text", "heading": title},
                        ),
                    ),
                ),
            )
        )
        revision = evidence_index.query(GetRevision(staged.revision_id))
        evidence_index.command(
            ActivateRevision(
                command_id=f"activate-model-{title}",
                revision_id=staged.revision_id,
                verified_points=tuple(
                    VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                    for point in revision.points
                ),
            )
        )


def _search(agent_session_factory):
    def search(request):
        with agent_session_factory() as session:
            return SqlEvidenceIndex(session).search(request)

    return search


def _hit_for_source(agent_session_factory, *, title: str, score: float = 0.95) -> EvidenceHit:
    with agent_session_factory() as session:
        source = session.scalar(select(Source).where(Source.title == title))
        assert source is not None
        chunk = session.scalar(
            select(MultimodalChunk).where(
                MultimodalChunk.source_id == source.id,
                MultimodalChunk.revision_id == source.active_revision_id,
            )
        )
        assert chunk is not None
        return EvidenceHit(
            evidence=PinnedEvidenceRef(
                source_id=source.id,
                revision_id=int(source.active_revision_id),
                index_revision_id=int(source.active_index_revision_id),
                chunk_id=chunk.id,
                source_type=source.source_type,
                modality=chunk.modality,
                content_hash=chunk.content_hash,
                locator={"kind": "document_chunk", "chunk_index": chunk.chunk_index},
                excerpt=chunk.content_text,
                currently_active=True,
            ),
            score=score,
        )


def test_force_quick_keeps_zero_model_and_planner_calls(agent_session_factory) -> None:
    model = RecordingAgentModel()
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(_open(request_id="quick-zero-model", mode=RunMode.FORCE_QUICK))

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.budget_usage["model_calls"] == 0
    assert model.calls == []


def test_force_agent_uses_a_typed_model_plan_and_accounts_its_budget(
    agent_session_factory,
) -> None:
    plan_result = AgentModelResult(
        value=PlanDecision(
            requirements=[
                RequirementProposal(text="核对 alpha 成本", kind="factual", priority="must"),
                RequirementProposal(text="核对 beta 延迟", kind="comparative", priority="must"),
            ],
            rationale="separate evidence axes",
        ),
        usage=AgentModelUsage(
            input_tokens=21,
            output_tokens=12,
            cost_micros=17,
            latency_ms=5,
        ),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan_result,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="typed-model-plan",
            mode=RunMode.FORCE_AGENT,
            goal="比较 alpha 与 beta",
        )
    )
    opened_view = agent.inspect(GetRun(opened.run_id))
    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )

    planned = runner.advance_one(
        opened.run_id,
        expected_version=dispatched.version,
        execution_epoch=0,
    )
    view = agent.inspect(GetRun(opened.run_id))

    assert planned.status is RunStatus.PLANNED
    assert view.budget_usage["model_calls"] == 1
    assert view.budget_usage["model_input_tokens"] == 21
    assert view.budget_usage["model_output_tokens"] == 12
    assert view.budget_usage["cost_micros"] == 17
    assert view.scope_snapshot == opened_view.scope_snapshot
    assert view.budget_limits == opened_view.budget_limits
    assert [call.operation for call in model.calls] == ["plan"]
    with agent_session_factory() as session:
        plan = session.scalar(select(AgentPlan).where(AgentPlan.run_id == opened.run_id))
        requirements = session.scalars(
            select(AgentRequirement)
            .where(AgentRequirement.run_id == opened.run_id)
            .order_by(AgentRequirement.ordinal)
        ).all()
        model_call = session.scalar(
            select(AgentModelCall).where(AgentModelCall.run_id == opened.run_id)
        )
        run = session.get(AgentRun, opened.run_id)
        assert plan is not None and plan.created_by == "model"
        assert plan.strategy == "structured_model_plan"
        assert [item.text for item in requirements] == ["核对 alpha 成本", "核对 beta 延迟"]
        assert model_call is not None and model_call.status == "completed"
        assert run is not None and run.policy_snapshot_json == '{"allow_scope_expansion":false,"read_only":true}'


def test_auto_mode_uses_model_routing_but_a_quick_decision_never_calls_planner(
    agent_session_factory,
) -> None:
    route_result = AgentModelResult(
        value=RouteDecision(mode="force_quick", rationale="one directly answerable fact"),
        usage=AgentModelUsage(input_tokens=8, output_tokens=4, cost_micros=3, latency_ms=2),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(routes=(route_result,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="auto-model-route",
            mode=RunMode.AUTO,
            goal="比较字样存在，但只需核对一个直接事实",
        )
    )
    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )

    selected = runner.advance_one(
        opened.run_id,
        expected_version=dispatched.version,
        execution_epoch=0,
    )
    view = agent.inspect(GetRun(opened.run_id))

    assert selected.reason == "quick_selected"
    assert view.effective_mode is RunMode.FORCE_QUICK
    assert [call.operation for call in model.calls] == ["route"]
    assert view.budget_usage["model_calls"] == 1


def test_agent_model_is_invoked_only_after_the_sql_transaction_closes(
    agent_session_factory,
) -> None:
    active_transactions: set[int] = set()

    def after_begin(_session, transaction, _connection) -> None:
        active_transactions.add(id(transaction))

    def after_end(_session, transaction) -> None:
        active_transactions.discard(id(transaction))

    event.listen(agent_session_factory.class_, "after_begin", after_begin)
    event.listen(agent_session_factory.class_, "after_transaction_end", after_end)
    observed: list[int] = []
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="transaction-free model call")],
            rationale="probe",
        ),
        usage=AgentModelUsage(input_tokens=3, output_tokens=2),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(
        plans=(plan,),
        on_call=lambda _call: observed.append(len(active_transactions)),
    )
    try:
        agent = SqlEvidenceAgent(agent_session_factory)
        runner = AgentRunner(
            agent_session_factory,
            lambda _request: EvidenceSearchResult(hits=()),
            agent_model=model,
        )
        opened = agent.submit(
            _open(request_id="transaction-free-model", mode=RunMode.FORCE_AGENT)
        )
        dispatched = runner.advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )

        runner.advance_one(
            opened.run_id,
            expected_version=dispatched.version,
            execution_epoch=0,
        )
    finally:
        event.remove(agent_session_factory.class_, "after_begin", after_begin)
        event.remove(agent_session_factory.class_, "after_transaction_end", after_end)

    assert observed == [0]


def test_cancel_during_model_call_discards_the_returned_plan(agent_session_factory) -> None:
    entered = Event()
    release = Event()
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="late plan")],
            rationale="must be fenced",
        ),
        usage=AgentModelUsage(input_tokens=3, output_tokens=2),
        provider="recording",
        model="recording-agent-v1",
    )

    def block_model(_call) -> None:
        entered.set()
        assert release.wait(timeout=5)

    model = RecordingAgentModel(plans=(plan,), on_call=block_model)
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(_open(request_id="cancel-model-call", mode=RunMode.FORCE_AGENT))
    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )
    returned: list[object] = []
    worker = Thread(
        target=lambda: returned.append(
            runner.advance_one(
                opened.run_id,
                expected_version=dispatched.version,
                execution_epoch=0,
            )
        )
    )
    worker.start()
    assert entered.wait(timeout=5)
    reserved = agent.inspect(GetRun(opened.run_id))

    cancelled = agent.submit(
        SignalRun(
            request_id="cancel-model-call-signal",
            run_id=opened.run_id,
            expected_version=reserved.version,
            signal=SignalKind.CANCEL,
        )
    )
    release.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert cancelled.status is RunStatus.CANCELLED
    assert returned and returned[0].applied is False
    with agent_session_factory() as session:
        assert session.scalar(select(AgentPlan).where(AgentPlan.run_id == opened.run_id)) is None
        model_call = session.scalar(
            select(AgentModelCall).where(AgentModelCall.run_id == opened.run_id)
        )
        assert model_call is not None and model_call.status == "abandoned"


def test_score_threshold_excludes_weak_partial_hits_from_claim_evidence(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="relevant-latency",
        content="alpha 延迟事实是 42 毫秒",
    )
    _index_source(agent_session_factory, title="irrelevant-cost-a", content="alpha 成本是 10 元")
    _index_source(agent_session_factory, title="irrelevant-cost-b", content="alpha 成本是 20 元")
    agent = SqlEvidenceAgent(agent_session_factory)
    model = RecordingAgentModel()
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory), agent_model=model)
    opened = agent.submit(
        _open(
            request_id="hard-coverage-gate",
            mode=RunMode.FORCE_QUICK,
            goal="alpha 延迟事实",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))
    evidence = agent.inspect(GetEvidence(artifact.claims[0].evidence_ids[0]))

    assert completed.status is RunStatus.COMPLETED
    assert artifact.claims[0].verification_status == "supported"
    assert len(artifact.claims[0].evidence_ids) == 1
    assert "42" in evidence.excerpt_preview
    assert "成本" not in evidence.excerpt_preview
    assert model.calls == []


def test_agent_mode_uses_model_assessment_and_claim_synthesis_with_hard_provenance(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="model-synthesis-source",
        content="alpha 延迟事实是 42 毫秒",
    )
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="alpha 延迟事实")],
            rationale="single evidence requirement",
        ),
        usage=AgentModelUsage(input_tokens=10, output_tokens=6, cost_micros=5),
        provider="recording",
        model="recording-agent-v1",
    )
    assessment = AgentModelResult(
        value=SufficiencyDecision(decision="answer", reason="direct evidence covers requirement"),
        usage=AgentModelUsage(input_tokens=12, output_tokens=5, cost_micros=6),
        provider="recording",
        model="recording-agent-v1",
    )
    synthesis = AgentModelResult(
        value=SynthesisDecision(
            claims=[ClaimProposal(requirement_ordinal=1, text="Alpha 的延迟为 42 毫秒。")],
            summary="one supported claim",
        ),
        usage=AgentModelUsage(input_tokens=16, output_tokens=8, cost_micros=7),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(
        plans=(plan,),
        assessments=(assessment,),
        syntheses=(synthesis,),
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory), agent_model=model)
    opened = agent.submit(
        _open(
            request_id="model-assess-synthesize",
            mode=RunMode.FORCE_AGENT,
            goal="总结 alpha 延迟事实",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))

    assert completed.status is RunStatus.COMPLETED
    assert [call.operation for call in model.calls] == ["plan", "assess", "synthesize"]
    assert completed.budget_usage["model_calls"] == 3
    assert completed.budget_usage["model_input_tokens"] == 38
    assert artifact.claims[0].text == "Alpha 的延迟为 42 毫秒。"
    assert len(artifact.claims[0].evidence_ids) == 1
    with agent_session_factory() as session:
        model_calls = session.scalars(
            select(AgentModelCall)
            .where(AgentModelCall.run_id == opened.run_id)
            .order_by(AgentModelCall.created_at, AgentModelCall.id)
        ).all()
        assert {item.operation for item in model_calls} == {"plan", "assess", "synthesize"}
        assert {item.status for item in model_calls} == {"completed"}


def test_model_cannot_select_a_winner_when_material_evidence_conflicts(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="conflicting-cost-a",
        content="该方案的成本是 10 元",
    )
    _index_source(
        agent_session_factory,
        title="conflicting-cost-b",
        content="该方案的成本是 20 元",
    )
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="该方案的成本")],
            rationale="one contested requirement",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    assessment = AgentModelResult(
        value=SufficiencyDecision(
            decision="answer",
            reason="model attempts to answer despite conflicting evidence",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    synthesis = AgentModelResult(
        value=SynthesisDecision(
            claims=[ClaimProposal(requirement_ordinal=1, text="该方案的成本是 10 元")],
            summary="model selected one side",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(
        plans=(plan,),
        assessments=(assessment,),
        syntheses=(synthesis,),
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        _search(agent_session_factory),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="model-conflict-abstention",
            mode=RunMode.FORCE_AGENT,
            goal="核对该方案的成本",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    claim = agent.inspect(GetArtifact(completed.final_artifact_id or "")).claims[0]

    assert completed.status is RunStatus.COMPLETED
    assert claim.verification_status == "contested"
    assert claim.resolution_status == "unresolved"
    assert claim.confidence_millis == 250
    assert "冲突" in claim.text
    assert claim.text != "该方案的成本是 10 元"


def test_model_can_issue_one_bounded_next_query_without_expanding_scope(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="rewritten-query-source",
        content="beta 目标延迟是 18 毫秒",
    )
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="alpha 原始问题")],
            rationale="start from the user wording",
        ),
        usage=AgentModelUsage(input_tokens=8, output_tokens=4),
        provider="recording",
        model="recording-agent-v1",
    )
    search_more = AgentModelResult(
        value=SufficiencyDecision(
            decision="search_more",
            reason="initial query found no covering evidence",
            target_requirement_ordinal=1,
            next_query="beta 目标延迟",
        ),
        usage=AgentModelUsage(input_tokens=10, output_tokens=6),
        provider="recording",
        model="recording-agent-v1",
    )
    answer = AgentModelResult(
        value=SufficiencyDecision(decision="answer", reason="follow-up evidence covers the fact"),
        usage=AgentModelUsage(input_tokens=11, output_tokens=4),
        provider="recording",
        model="recording-agent-v1",
    )
    synthesis = AgentModelResult(
        value=SynthesisDecision(
            claims=[ClaimProposal(requirement_ordinal=1, text="目标延迟为 18 毫秒。")],
            summary="bounded follow-up succeeded",
        ),
        usage=AgentModelUsage(input_tokens=13, output_tokens=7),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(
        plans=(plan,),
        assessments=(search_more, answer),
        syntheses=(synthesis,),
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory), agent_model=model)
    opened = agent.submit(
        _open(
            request_id="bounded-next-query",
            mode=RunMode.FORCE_AGENT,
            goal="查明目标延迟",
        )
    )
    opened_view = agent.inspect(GetRun(opened.run_id))

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))

    assert completed.status is RunStatus.COMPLETED
    assert completed.scope_snapshot == opened_view.scope_snapshot
    assert completed.budget_usage["query_rewrites"] == 1
    assert [call.operation for call in model.calls] == [
        "plan",
        "assess",
        "assess",
        "synthesize",
    ]
    # The model omitted beta; publish the named evidence instead of a broader claim.
    assert artifact.claims[0].text == "beta 目标延迟是 18 毫秒"
    with agent_session_factory() as session:
        tool_calls = session.scalars(
            select(AgentToolCall).where(AgentToolCall.run_id == opened.run_id)
        ).all()
        assert len(tool_calls) == 2
        assert {item.tool_name for item in tool_calls} == {"search_evidence"}


def test_model_failures_fall_back_to_deterministic_policy_without_failing_the_run(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="fallback-source",
        content="fallback evidence states latency is 33 ms",
    )
    model = RecordingAgentModel(
        plans=(RuntimeError("planner unavailable"),),
        assessments=(RuntimeError("verifier unavailable"),),
        syntheses=(RuntimeError("synthesizer unavailable"),),
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory), agent_model=model)
    opened = agent.submit(
        _open(
            request_id="deterministic-model-fallback",
            mode=RunMode.FORCE_AGENT,
            goal="fallback evidence",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))

    assert completed.status is RunStatus.COMPLETED
    assert [call.operation for call in model.calls] == ["plan", "assess", "synthesize"]
    assert "33 ms" in artifact.claims[0].text
    with agent_session_factory() as session:
        model_calls = session.scalars(
            select(AgentModelCall).where(AgentModelCall.run_id == opened.run_id)
        ).all()
        assert len(model_calls) == 3
        assert {item.status for item in model_calls} == {"failed"}


def test_model_call_budget_prevents_any_later_model_invocation(agent_session_factory) -> None:
    _index_source(
        agent_session_factory,
        title="one-model-call-source",
        content="one model call evidence is grounded",
    )
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="one model call evidence")],
            rationale="single requirement",
        ),
        usage=AgentModelUsage(input_tokens=5, output_tokens=3),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory), agent_model=model)
    opened = agent.submit(
        _open(
            request_id="model-call-hard-stop",
            mode=RunMode.FORCE_AGENT,
            goal="one model call evidence",
            budget=BudgetLimits(max_steps=8, max_tool_calls=4, max_model_calls=1),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.COMPLETED
    assert completed.budget_usage["model_calls"] == 1
    assert [call.operation for call in model.calls] == ["plan"]


def test_one_repair_attempt_never_crosses_the_external_model_call_budget(
    agent_session_factory,
) -> None:
    provider = _RecordingProvider(
        [
            _result("invalid first response", input_tokens=4, output_tokens=2),
            _result(
                '{"requirements":[{"text":"should not be reached"}],"rationale":"repair"}',
                input_tokens=5,
                output_tokens=3,
            ),
        ]
    )
    model = StructuredAgentModel(LLMService(provider))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="repair-call-budget",
            mode=RunMode.FORCE_AGENT,
            goal="deterministic fallback goal",
            budget=BudgetLimits(max_steps=4, max_model_calls=1),
        )
    )
    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )

    planned = runner.advance_one(
        opened.run_id,
        expected_version=dispatched.version,
        execution_epoch=0,
    )
    view = agent.inspect(GetRun(opened.run_id))

    assert planned.status is RunStatus.PLANNED
    assert provider.calls == 1
    assert view.budget_usage["model_calls"] == 1
    assert view.budget_usage["model_input_tokens"] == 4
    assert view.budget_usage["model_output_tokens"] == 2
    assert view.budget_usage["cost_micros"] == 9
    # The provider reports 4 ms, but AgentRunner deliberately records the
    # larger of provider latency and observed wall time. OS scheduling can
    # therefore make this value higher without changing the budget behavior.
    assert view.budget_usage["active_ms"] >= 4
    with agent_session_factory() as session:
        plan = session.scalar(select(AgentPlan).where(AgentPlan.run_id == opened.run_id))
        assert plan is not None and plan.created_by == "policy"


def test_successful_structured_repair_counts_as_a_second_model_call_and_step(
    agent_session_factory,
) -> None:
    provider = _RecordingProvider(
        [
            _result("invalid first response", input_tokens=4, output_tokens=2),
            _result(
                '{"requirements":[{"text":"repaired requirement"}],"rationale":"repair"}',
                input_tokens=5,
                output_tokens=3,
            ),
        ]
    )
    model = StructuredAgentModel(LLMService(provider))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="repair-call-accounting",
            mode=RunMode.FORCE_AGENT,
            goal="repair this plan",
            budget=BudgetLimits(max_steps=4, max_model_calls=2),
        )
    )
    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )

    planned = runner.advance_one(
        opened.run_id,
        expected_version=dispatched.version,
        execution_epoch=0,
    )
    view = agent.inspect(GetRun(opened.run_id))

    assert planned.status is RunStatus.PLANNED
    assert provider.calls == 2
    assert view.budget_usage["model_calls"] == 2
    assert view.budget_usage["steps"] == 2
    assert view.budget_usage["model_input_tokens"] == 9
    assert view.budget_usage["model_output_tokens"] == 5
    with agent_session_factory() as session:
        plan = session.scalar(select(AgentPlan).where(AgentPlan.run_id == opened.run_id))
        model_call = session.scalar(
            select(AgentModelCall).where(AgentModelCall.run_id == opened.run_id)
        )
        assert plan is not None and plan.created_by == "model"
        assert model_call is not None and model_call.retries == 1


def test_step_budget_stops_before_the_next_external_tool_call(agent_session_factory) -> None:
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="step budget evidence")],
            rationale="single requirement",
        ),
        usage=AgentModelUsage(input_tokens=4, output_tokens=2),
        provider="recording",
        model="recording-agent-v1",
    )
    searches: list[object] = []
    model = RecordingAgentModel(plans=(plan,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda request: searches.append(request) or EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="step-hard-stop",
            mode=RunMode.FORCE_AGENT,
            goal="step budget evidence",
            budget=BudgetLimits(max_steps=1, max_tool_calls=4, max_model_calls=4),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "max_steps"
    assert completed.budget_usage["steps"] == 1
    assert searches == []


def test_no_new_evidence_budget_stops_repeated_model_query_rewrites(
    agent_session_factory,
) -> None:
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="first empty query")],
            rationale="probe",
        ),
        usage=AgentModelUsage(input_tokens=4, output_tokens=2),
        provider="recording",
        model="recording-agent-v1",
    )
    rewrite = AgentModelResult(
        value=SufficiencyDecision(
            decision="search_more",
            reason="try one bounded rewrite",
            target_requirement_ordinal=1,
            next_query="second empty query",
        ),
        usage=AgentModelUsage(input_tokens=5, output_tokens=3),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan,), assessments=(rewrite,))
    searches: list[object] = []
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda request: searches.append(request) or EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="no-new-evidence-hard-stop",
            mode=RunMode.FORCE_AGENT,
            goal="find absent evidence",
            budget=BudgetLimits(
                max_steps=8,
                max_tool_calls=4,
                max_model_calls=4,
                max_no_new_evidence_rounds=2,
            ),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "max_no_new_evidence_rounds"
    assert len(searches) == 2
    assert [call.operation for call in model.calls] == ["plan", "assess"]


@pytest.mark.parametrize(
    ("limits", "usage", "expected_reason"),
    [
        (
            BudgetLimits(max_model_input_tokens=4),
            AgentModelUsage(input_tokens=5),
            "max_model_input_tokens",
        ),
        (
            BudgetLimits(max_model_output_tokens=4),
            AgentModelUsage(output_tokens=5),
            "max_model_output_tokens",
        ),
        (
            BudgetLimits(max_cost_micros=9),
            AgentModelUsage(cost_micros=10),
            "max_cost_micros",
        ),
        (
            BudgetLimits(max_active_ms=9),
            AgentModelUsage(latency_ms=10),
            "max_active_ms",
        ),
    ],
)
def test_output_cost_and_active_time_model_budgets_are_hard_limits(
    limits: BudgetLimits,
    usage: AgentModelUsage,
    expected_reason: str,
) -> None:
    controller = BudgetController(limits)
    reserved = controller.reserve_model_call(BudgetUsage())

    with pytest.raises(BudgetExceeded) as exceeded:
        controller.record_model_usage(
            reserved,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_micros=usage.cost_micros,
            active_ms=usage.latency_ms,
        )

    assert exceeded.value.reason == expected_reason
    assert exceeded.value.usage is not None


def test_retrieval_active_time_is_accounted_and_stops_the_run(agent_session_factory) -> None:
    ticks = iter((10.000, 10.015))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        clock=lambda: next(ticks),
    )
    opened = agent.submit(
        _open(
            request_id="retrieval-active-time",
            mode=RunMode.FORCE_QUICK,
            budget=BudgetLimits(max_active_ms=10),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "max_active_ms"
    assert completed.budget_usage["active_ms"] == 15


def test_measured_model_wall_time_cannot_be_hidden_by_adapter_usage(
    agent_session_factory,
) -> None:
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="model wall time")],
            rationale="single requirement",
        ),
        usage=AgentModelUsage(latency_ms=0),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan,))
    searches: list[object] = []
    ticks = iter((20.000, 20.015))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda request: searches.append(request) or EvidenceSearchResult(hits=()),
        agent_model=model,
        clock=lambda: next(ticks),
    )
    opened = agent.submit(
        _open(
            request_id="model-wall-time",
            mode=RunMode.FORCE_AGENT,
            goal="model wall time",
            budget=BudgetLimits(max_active_ms=10),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "max_active_ms"
    assert completed.budget_usage["active_ms"] == 15
    assert searches == []


def test_context_tokens_are_persisted_and_block_the_next_external_model_call(
    agent_session_factory,
) -> None:
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="context limited evidence")],
            rationale="single requirement",
        ),
        usage=AgentModelUsage(input_tokens=5, output_tokens=2),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="context-token-hard-stop",
            mode=RunMode.FORCE_AGENT,
            goal="context limited evidence",
            budget=BudgetLimits(max_context_tokens=5),
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    frames = asyncio.run(_public_frames(agent, opened.run_id))
    budget_events = [frame for frame in frames if frame.event_type == "budget.exhausted"]

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.budget_usage["context_tokens"] == 5
    assert [call.operation for call in model.calls] == ["plan"]
    assert any(frame.payload["reason"] == "max_context_tokens" for frame in budget_events)


def test_missing_provider_token_usage_gets_a_conservative_context_estimate(
    agent_session_factory,
) -> None:
    provider = _RecordingProvider(
        [
            LLMResult(
                text=(
                    '{"requirements":[{"text":"estimated context evidence"}],'
                    '"rationale":"single requirement"}'
                ),
                provider="recording",
                model="recording-structured-v1",
                estimated_usage=True,
            )
        ]
    )
    model = StructuredAgentModel(LLMService(provider))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="estimated-context-token-hard-stop",
            mode=RunMode.FORCE_AGENT,
            goal="estimated context evidence",
            budget=BudgetLimits(max_context_tokens=1),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.budget_usage["context_tokens"] > 1
    assert provider.calls == 1


def test_unknown_model_cost_is_persisted_without_pretending_it_is_zero(
    agent_session_factory,
) -> None:
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="unknown cost evidence")],
            rationale="single requirement",
        ),
        usage=AgentModelUsage(input_tokens=3, output_tokens=1, cost_micros=None),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="unknown-cost-accounting",
            mode=RunMode.FORCE_AGENT,
            goal="unknown cost evidence",
            budget=BudgetLimits(max_model_calls=1),
        )
    )

    _drain(agent, runner, opened.run_id)
    view = agent.inspect(GetRun(opened.run_id))

    assert view.budget_usage["cost_micros"] == 0
    assert view.budget_usage["cost_unknown_calls"] == 1
    assert view.cost_measurement == "unknown"


def test_estimated_model_cost_is_distinct_from_unknown_cost(agent_session_factory) -> None:
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="estimated cost evidence")],
            rationale="single requirement",
        ),
        usage=AgentModelUsage(
            input_tokens=3,
            output_tokens=1,
            cost_micros=4,
            cost_status="estimated",
        ),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(plans=(plan,))
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="estimated-cost-accounting",
            mode=RunMode.FORCE_AGENT,
            goal="estimated cost evidence",
            budget=BudgetLimits(max_model_calls=1),
        )
    )

    _drain(agent, runner, opened.run_id)
    view = agent.inspect(GetRun(opened.run_id))

    assert view.budget_usage["cost_micros"] == 4
    assert view.budget_usage["cost_estimated_calls"] == 1
    assert view.cost_measurement == "estimated"


@pytest.mark.parametrize(
    ("candidate_claim", "unsupported_literal"),
    [
        ("Alpha 延迟事实是99毫秒。", "99"),
        ("Beta 延迟事实是42毫秒。", "Beta"),
    ],
)
def test_claim_synthesis_falls_back_when_model_introduces_unseen_numbers_or_names(
    agent_session_factory,
    candidate_claim: str,
    unsupported_literal: str,
) -> None:
    _index_source(
        agent_session_factory,
        title="claim-entailment-source",
        content="Alpha 延迟事实是42毫秒",
    )
    model = RecordingAgentModel(
        plans=(
            AgentModelResult(
                value=PlanDecision(
                    requirements=[RequirementProposal(text="Alpha 延迟事实")],
                    rationale="single requirement",
                ),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
        assessments=(
            AgentModelResult(
                value=SufficiencyDecision(decision="answer", reason="evidence found"),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
        syntheses=(
            AgentModelResult(
                value=SynthesisDecision(
                    claims=[
                        ClaimProposal(
                            requirement_ordinal=1,
                            text=candidate_claim,
                        )
                    ],
                    summary="unsupported literals",
                ),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory), agent_model=model)
    opened = agent.submit(
        _open(
            request_id="claim-literal-entailment",
            mode=RunMode.FORCE_AGENT,
            goal="核验 Alpha 延迟事实",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))

    assert artifact.claims[0].text == "Alpha 延迟事实是42毫秒"
    assert unsupported_literal not in artifact.claims[0].text


def test_agent_does_not_publish_unrelated_bounded_claim_as_supported(
    agent_session_factory,
) -> None:
    excerpt = "Alpha latency is 42 milliseconds."
    _index_source(agent_session_factory, title="alpha-latency-evidence", content=excerpt)
    model = RecordingAgentModel(
        plans=(
            AgentModelResult(
                value=PlanDecision(
                    requirements=[RequirementProposal(text="Alpha latency")],
                    rationale="one factual requirement",
                ),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
        assessments=(
            AgentModelResult(
                value=SufficiencyDecision(decision="answer", reason="evidence found"),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
        syntheses=(
            AgentModelResult(
                value=SynthesisDecision(
                    claims=[ClaimProposal(requirement_ordinal=1, text="Omega supports at least 40 users.")],
                    summary="attempted unsupported conclusion",
                ),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(
            hits=(_hit_for_source(agent_session_factory, title="alpha-latency-evidence"),)
        ),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="unrelated-bounded-model-claim",
            mode=RunMode.FORCE_AGENT,
            goal="What is Alpha latency?",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))

    assert completed.status is RunStatus.COMPLETED
    assert artifact.claims[0].text == excerpt


def test_model_clarification_gate_accepts_input_and_resumes_the_same_run(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="clarification-source",
        content="Beta 目标延迟在 2024 年是 18 毫秒",
    )
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="Beta 目标延迟")],
            rationale="one ambiguous period",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    clarify = AgentModelResult(
        value=SufficiencyDecision(
            decision="request_clarification",
            reason="the requested period is ambiguous",
            target_requirement_ordinal=1,
            clarification_question="请指定要核验的年份。",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    answer = AgentModelResult(
        value=SufficiencyDecision(decision="answer", reason="the clarified evidence is sufficient"),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    synthesis = AgentModelResult(
        value=SynthesisDecision(
            claims=[ClaimProposal(requirement_ordinal=1, text="Beta 在 2024 年的目标延迟是 18 毫秒。")],
            summary="clarified answer",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    model = RecordingAgentModel(
        plans=(plan,),
        assessments=(clarify, answer),
        syntheses=(synthesis,),
    )
    search = _search(agent_session_factory)
    observed_queries: list[str] = []

    def recording_search(request):
        observed_queries.append(request.text)
        return search(request)

    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, recording_search, agent_model=model)
    opened = agent.submit(
        _open(
            request_id="clarification-resume",
            mode=RunMode.FORCE_AGENT,
            goal="核验 Beta 目标延迟",
        )
    )

    for _ in range(20):
        waiting = agent.inspect(GetRun(opened.run_id))
        if waiting.status is RunStatus.AWAITING_INPUT:
            break
        advanced = runner.advance_one(
            opened.run_id,
            expected_version=waiting.version,
            execution_epoch=waiting.execution_epoch,
        )
        assert advanced.applied is True
    else:
        raise AssertionError("Run did not request clarification.")

    frames = asyncio.run(
        _public_frames_until(agent, opened.run_id, "interaction.required")
    )
    interaction = next(frame for frame in frames if frame.event_type == "interaction.required")
    assert interaction.payload == {
        "gate_id": interaction.payload["gate_id"],
        "kind": "clarification",
        "question": "请指定要核验的年份。",
        "response_schema": {
            "additionalProperties": False,
            "properties": {"text": {"maxLength": 500, "minLength": 1, "type": "string"}},
            "required": ["text"],
            "type": "object",
        },
        "target": {
            "requirement_id": interaction.payload["target"]["requirement_id"],
            "requirement_ordinal": 1,
        },
    }

    with pytest.raises(ServiceError) as invalid:
        agent.submit(
            SignalRun(
                request_id="clarification-empty",
                run_id=opened.run_id,
                expected_version=waiting.version,
                signal=SignalKind.PROVIDE_INPUT,
                response={"text": "   "},
            )
        )
    assert invalid.value.code == "INVALID_CLARIFICATION_RESPONSE"
    assert agent.inspect(GetRun(opened.run_id)).status is RunStatus.AWAITING_INPUT

    resumed = agent.submit(
        SignalRun(
            request_id="clarification-valid",
            run_id=opened.run_id,
            expected_version=waiting.version,
            signal=SignalKind.PROVIDE_INPUT,
            response={"text": "2024"},
        )
    )
    replay = agent.submit(
        SignalRun(
            request_id="clarification-valid",
            run_id=opened.run_id,
            expected_version=waiting.version,
            signal=SignalKind.PROVIDE_INPUT,
            response={"text": "2024"},
        )
    )

    assert resumed.run_id == opened.run_id
    assert resumed.status is RunStatus.QUEUED
    assert replay.replayed is True
    completed = _drain(agent, runner, opened.run_id)

    assert completed.id == opened.run_id
    assert completed.status is RunStatus.COMPLETED
    assert observed_queries == ["Beta 目标延迟", "Beta 目标延迟 2024"]
    assert [call.operation for call in model.calls] == ["plan", "assess", "assess", "synthesize"]


def test_public_events_expose_full_evidence_reference_and_published_artifact(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="immutable-source-title",
        content="Alpha 延迟事实是 42 毫秒",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory))
    opened = agent.submit(
        _open(
            request_id="public-event-wire-contract",
            mode=RunMode.FORCE_QUICK,
            goal="Alpha 延迟事实是 42 毫秒",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    frames = asyncio.run(_public_frames(agent, opened.run_id))
    evidence_events = [frame for frame in frames if frame.event_type == "evidence.added"]
    published_events = [frame for frame in frames if frame.event_type == "artifact.published"]

    assert len(evidence_events) == 1
    evidence_payload = evidence_events[0].payload
    evidence = agent.inspect(GetEvidence(str(evidence_payload["evidence_id"])))
    assert evidence_payload == {
        "evidence_id": evidence.id,
        "excerpt": "Alpha 延迟事实是 42 毫秒",
        "reference": {
            "chunk_id": evidence.chunk_id,
            "content_hash": evidence.content_hash,
            "index_revision_id": evidence.index_revision_id,
            "locator": dict(evidence.locator),
            "revision_id": evidence.revision_id,
            "source_id": evidence.source_id,
        },
        "relation": "supports",
        "source_title": "immutable-source-title",
    }
    assert len(published_events) == 1
    assert published_events[0].payload["artifact_id"] == completed.final_artifact_id
    assert published_events[0].payload["final_artifact_id"] == completed.final_artifact_id


def test_agent_keeps_high_scoring_semantic_hit_without_lexical_overlap(
    agent_session_factory,
) -> None:
    excerpt = "An immutable provenance ledger binds every claim to source revisions."
    distractor = "Operational dashboards summarize fleet capacity and regional traffic."
    _index_source(
        agent_session_factory,
        title="semantic-provenance-source",
        content=excerpt,
    )
    _index_source(
        agent_session_factory,
        title="semantic-distractor-source",
        content=distractor,
    )
    with agent_session_factory() as session:
        hits: list[EvidenceHit] = []
        for title, score in (
            ("semantic-provenance-source", 0.97),
            ("semantic-distractor-source", 0.90),
        ):
            source = session.scalar(select(Source).where(Source.title == title))
            assert source is not None
            chunk = session.scalar(
                select(MultimodalChunk).where(
                    MultimodalChunk.source_id == source.id,
                    MultimodalChunk.revision_id == source.active_revision_id,
                )
            )
            assert chunk is not None
            hits.append(
                EvidenceHit(
                    evidence=PinnedEvidenceRef(
                        source_id=source.id,
                        revision_id=int(source.active_revision_id),
                        index_revision_id=int(source.active_index_revision_id),
                        chunk_id=chunk.id,
                        source_type=source.source_type,
                        modality=chunk.modality,
                        content_hash=chunk.content_hash,
                        locator={"kind": "document_chunk", "chunk_index": chunk.chunk_index},
                        excerpt=chunk.content_text,
                        currently_active=True,
                    ),
                    score=score,
                )
            )

    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="How can answers be traced back?")],
            rationale="verify one semantic requirement",
        ),
        usage=AgentModelUsage(input_tokens=8, output_tokens=4),
        provider="recording",
        model="recording-agent-v1",
    )
    synthesis = AgentModelResult(
        value=SynthesisDecision(
            claims=[ClaimProposal(requirement_ordinal=1, text=excerpt)],
            summary="semantic evidence supports the claim",
        ),
        usage=AgentModelUsage(input_tokens=12, output_tokens=6),
        provider="recording",
        model="recording-agent-v1",
    )
    def select_traceability_candidate(request: AssessModelInput) -> list[dict[str, object]]:
        requirement = request.requirements[0]
        selected = next(item for item in requirement.evidence if item.excerpt == excerpt)
        return [
            {
                "requirement_ordinal": requirement.ordinal,
                "supporting_evidence_ids": [selected.evidence_id],
            }
        ]

    model = _SelectingAgentModel(
        plans=(plan,),
        syntheses=(synthesis,),
        select=select_traceability_candidate,
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=tuple(hits)),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="semantic-dense-hit",
            mode=RunMode.FORCE_AGENT,
            goal="How can answers be traced back?",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    assert completed.status is RunStatus.COMPLETED
    assert completed.final_artifact_id is not None
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id))
    assert artifact.claims[0].text == excerpt
    evidence = agent.inspect(GetEvidence(artifact.claims[0].evidence_ids[0]))
    assert evidence.excerpt_preview == excerpt
    assessment_input = model.calls[1].request
    assert isinstance(assessment_input, AssessModelInput)
    assert assessment_input.requirements[0].status == "partial"
    assert {item.relation for item in assessment_input.requirements[0].evidence} == {"candidate"}
    synthesis_input = model.calls[2].request
    assert [item.evidence_id for item in synthesis_input.requirements[0].evidence] == [
        evidence.id
    ]
    with agent_session_factory() as session:
        support_rows = session.execute(
            select(AgentEvidence.excerpt_preview, RequirementEvidence.relation)
            .join(RequirementEvidence, RequirementEvidence.evidence_id == AgentEvidence.id)
            .join(AgentRequirement, AgentRequirement.id == RequirementEvidence.requirement_id)
            .where(AgentRequirement.run_id == opened.run_id)
        ).all()
        requirement_id = session.scalar(
            select(AgentRequirement.id).where(
                AgentRequirement.run_id == opened.run_id,
                AgentRequirement.ordinal == 1,
            )
        )
        assert requirement_id is not None
    assert set(support_rows) == {(excerpt, "supports"), (distractor, "excluded")}
    assert artifact.claims[0].evidence_ids == (evidence.id,)
    frames = asyncio.run(_public_frames(agent, opened.run_id))
    relation_changes = [
        frame
        for frame in frames
        if frame.event_type == "evidence.relation_changed"
        and frame.payload.get("evidence_id") == evidence.id
    ]
    assert len(relation_changes) == 1
    assert relation_changes[0].payload == {
        "evidence_id": evidence.id,
        "requirement_id": requirement_id,
        "requirement_ordinal": 1,
        "previous_relation": "candidate",
        "relation": "supports",
        "reason": "model_selected_support",
        "method": "model_assessment",
    }
    candidate_event = next(
        frame
        for frame in frames
        if frame.event_type == "evidence.added"
        and frame.payload.get("evidence_id") == evidence.id
    )
    assert candidate_event.cursor < relation_changes[0].cursor
    excluded_change = next(
        frame
        for frame in frames
        if frame.event_type == "evidence.relation_changed"
        and frame.payload.get("relation") == "excluded"
    )
    assert excluded_change.payload["reason"] == "model_not_selected"
    assert excluded_change.payload["method"] == "model_assessment"


def test_agent_rejects_model_selected_evidence_id_outside_the_requirement_candidates(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="fake-selection-source",
        content="An immutable provenance ledger binds every claim to source revisions.",
    )
    hit = _hit_for_source(agent_session_factory, title="fake-selection-source")
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[RequirementProposal(text="How can answers be traced back?")],
            rationale="one semantic requirement",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )
    model = _SelectingAgentModel(
        plans=(plan,),
        select=lambda request: [
            {
                "requirement_ordinal": request.requirements[0].ordinal,
                "supporting_evidence_ids": ["not-a-real-evidence-id"],
            }
        ],
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=(hit,)),
        agent_model=model,
    )
    opened = agent.submit(
        _open(
            request_id="reject-fake-model-evidence-id",
            mode=RunMode.FORCE_AGENT,
            goal="How can answers be traced back?",
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "model_evidence_selection_invalid"
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))
    assert artifact.kind == "evidence_gap_report"
    assert artifact.claims == ()


def test_agent_rejects_cross_requirement_evidence_selection(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="traceability-candidate",
        content="An immutable provenance ledger binds every claim to source revisions.",
    )
    _index_source(
        agent_session_factory,
        title="governance-candidate",
        content="A designated chair authorizes each controlled publication window.",
    )
    traceability_hit = _hit_for_source(agent_session_factory, title="traceability-candidate")
    governance_hit = _hit_for_source(agent_session_factory, title="governance-candidate")
    plan = AgentModelResult(
        value=PlanDecision(
            requirements=[
                RequirementProposal(text="How can answers be traced back?"),
                RequirementProposal(text="Who controls release governance?"),
            ],
            rationale="two independent semantic requirements",
        ),
        usage=AgentModelUsage(),
        provider="recording",
        model="recording-agent-v1",
    )

    def select_cross_requirement(request: AssessModelInput) -> list[dict[str, object]]:
        first_id = request.requirements[0].evidence[0].evidence_id
        return [
            {
                "requirement_ordinal": request.requirements[0].ordinal,
                "supporting_evidence_ids": [first_id],
            },
            {
                "requirement_ordinal": request.requirements[1].ordinal,
                "supporting_evidence_ids": [first_id],
            },
        ]

    model = _SelectingAgentModel(plans=(plan,), select=select_cross_requirement)

    def search(request):
        hit = traceability_hit if "traced" in request.text else governance_hit
        return EvidenceSearchResult(hits=(hit,))

    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, search, agent_model=model)
    opened = agent.submit(
        _open(
            request_id="reject-cross-requirement-selection",
            mode=RunMode.FORCE_AGENT,
            goal="Verify traceability and release governance",
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "model_evidence_selection_invalid"
    with agent_session_factory() as session:
        assert set(
            session.scalars(
                select(RequirementEvidence.relation)
                .join(AgentRequirement, AgentRequirement.id == RequirementEvidence.requirement_id)
                .where(AgentRequirement.run_id == opened.run_id)
            )
        ) == {"candidate"}


def test_quick_mode_does_not_treat_same_entity_candidate_as_fact_coverage(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="alpha-service-facts",
        content="Alpha 服务延迟事实是 42 毫秒。Alpha 服务月成本事实是 10 元。",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory))
    opened = agent.submit(
        _open(
            request_id="quick-candidate-is-not-coverage",
            mode=RunMode.FORCE_QUICK,
            goal="Alpha 服务董事长事实",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert completed.termination_reason == "required_evidence_missing"
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))
    assert artifact.kind == "evidence_gap_report"
    assert artifact.claims == ()


def test_production_runner_requires_exact_approval_before_publishing_artifact(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="approval-source",
        content="The audit trail uses immutable revision hashes and locators.",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory))
    opened = agent.submit(
        _open(
            request_id="production-artifact-approval",
            mode=RunMode.FORCE_QUICK,
            goal="immutable revision hashes and locators",
            permissions=PermissionPolicy(read_only=False),
        )
    )

    for _ in range(12):
        waiting = agent.inspect(GetRun(opened.run_id))
        if waiting.status is RunStatus.AWAITING_APPROVAL:
            break
        advanced = runner.advance_one(
            opened.run_id,
            expected_version=waiting.version,
            execution_epoch=waiting.execution_epoch,
        )
        assert advanced.applied is True
    else:
        raise AssertionError("Production runner never proposed its protected artifact write.")

    assert waiting.budget_usage["tool_calls"] == 2
    frames = asyncio.run(
        _public_frames_until(agent, opened.run_id, "interaction.required")
    )
    interaction = next(frame for frame in frames if frame.event_type == "interaction.required")
    assert interaction.payload["kind"] == "approval"
    assert interaction.payload["risk_class"] == "write"
    assert interaction.payload["target"].startswith("artifact:")
    assert len(interaction.payload["proposal_digest"]) == 64
    artifact_id = interaction.payload["target"].removeprefix("artifact:")

    draft = agent.inspect(GetArtifact(artifact_id))
    assert draft.status == "draft"
    with agent_session_factory() as session:
        gate = session.scalar(
            select(AgentGate).where(
                AgentGate.run_id == opened.run_id,
                AgentGate.status == "open",
            )
        )
        assert gate is not None
        proposal = session.get(AgentToolCall, gate.proposed_tool_call_id)
        assert proposal is not None
        assert proposal.tool_name == "publish_artifact"
        assert proposal.status == "awaiting_approval"
        assert proposal.arguments_digest == interaction.payload["proposal_digest"]
        proposal_arguments = json.loads(proposal.arguments_json)
        assert proposal_arguments == {
            "artifact_digest": proposal_arguments["artifact_digest"],
            "artifact_id": artifact_id,
            "expected_status": "draft",
            "run_id": opened.run_id,
        }
        assert len(proposal_arguments["artifact_digest"]) == 64

    approved = agent.submit(
        SignalRun(
            request_id="approve-production-artifact",
            run_id=opened.run_id,
            expected_version=waiting.version,
            signal=SignalKind.APPROVE,
            proposal_digest=interaction.payload["proposal_digest"],
        )
    )
    assert approved.status is RunStatus.QUEUED

    completed = _drain(agent, runner, opened.run_id)
    published = agent.inspect(GetArtifact(artifact_id))
    assert completed.status is RunStatus.COMPLETED
    assert completed.final_artifact_id == artifact_id
    assert published.status == "final"
    with agent_session_factory() as session:
        proposal = session.scalar(
            select(AgentToolCall).where(
                AgentToolCall.run_id == opened.run_id,
                AgentToolCall.tool_name == "publish_artifact",
            )
        )
        assert proposal is not None
        assert proposal.status == "completed"
        assert proposal.result_json == '{"artifact_id":"' + artifact_id + '","status":"final"}'


def test_modifying_artifact_title_rotates_the_exact_approval_digest(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="modify-approval-source",
        content="Immutable evidence makes artifact review reproducible.",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory))
    opened = agent.submit(
        _open(
            request_id="modify-production-artifact",
            mode=RunMode.FORCE_QUICK,
            goal="Immutable evidence makes artifact review reproducible.",
            permissions=PermissionPolicy(read_only=False),
        )
    )
    for _ in range(12):
        waiting = agent.inspect(GetRun(opened.run_id))
        if waiting.status is RunStatus.AWAITING_APPROVAL:
            break
        runner.advance_one(
            opened.run_id,
            expected_version=waiting.version,
            execution_epoch=waiting.execution_epoch,
        )
    else:
        raise AssertionError("Runner never proposed the protected artifact write.")

    with agent_session_factory() as session:
        old_gate = session.scalar(
            select(AgentGate).where(AgentGate.run_id == opened.run_id, AgentGate.status == "open")
        )
        assert old_gate is not None and old_gate.arguments_digest is not None
        old_digest = old_gate.arguments_digest
        proposal = session.get(AgentToolCall, old_gate.proposed_tool_call_id)
        assert proposal is not None
        artifact_id = str(json.loads(proposal.arguments_json)["artifact_id"])

    modified = agent.submit(
        SignalRun(
            request_id="modify-artifact-title",
            run_id=opened.run_id,
            expected_version=waiting.version,
            signal=SignalKind.MODIFY,
            response={"title": "经过人工复核的证据报告"},
            proposal_digest=old_digest,
        )
    )
    assert modified.status is RunStatus.AWAITING_APPROVAL

    with agent_session_factory() as session:
        artifact = session.get(AgentArtifact, artifact_id)
        new_gate = session.get(AgentGate, session.get(AgentRun, opened.run_id).pending_gate_id)
        assert artifact is not None and artifact.title == "经过人工复核的证据报告"
        assert new_gate is not None and new_gate.arguments_digest != old_digest
        new_digest = new_gate.arguments_digest

    with pytest.raises(ServiceError) as stale:
        agent.submit(
            SignalRun(
                request_id="approve-old-modified-proposal",
                run_id=opened.run_id,
                expected_version=modified.run_version,
                signal=SignalKind.APPROVE,
                proposal_digest=old_digest,
            )
        )
    assert stale.value.code == "STALE_APPROVAL"

    approved = agent.submit(
        SignalRun(
            request_id="approve-new-modified-proposal",
            run_id=opened.run_id,
            expected_version=modified.run_version,
            signal=SignalKind.APPROVE,
            proposal_digest=new_digest,
        )
    )
    assert approved.status is RunStatus.QUEUED
    completed = _drain(agent, runner, opened.run_id)
    assert completed.status is RunStatus.COMPLETED
    assert agent.inspect(GetArtifact(artifact_id)).title == "经过人工复核的证据报告"


def test_rejecting_production_artifact_proposal_ends_as_insufficient_without_publication(
    agent_session_factory,
) -> None:
    _index_source(
        agent_session_factory,
        title="rejected-approval-source",
        content="Immutable locators make every factual answer reproducible.",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(agent_session_factory, _search(agent_session_factory))
    opened = agent.submit(
        _open(
            request_id="reject-production-artifact",
            mode=RunMode.FORCE_QUICK,
            goal="Immutable locators make every factual answer reproducible.",
            permissions=PermissionPolicy(read_only=False),
        )
    )

    for _ in range(12):
        waiting = agent.inspect(GetRun(opened.run_id))
        if waiting.status is RunStatus.AWAITING_APPROVAL:
            break
        advanced = runner.advance_one(
            opened.run_id,
            expected_version=waiting.version,
            execution_epoch=waiting.execution_epoch,
        )
        assert advanced.applied is True
    else:
        raise AssertionError("Production runner never proposed its protected artifact write.")

    frames = asyncio.run(
        _public_frames_until(agent, opened.run_id, "interaction.required")
    )
    interaction = next(frame for frame in frames if frame.event_type == "interaction.required")
    artifact_id = interaction.payload["target"].removeprefix("artifact:")
    rejected = agent.submit(
        SignalRun(
            request_id="reject-protected-artifact",
            run_id=opened.run_id,
            expected_version=waiting.version,
            signal=SignalKind.REJECT,
            proposal_digest=interaction.payload["proposal_digest"],
        )
    )

    outcome = agent.inspect(GetRun(opened.run_id))
    draft = agent.inspect(GetArtifact(artifact_id))
    all_frames = asyncio.run(_public_frames(agent, opened.run_id))
    assert rejected.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.termination_reason == "approval_rejected"
    assert outcome.final_artifact_id is None
    assert draft.status == "rejected"
    assert not any(frame.event_type == "artifact.published" for frame in all_frames)
    with agent_session_factory() as session:
        proposal = session.scalar(
            select(AgentToolCall).where(
                AgentToolCall.run_id == opened.run_id,
                AgentToolCall.tool_name == "publish_artifact",
            )
        )
        assert proposal is not None
        assert proposal.status == "rejected"
        assert proposal.error_code == "approval_rejected"


def test_insufficient_gap_artifact_is_published_to_the_public_event_stream(
    agent_session_factory,
) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = AgentRunner(
        agent_session_factory,
        lambda _request: EvidenceSearchResult(hits=()),
    )
    opened = agent.submit(
        _open(
            request_id="insufficient-artifact-event",
            mode=RunMode.FORCE_QUICK,
            goal="missing evidence",
        )
    )

    completed = _drain(agent, runner, opened.run_id)
    frames = asyncio.run(_public_frames(agent, opened.run_id))
    published = [frame for frame in frames if frame.event_type == "artifact.published"]

    assert completed.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert len(published) == 1
    assert published[0].payload["artifact_id"] == completed.final_artifact_id
    assert published[0].payload["final_artifact_id"] == completed.final_artifact_id
