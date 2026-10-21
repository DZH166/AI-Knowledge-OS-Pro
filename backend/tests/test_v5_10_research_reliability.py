from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ServiceError
from app.db.session import Base
from app.models.knowledge_space import KnowledgeSpace
from app.models.agent_evidence import ClaimEvidence
from app.models.source import IndexRevision, Source, SourceRevision
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    ContinueRun,
    DeliverableSpec,
    GetArtifact,
    GetEvidence,
    GetRun,
    ListRuns,
    OpenRun,
    PermissionPolicy,
    RunMode,
    RunStatus,
    ScopeSelector,
    SignalKind,
    SignalRun,
)
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_index import (
    ActivateRevision,
    ChunkDraft,
    EvidenceSearchResult,
    GetRevision,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    VerifiedPoint,
)
from app.services.agent_model import (
    AgentModelResult,
    AgentModelUsage,
    ClaimProposal,
    PlanDecision,
    RequirementProposal,
    SynthesisDecision,
)
from test_v5_agent_model_runner import _SelectingAgentModel, _hit_for_source


@pytest.fixture()
def research_sessions():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Research reliability"))
        session.add(KnowledgeSpace(id=2, name="Other space"))
    try:
        yield factory
    finally:
        engine.dispose()


def index_source(factory, *, title: str, content: str, space_id: int = 1) -> Source:
    with factory() as session:
        source = Source(space_id=space_id, source_type="document", title=title, file_size=len(content))
        session.add(source)
        session.commit()
        index = SqlEvidenceIndex(session)
        staged = index.command(StageRevision(
            command_id=f"stage-{title}",
            draft=RevisionDraft(
                source_id=source.id, content_hash=sha256(content.encode()).hexdigest(),
                index_version="reliability-test", collection_name="reliability-test",
                chunks=(ChunkDraft(chunk_index=0, modality="text", content=content,
                                   locator={"kind": "text", "heading": title}),),
            ),
        ))
        revision = index.query(GetRevision(staged.revision_id))
        index.command(ActivateRevision(
            command_id=f"activate-{title}", revision_id=staged.revision_id,
            verified_points=tuple(VerifiedPoint(point.point_id, point.payload_digest) for point in revision.points),
        ))
        session.refresh(source)
        session.expunge(source)
        return source


def open_research(*, source_ids=(), request_id="research-request", goal="延迟", kind="answer") -> OpenRun:
    return OpenRun(
        request_id=request_id, space_id=1, goal=goal, scope=ScopeSelector(source_ids=source_ids),
        deliverable=DeliverableSpec(kind=kind), mode=RunMode.FORCE_QUICK,
        budget=BudgetLimits(), permissions=PermissionPolicy(), provider_mode="recording",
    )


@pytest.mark.parametrize("invalid_state", [
    "missing", "retired", "wrong_space", "no_revision", "revision_missing", "revision_retired",
    "revision_failed", "wrong_revision", "index_missing", "index_retired", "index_failed", "wrong_index",
])
def test_explicit_selection_never_creates_a_run_with_a_reduced_source_scope(research_sessions, invalid_state):
    good = index_source(research_sessions, title="good", content="延迟为 12 ms")
    bad = index_source(research_sessions, title="bad", content="延迟为 8 ms")
    bad_id = bad.id
    with research_sessions.begin() as session:
        source = session.get(Source, bad.id)
        if invalid_state == "missing":
            bad_id = 9999
        elif invalid_state == "retired":
            source.retired_at = datetime.now(UTC)
        elif invalid_state == "wrong_space":
            source.space_id = 2
        elif invalid_state == "no_revision":
            source.active_revision_id = None
        elif invalid_state == "revision_missing":
            source.active_revision_id = 9999
        elif invalid_state == "revision_retired":
            session.get(SourceRevision, source.active_revision_id).status = "retired"
        elif invalid_state == "revision_failed":
            session.get(SourceRevision, source.active_revision_id).validation_status = "failed"
        elif invalid_state == "wrong_revision":
            source.active_revision_id = good.active_revision_id
        elif invalid_state == "index_missing":
            source.active_index_revision_id = 9999
        elif invalid_state == "index_retired":
            session.get(IndexRevision, source.active_index_revision_id).status = "retired"
        elif invalid_state == "index_failed":
            session.get(IndexRevision, source.active_index_revision_id).validation_status = "failed"
        else:
            source.active_index_revision_id = good.active_index_revision_id
    agent = SqlEvidenceAgent(research_sessions)

    with pytest.raises(ServiceError) as error:
        agent.submit(open_research(source_ids=(good.id, bad_id)))

    assert error.value.code == "RUN_SCOPE_INVALID"
    assert error.value.status_code == 422
    assert bad_id in error.value.details["invalid_source_ids"]
    assert agent.inspect(ListRuns()).items == ()


