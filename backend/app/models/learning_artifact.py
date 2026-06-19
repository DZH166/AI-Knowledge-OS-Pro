from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LearningArtifact(Base):
    __tablename__ = "learning_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("multimodal_chunks.id"), nullable=True, index=True)
    document_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id"), nullable=True, index=True)
    locator_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("learning_cards.id"), nullable=True)
    quiz_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_questions.id"), nullable=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("learning_notes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
