from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentEvaluation(Base):
    __tablename__ = "agent_evaluations"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_agent_evaluations_request_id"),
        CheckConstraint(
            "status IN ('queued', 'running', 'passed', 'failed')",
            name="ck_agent_evaluations_status",
        ),
        CheckConstraint("attempt >= 0", name="ck_agent_evaluations_attempt_non_negative"),
        CheckConstraint("case_count >= 0", name="ck_agent_evaluations_case_count_non_negative"),
        CheckConstraint(
            "external_provider_calls IS NULL OR external_provider_calls >= 0",
            name="ck_agent_evaluations_provider_calls_non_negative",
        ),
        CheckConstraint(
            "case_pass_rate_millis IS NULL OR "
            "(case_pass_rate_millis >= 0 AND case_pass_rate_millis <= 1000)",
            name="ck_agent_evaluations_pass_rate_millis",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    request_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False, default="deterministic_recording")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    schema_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dataset_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    evaluator_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    case_pass_rate_millis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_provider_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category_counts_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    hard_gates_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    failure_case_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_boundary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Deterministic recording only; not a real-model quality benchmark.",
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
