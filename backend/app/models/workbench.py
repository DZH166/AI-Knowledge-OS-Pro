from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OptimizationStudyEvent(Base):
    __tablename__ = "optimization_study_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('study_created','study_started','trial_created','trial_completed',"
            "'trial_failed','trial_cancelled','round_started','recommendation_updated',"
            "'study_completed','study_failed','study_cancelled','draft_converted')",
            name="ck_optimization_study_events_type",
        ),
        CheckConstraint("round_no >= 1", name="ck_optimization_study_events_round_no"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_studies.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class AgentRunShareLink(Base):
    __tablename__ = "agent_run_share_links"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_run_share_links_expiry_after_creation",
        ),
    )

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
