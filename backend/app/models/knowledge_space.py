from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents = relationship("Document", back_populates="space", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="space", cascade="all, delete-orphan")
    qa_logs = relationship("QALog", back_populates="space", cascade="all, delete-orphan")

