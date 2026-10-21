from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LearningLog(Base):
    __tablename__ = "learning_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    version_name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    implemented_features_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    major_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    knowledge_points_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    focus: Mapped[str] = mapped_column(Text, nullable=False)
    review_suggestions: Mapped[str] = mapped_column(Text, nullable=False)
    interview_expression: Mapped[str] = mapped_column(Text, nullable=False)
    next_version_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