def runner_for(factory) -> AgentRunner:
    def search(request):
        with factory() as session:
            return SqlEvidenceIndex(session).search(request)
    return AgentRunner(factory, search)


def finish(agent, runner, run_id):
    for _ in range(30):
        run = agent.inspect(GetRun(run_id))
        if run.status in {RunStatus.COMPLETED, RunStatus.INSUFFICIENT_EVIDENCE, RunStatus.FAILED}:
            return run
        outcome = runner.advance_one(run_id, expected_version=run.version, execution_epoch=run.execution_epoch)
        assert outcome.applied
    raise AssertionError("Run did not terminate within its bounded test steps")


def test_comparison_reports_a_selected_source_without_adopted_evidence(research_sessions):
    first = index_source(research_sessions, title="方案A", content="延迟为 12 ms")
    second = index_source(research_sessions, title="方案B", content="延迟为 12 ms")
    third = index_source(research_sessions, title="方案C", content="资料只记录吞吐量。")
    agent = SqlEvidenceAgent(research_sessions)
    opened = agent.submit(open_research(source_ids=(first.id, second.id, third.id), kind="comparison"))

    ended = finish(agent, runner_for(research_sessions), opened.run_id)
    artifact = agent.inspect(GetArtifact(ended.final_artifact_id))

    assert ended.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert ended.termination_reason == "comparison_source_coverage_missing"
    assert artifact.kind == "evidence_gap_report"
    assert "方案C" in artifact.body_markdown
    assert "来源" in artifact.body_markdown
    assert artifact.claims == ()


def test_explicit_scope_replay_keeps_the_original_revisions_after_source_retirement(research_sessions):
    source = index_source(research_sessions, title="replay-source", content="延迟为 12 ms")
    agent = SqlEvidenceAgent(research_sessions)
    command = open_research(source_ids=(source.id,))
    opened = agent.submit(command)
    original_scope = agent.inspect(GetRun(opened.run_id)).scope_snapshot
    with research_sessions.begin() as session:
        session.get(Source, source.id).retired_at = datetime.now(UTC)

    replay = agent.submit(command)

    assert replay.replayed
    assert replay.run_id == opened.run_id
    assert agent.inspect(GetRun(opened.run_id)).scope_snapshot == original_scope


