from datetime import datetime
import json

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ErrorArchive(Base):
    __tablename__ = "error_archives"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("multimodal_chunks.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    error_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", index=True)
    detection_method: Mapped[str] = mapped_column(String(80), nullable=False, default="ocr_pattern")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suggested_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source = relationship("Source")
    chunk = relationship("MultimodalChunk")

    @property
    def suggested_actions(self) -> list[str]:
        return self._string_list(self.suggested_actions_json)

    @property
    def tags(self) -> list[str]:
        return self._string_list(self.tags_json)

    @staticmethod
    def _string_list(value: str) -> list[str]:
        try:
            parsed = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
