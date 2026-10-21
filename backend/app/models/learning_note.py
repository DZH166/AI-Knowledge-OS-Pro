from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LearningNote(Base):
    __tablename__ = "learning_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    qa_log_id: Mapped[int | None] = mapped_column(ForeignKey("qa_logs.id"), nullable=True, index=True)
    version_slug: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
