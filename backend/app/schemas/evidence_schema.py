from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictEvidenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactClaimSchema(StrictEvidenceSchema):
    id: str
    ordinal: int
    text: str
    kind: str
    verification_status: str
    evidence_ids: list[str]


class ArtifactSchema(StrictEvidenceSchema):
    schema_version: Literal[1] = 1
    id: str
    producing_run_id: str
    kind: str
    title: str
    body_markdown: str
    status: str
    claims: list[ArtifactClaimSchema]


class EvidenceReferenceSchema(StrictEvidenceSchema):
    schema_version: Literal[1] = 1
    id: str
    run_id: str
    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    source_type: str
    locator: dict[str, object]
    revision_content_hash: str
    content_hash: str
    excerpt_preview: str
    claim_ids: list[str]


class ArtifactSummarySchema(StrictEvidenceSchema):
    id: str
    producing_run_id: str
    kind: str
    title: str
    status: str


class ArtifactCatalogSchema(StrictEvidenceSchema):
    schema_version: Literal[1] = 1
    items: list[ArtifactSummarySchema]