@pytest.mark.parametrize(("first", "second", "goal", "expected_status"), [
    ("方案A延迟为 12 ms", "方案B延迟为 8 ms", "延迟", "supported"),
    ("系统延迟为 12 ms", "系统超时为 8 ms", "系统", "supported"),
    ("系统延迟在2024年为 12 ms", "系统延迟在2025年为 8 ms", "系统延迟", "supported"),
    ("系统延迟为 10 至 20 ms", "系统延迟为 20 至 30 ms", "系统延迟", "supported"),
    ("系统延迟为12毫秒", "系统延迟为8毫秒", "系统延迟", "contested"),
    ("系统延迟12毫秒", "系统延迟8毫秒", "系统延迟", "contested"),
    ("系统延迟12毫秒", "系统延迟为8毫秒", "系统延迟", "contested"),
    ("系统延迟1000毫秒", "系统延迟1秒", "系统延迟", "supported"),
    ("系统成本1万元", "系统成本10000元", "系统成本", "supported"),
    ("合约金额12元", "合约金额8元", "合约金额", "contested"),
    ("方案A延迟12毫秒", "方案B延迟8毫秒", "延迟", "supported"),
    ("系统延迟12毫秒", "系统超时8毫秒", "系统", "supported"),
    ("2024年。系统延迟12毫秒", "2025年。系统延迟8毫秒", "系统延迟", "supported"),
    ("系统延迟至少12毫秒", "系统延迟至少8毫秒", "系统延迟", "supported"),
    ("系统延迟不等于12毫秒", "系统延迟不等于8毫秒", "系统延迟", "supported"),
    ("系统延迟高于12毫秒", "系统延迟高于8毫秒", "系统延迟", "supported"),
    ("系统延迟约12毫秒", "系统延迟约8毫秒", "系统延迟", "supported"),
    ("系统不会耗时12秒", "系统不会耗时8秒", "系统", "supported"),
    ("操作可能耗时12秒", "操作可能耗时8秒", "操作", "supported"),
    ("系统没有耗时12秒", "系统没有耗时8秒", "系统", "supported"),
    ("操作可能会耗时12秒", "操作可能会耗时8秒", "操作", "supported"),
    ("操作约耗时12秒", "操作约耗时8秒", "操作", "supported"),
    ("操作大概耗时12秒", "操作大概耗时8秒", "操作", "supported"),
    ("系统延迟12毫秒左右", "系统延迟8毫秒左右", "系统延迟", "supported"),
    ("系统延迟10至20毫秒", "系统延迟20至30毫秒", "系统延迟", "supported"),
    ("系统延迟为 1.0 ms", "系统延迟为 1 ms", "系统延迟", "supported"),
    ("系统延迟为 1000 ms", "系统延迟为 1 s", "系统延迟", "supported"),
    ("系统延迟不是 10 ms", "系统延迟不是 20 ms", "系统延迟", "supported"),
    ("系统成本为1万元", "系统成本为10000元", "系统成本", "supported"),
    ("system latency is 1000 ms", "system latency is 2 s", "system latency", "contested"),
    ("合约金额为12元", "合约金额为8元", "合约金额", "contested"),
    ("到账耗时为12毫秒", "到账耗时为8毫秒", "到账耗时", "contested"),
    ("合约金额约为12元", "合约金额约为8元", "合约金额", "supported"),
    ("到账耗时至少为12毫秒", "到账耗时至少为8毫秒", "到账耗时", "supported"),
    ("system under load latency is 12 ms", "system under load latency is 8 ms", "latency", "contested"),
    ("系统延迟不等于 10 ms", "系统延迟不等于 20 ms", "系统延迟", "supported"),
    ("2024年。系统延迟为12毫秒", "2025年。系统延迟为8毫秒", "系统延迟", "supported"),
    ("系统延迟最多为12毫秒", "系统延迟最多为8毫秒", "系统延迟", "supported"),
    ("系统延迟最少为12毫秒", "系统延迟最少为8毫秒", "系统延迟", "supported"),
    ("service A B latency is 12 ms", "service AB latency is 8 ms", "latency", "supported"),
    ("Plan A. System latency is 12 ms", "Plan B. System latency is 8 ms", "latency", "supported"),
    ("Under high load. System latency is 12 ms", "Under low load. System latency is 8 ms", "latency", "supported"),
    ("方案A。系统延迟为12毫秒", "方案B。系统延迟为8毫秒", "系统延迟", "supported"),
    ("Under high load. System latency is 12 ms", "Under high load. System latency is 8 ms", "latency", "contested"),
])
def test_quantitative_difference_is_contested_only_in_the_same_assertion_context(
    research_sessions, first, second, goal, expected_status,
):
    index_source(research_sessions, title="first-fact", content=first)
    index_source(research_sessions, title="second-fact", content=second)
    agent = SqlEvidenceAgent(research_sessions)
    opened = agent.submit(open_research(goal=goal))

    ended = finish(agent, runner_for(research_sessions), opened.run_id)
    artifact = agent.inspect(GetArtifact(ended.final_artifact_id))

    assert ended.status is RunStatus.COMPLETED
    assert artifact.claims[0].verification_status == expected_status
    sources = {agent.inspect(GetEvidence(evidence_id)).source_id for evidence_id in artifact.claims[0].evidence_ids}
    assert len(sources) == 2


