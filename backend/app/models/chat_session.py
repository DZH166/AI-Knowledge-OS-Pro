from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="新的知识问答")
    answer_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    qa_log_id: Mapped[int | None] = mapped_column(ForeignKey("qa_logs.id"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    citations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    used_citation_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    related_chunks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    retrieval_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    answer_confidence: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")
