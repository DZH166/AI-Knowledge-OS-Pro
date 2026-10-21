from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentEvidence(Base):
    __tablename__ = "agent_evidence"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "revision_id", "chunk_id", "locator_digest", name="uq_agent_evidence_identity"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("source_revisions.id"), nullable=False, index=True)
    index_revision_id: Mapped[int] = mapped_column(ForeignKey("index_revisions.id"), nullable=False, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("multimodal_chunks.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    locator_json: Mapped[str] = mapped_column(Text, nullable=False)
    locator_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    excerpt_preview: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_by_tool_call_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_tool_calls.id"), nullable=True, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    trust_level: Mapped[str] = mapped_column(String(30), nullable=False, default="untrusted")
    active_at_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequirementEvidence(Base):
    __tablename__ = "requirement_evidence"
    __table_args__ = (
        UniqueConstraint("requirement_id", "evidence_id", "relation", name="uq_requirement_evidence_relation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("agent_requirements.id"), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("agent_evidence.id"), nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence_millis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    producing_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentClaim(Base):
    __tablename__ = "agent_claims"
    __table_args__ = (UniqueConstraint("artifact_id", "ordinal", name="uq_agent_claim_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("agent_artifacts.id"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        UniqueConstraint("claim_id", "evidence_id", "relation", name="uq_claim_evidence_relation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("agent_claims.id"), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("agent_evidence.id"), nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    verifier_method: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence_millis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
