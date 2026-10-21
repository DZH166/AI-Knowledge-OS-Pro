from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class QALog(Base):
    __tablename__ = "qa_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    citations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    related_chunks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    used_citation_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    answer_confidence: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieval_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    runtime_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="real")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    space = relationship("KnowledgeSpace", back_populates="qa_logs")
