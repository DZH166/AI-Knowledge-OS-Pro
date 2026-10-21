from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ResearchFeedback(Base):
    __tablename__ = "research_feedback"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="ck_feedback_status"),
        CheckConstraint("version >= 1", name="ck_feedback_version"),
        CheckConstraint("issue IN ('missing_evidence', 'incorrect_answer', 'unsupported_citation', 'incomplete_answer')",
                        name="ck_feedback_issue"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("agent_artifacts.id"), nullable=False, index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("agent_claims.id"), nullable=True)
    provider_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    issue: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_request_id: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    review_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeedbackSample(Base):
    __tablename__ = "feedback_samples"
    __table_args__ = (CheckConstraint("split IN ('tuning', 'holdout')", name="ck_feedback_sample_split"),)

    feedback_id: Mapped[int] = mapped_column(ForeignKey("research_feedback.id"), primary_key=True)
    split: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
