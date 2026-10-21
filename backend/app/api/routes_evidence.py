from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.evidence_agent.contracts import GetArtifact, GetEvidence, ListArtifacts
from app.modules.evidence_agent.interface import EvidenceAgent
from app.modules.evidence_agent.wiring import get_evidence_agent
from app.schemas.evidence_schema import ArtifactCatalogSchema, ArtifactSchema, EvidenceReferenceSchema


router = APIRouter(prefix="/v1", tags=["evidence-agent"])
AgentDependency = Annotated[EvidenceAgent, Depends(get_evidence_agent)]


@router.get("/artifacts", response_model=ArtifactCatalogSchema)
def list_artifacts(
    agent: AgentDependency,
    space_id: Annotated[int | None, Query(gt=0)] = None,
    source_id: Annotated[int | None, Query(gt=0)] = None,
    run_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ArtifactCatalogSchema:
    catalog = agent.inspect(
        ListArtifacts(
            space_id=space_id,
            source_id=source_id,
            run_id=run_id,
            limit=limit,
        )
    )
    return ArtifactCatalogSchema(
        items=[
            {
                "id": item.id,
                "producing_run_id": item.producing_run_id,
                "kind": item.kind,
                "title": item.title,
                "status": item.status,
            }
            for item in catalog.items
        ]
    )


@router.get("/artifacts/{artifact_id}", response_model=ArtifactSchema)
def get_artifact(artifact_id: str, agent: AgentDependency) -> ArtifactSchema:
    artifact = agent.inspect(GetArtifact(artifact_id))
    return ArtifactSchema.model_validate(
        {
            "schema_version": artifact.schema_version,
            "id": artifact.id,
            "producing_run_id": artifact.producing_run_id,
            "kind": artifact.kind,
            "title": artifact.title,
            "body_markdown": artifact.body_markdown,
            "status": artifact.status,
            "claims": [
                {
                    "id": claim.id,
                    "ordinal": claim.ordinal,
                    "text": claim.text,
                    "kind": claim.kind,
                    "verification_status": claim.verification_status,
                    "evidence_ids": list(claim.evidence_ids),
                }
                for claim in artifact.claims
            ],
        }
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceReferenceSchema)
def get_evidence(evidence_id: str, agent: AgentDependency) -> EvidenceReferenceSchema:
    evidence = agent.inspect(GetEvidence(evidence_id))
    return EvidenceReferenceSchema(
        id=evidence.id,
        run_id=evidence.run_id,
        source_id=evidence.source_id,
        revision_id=evidence.revision_id,
        index_revision_id=evidence.index_revision_id,
        chunk_id=evidence.chunk_id,
        source_type=evidence.source_type,
        locator=dict(evidence.locator),
        revision_content_hash=evidence.revision_content_hash,
        content_hash=evidence.content_hash,
        excerpt_preview=evidence.excerpt_preview,
        claim_ids=list(evidence.claim_ids),
    )