def test_comparison_candidate_retrieval_does_not_count_as_source_coverage(research_sessions):
    first = index_source(research_sessions, title="已采纳", content="比较 延迟为 12 ms")
    candidate = index_source(research_sessions, title="仅候选", content="延迟测量方法尚未解释。")
    agent = SqlEvidenceAgent(research_sessions)
    opened = agent.submit(open_research(source_ids=(first.id, candidate.id), goal="比较 延迟", kind="comparison"))

    ended = finish(agent, runner_for(research_sessions), opened.run_id)

    assert ended.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert "仅候选" in agent.inspect(GetArtifact(ended.final_artifact_id)).body_markdown


@pytest.mark.parametrize(("kind", "source_count"), [("comparison", 3), ("comparison", 1), ("answer", 3)])
def test_covered_comparisons_and_ordinary_answers_still_complete(research_sessions, kind, source_count):
    sources = [index_source(research_sessions, title=f"covered-{number}", content="延迟为 12 ms")
               for number in range(source_count)]
    agent = SqlEvidenceAgent(research_sessions)
    opened = agent.submit(open_research(source_ids=tuple(source.id for source in sources), kind=kind))

    ended = finish(agent, runner_for(research_sessions), opened.run_id)
    artifact = agent.inspect(GetArtifact(ended.final_artifact_id))

    assert ended.status is RunStatus.COMPLETED
    assert artifact.kind == kind
    assert {agent.inspect(GetEvidence(evidence_id)).source_id for claim in artifact.claims
            for evidence_id in claim.evidence_ids} == {source.id for source in sources}


async def approval_interaction(agent, run_id):
    async for frame in agent.follow(run_id, cursor=0):
        if frame.event_type == "interaction.required":
            return frame.payload
    raise AssertionError("No public approval interaction was emitted")


def test_recovered_approved_comparison_rechecks_claim_source_coverage_before_publication(research_sessions):
    first = index_source(research_sessions, title="方案A", content="延迟为 12 ms")
    second = index_source(research_sessions, title="方案B", content="延迟为 12 ms")
    agent = SqlEvidenceAgent(research_sessions)
    runner = runner_for(research_sessions)
    opened = agent.submit(replace(
        open_research(source_ids=(first.id, second.id), kind="comparison"),
        permissions=PermissionPolicy(read_only=False),
    ))
    for _ in range(15):
        waiting = agent.inspect(GetRun(opened.run_id))
        if waiting.status is RunStatus.AWAITING_APPROVAL:
            break
        runner.advance_one(opened.run_id, expected_version=waiting.version, execution_epoch=waiting.execution_epoch)
    else:
        raise AssertionError("Expected comparison publication approval")
    interaction = asyncio.run(approval_interaction(agent, opened.run_id))
    draft_id = interaction["target"].removeprefix("artifact:")
    draft = agent.inspect(GetArtifact(draft_id))
    second_evidence_ids = [evidence_id for claim in draft.claims for evidence_id in claim.evidence_ids
                           if agent.inspect(GetEvidence(evidence_id)).source_id == second.id]
    # Simulate a historical/recovered draft whose persisted claim links lost a source.
    with research_sessions.begin() as session:
        session.execute(delete(ClaimEvidence).where(ClaimEvidence.evidence_id.in_(second_evidence_ids)))
    agent.submit(SignalRun(
        request_id="approve-comparison", run_id=opened.run_id, expected_version=waiting.version,
        signal=SignalKind.APPROVE, proposal_digest=interaction["proposal_digest"],
    ))

    ended = finish(agent, runner, opened.run_id)
    report = agent.inspect(GetArtifact(ended.final_artifact_id))

    assert ended.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert report.kind == "evidence_gap_report"
    assert "方案B" in report.body_markdown
    assert report.id == draft_id
    assert report.status == "final"
    assert report.claims == ()


