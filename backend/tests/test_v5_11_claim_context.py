from __future__ import annotations

import asyncio
from hashlib import sha256

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.source import Source
from app.modules.evidence_agent.claim_verifier import (
    ClaimVerificationRequest,
    DeterministicClaimVerifier,
)
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
)
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.service import SqlEvidenceAgent
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
    ClaimProposal,
    PlanDecision,
    RecordingAgentModel,
    RequirementProposal,
    SufficiencyDecision,
    SynthesisDecision,
)


@pytest.mark.parametrize(
    "evidence",
    [
        "Under high load. Alpha latency is 12 ms.",
        "In the year 2024; Alpha latency is 12 ms.",
        "For Plan A. Alpha latency is 12 ms.",
        "Under high load, Alpha latency is 12 ms.",
        "## Plan A\nAlpha latency is 12 ms.",
        "2024\nAlpha latency is 12 ms.",
        "在高负载下。Alpha latency is 12 ms.",
    ],
)
def test_preceding_context_does_not_prove_unqualified_numeric_claim(evidence: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(
            claim="Alpha latency is 12 ms.",
            evidence=(evidence,),
        )
    )

    assert result.entailed is False
    assert result.confidence_millis == 0


@pytest.mark.parametrize(
    ("evidence", "claim", "entailed"),
    [
        (("Under high load.", "Alpha latency is 12 milliseconds."), "Alpha delay is below 20 ms.", True),
        (("For Plan A.", "Alpha latency is 12 ms."), "For Plan A. Alpha latency is 12 ms.", False),
        (("In the year 2024.", "Alpha latency is 12 ms."), "In the year 2024. Alpha latency is 12 ms.", False),
    ],
)
def test_evidence_items_cannot_supply_each_others_context(
    evidence: tuple[str, ...], claim: str, entailed: bool
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=evidence)
    )

    # The standalone measurement proves a bound, but separate excerpts cannot
    # be joined to manufacture a plan/year scope for that measurement.
    assert result.entailed is entailed


@pytest.mark.parametrize(
    "evidence",
    [
        "Under high load. Alpha supports offline caching.",
        "In the year 2024; Alpha supports offline caching.",
        "For Plan A. Alpha supports offline caching.",
        "在高负载下。Alpha supports offline caching.",
    ],
)
def test_preceding_context_does_not_prove_unqualified_nonnumeric_claim(evidence: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(
            claim="Alpha supports offline caching.",
            evidence=(evidence,),
        )
    )

    assert result.entailed is False
    assert result.confidence_millis == 0


@pytest.mark.parametrize(
    "excerpt",
    [
        "For Plan A.\nAlpha latency is 12 ms.",
        "In the year 2024;\nAlpha latency is 12 ms.",
        "Under high load.\nAlpha supports offline caching.",
    ],
)
def test_full_context_remains_supported_when_whitespace_is_normalized(excerpt: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=" ".join(excerpt.split()), evidence=(excerpt,))
    )

    assert result.entailed is True
    assert result.confidence_millis == 1000
    assert result.reason_code == "literal_entailment"


@pytest.mark.parametrize(
    "excerpt",
    [
        "Under high load. Alpha latency is 12 ms.",
        "In the year 2024; Alpha latency is 12 ms.",
        "For Plan A. Alpha latency is 12 ms.",
    ],
)
def test_agent_preserves_qualified_excerpt_when_recorded_model_drops_context(
    db_session, knowledge_space, excerpt: str
) -> None:
    source = Source(
        space_id=knowledge_space.id,
        source_type="document",
        title="Alpha latency",
        status="uploaded",
        file_size=len(excerpt),
    )
    db_session.add(source)
    db_session.commit()
    index = SqlEvidenceIndex(db_session)
    staged = index.command(
        StageRevision(
            command_id="stage-qualified-evidence",
            draft=RevisionDraft(
                source_id=source.id,
                content_hash=sha256(excerpt.encode()).hexdigest(),
                index_version="v511-claim-context-test",
                collection_name="v511-claim-context-test",
                chunks=(
                    ChunkDraft(
                        chunk_index=0,
                        modality="text",
                        content=excerpt,
                        locator={"kind": "text", "heading": "Alpha latency"},
                    ),
                ),
            ),
        )
    )
    revision = index.query(GetRevision(staged.revision_id))
    index.command(
        ActivateRevision(
            command_id="activate-qualified-evidence",
            revision_id=staged.revision_id,
            verified_points=tuple(
                VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                for point in revision.points
            ),
        )
    )
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
                    claims=[ClaimProposal(requirement_ordinal=1, text="Alpha latency is 12 ms.")],
                    summary="recorded model discards the evidence qualifier",
                ),
                usage=AgentModelUsage(),
                provider="recording",
                model="recording-agent-v1",
            ),
        ),
    )
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    agent = SqlEvidenceAgent(factory)

    def search(request):
        with factory() as session:
            return SqlEvidenceIndex(session).search(request)

    runner = AgentRunner(factory, search, agent_model=model)
    opened = agent.submit(
        OpenRun(
            request_id="qualified-claim-fallback",
            space_id=knowledge_space.id,
            goal="What is Alpha latency?",
            scope=ScopeSelector(),
            deliverable=DeliverableSpec(kind="answer"),
            mode=RunMode.FORCE_AGENT,
            budget=BudgetLimits(max_steps=8, max_tool_calls=4, max_model_calls=4),
            permissions=PermissionPolicy(read_only=True),
            provider_mode="recording",
        )
    )
    terminal = {
        RunStatus.COMPLETED,
        RunStatus.INSUFFICIENT_EVIDENCE,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    }
    for _ in range(20):
        run = agent.inspect(GetRun(opened.run_id))
        if run.status in terminal:
            break
        advanced = runner.advance_one(
            run.id,
            expected_version=run.version,
            execution_epoch=run.execution_epoch,
        )
        assert advanced.applied is True
    else:
        pytest.fail("Recorded run did not reach a terminal state.")

    assert run.status is RunStatus.COMPLETED
    assert run.final_artifact_id is not None
    artifact = agent.inspect(GetArtifact(run.final_artifact_id))
    assert len(artifact.claims) == 1
    claim = artifact.claims[0]
    assert claim.text == excerpt
    assert claim.verification_status == "supported"
    assert 0 < claim.confidence_millis <= 1000
    assert len(claim.evidence_ids) == 1
    evidence = agent.inspect(GetEvidence(claim.evidence_ids[0]))
    assert evidence.excerpt_preview == excerpt
    assert evidence.source_id == source.id
    assert evidence.revision_id == staged.revision_id
    assert excerpt in artifact.body_markdown

    async def public_events():
        return [frame async for frame in agent.follow(opened.run_id, cursor=0)]

    finalized = next(
        frame for frame in asyncio.run(public_events()) if frame.event_type == "artifact.finalized"
    )
    assert finalized.payload["rejected_model_claims"] == 1
