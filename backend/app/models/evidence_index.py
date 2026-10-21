from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class IndexOperation(Base):
    __tablename__ = "index_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    command_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    revision_id: Mapped[int | None] = mapped_column(ForeignKey("source_revisions.id"), nullable=True, index=True)
    index_revision_id: Mapped[int | None] = mapped_column(ForeignKey("index_revisions.id"), nullable=True, index=True)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    draft_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parser_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    points = relationship("VectorPointManifest", back_populates="operation", cascade="all, delete-orphan")


class VectorPointManifest(Base):
    __tablename__ = "vector_point_manifests"
    __table_args__ = (
        UniqueConstraint("collection_name", "point_id", name="uq_vector_manifest_collection_point"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("index_operations.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("source_revisions.id"), nullable=False, index=True)
    index_revision_id: Mapped[int] = mapped_column(ForeignKey("index_revisions.id"), nullable=False, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("multimodal_chunks.id"), nullable=False, index=True)
    collection_name: Mapped[str] = mapped_column(String(160), nullable=False)
    point_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="expected", index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    operation = relationship("IndexOperation", back_populates="points")