def test_continuation_cannot_silently_drop_a_parent_source_that_is_now_retired(research_sessions):
    source = index_source(research_sessions, title="parent-source", content="资料尚无延迟数值。")
    agent = SqlEvidenceAgent(research_sessions)
    opened = agent.submit(open_research(source_ids=(source.id,), goal="aurora latency"))
    parent = finish(agent, runner_for(research_sessions), opened.run_id)
    assert parent.status is RunStatus.INSUFFICIENT_EVIDENCE
    with research_sessions.begin() as session:
        session.get(Source, source.id).retired_at = datetime.now(UTC)

    with pytest.raises(ServiceError) as error:
        agent.submit(ContinueRun(
            request_id="continue-retired", source_run_id=parent.id, gap_artifact_id=parent.final_artifact_id,
        ))

    assert error.value.code == "RUN_SCOPE_INVALID"
    assert [run.id for run in agent.inspect(ListRuns()).items] == [parent.id]


def test_explicit_selection_keeps_legacy_active_index_resolution(research_sessions):
    source = index_source(research_sessions, title="legacy-index-pointer", content="延迟为 12 ms")
    with research_sessions.begin() as session:
        session.get(Source, source.id).active_index_revision_id = None
    agent = SqlEvidenceAgent(research_sessions)

    opened = agent.submit(open_research(source_ids=(source.id,)))

    pinned = agent.inspect(GetRun(opened.run_id)).scope_snapshot.revisions
    assert len(pinned) == 1
    assert pinned[0].index_revision_id == source.active_index_revision_id


def test_model_adopting_semantic_candidates_cannot_hide_their_quantitative_conflict(research_sessions):
    first = index_source(research_sessions, title="semantic-first", content="系统延迟为12毫秒")
    second = index_source(research_sessions, title="semantic-second", content="系统延迟为8毫秒")
    hits = tuple(_hit_for_source(research_sessions, title=source.title) for source in (first, second))
    plan = AgentModelResult(
        value=PlanDecision(requirements=[RequirementProposal(text="system performance", kind="comparative")]),
        usage=AgentModelUsage(), provider="recording", model="recording-agent-v1",
    )
    synthesis = AgentModelResult(
        value=SynthesisDecision(claims=[ClaimProposal(requirement_ordinal=1, text="系统延迟为12毫秒")]),
        usage=AgentModelUsage(), provider="recording", model="recording-agent-v1",
    )
    model = _SelectingAgentModel(
        plans=(plan,), syntheses=(synthesis,),
        select=lambda request: [{
            "requirement_ordinal": requirement.ordinal,
            "supporting_evidence_ids": [item.evidence_id for item in requirement.evidence],
        } for requirement in request.requirements if requirement.status == "partial"],
    )
    agent = SqlEvidenceAgent(research_sessions)
    runner = AgentRunner(research_sessions, lambda _request: EvidenceSearchResult(hits=hits), agent_model=model)
    opened = agent.submit(replace(
        open_research(source_ids=(first.id, second.id), goal="system performance", kind="comparison"),
        mode=RunMode.FORCE_AGENT,
    ))

    ended = finish(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(ended.final_artifact_id))

    assert ended.status is RunStatus.COMPLETED
    assert artifact.kind == "comparison"
    assert artifact.claims[0].verification_status == "contested"
    assert artifact.claims[0].resolution_status == "unresolved"
    assert artifact.claims[0].confidence_millis == 250
    assert "冲突" in artifact.claims[0].text
