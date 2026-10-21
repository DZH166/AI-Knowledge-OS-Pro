from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OptimizationStudy(Base):
    __tablename__ = "optimization_studies"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_optimization_studies_request_id"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'cancelled', 'failed')",
            name="ck_optimization_studies_status",
        ),
        CheckConstraint(
            "objective IN ('quality_first', 'balanced', 'cost_first')",
            name="ck_optimization_studies_objective",
        ),
        CheckConstraint("seed >= 0", name="ck_optimization_studies_seed_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    request_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    objective: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    base_policy_id: Mapped[str] = mapped_column(
        ForeignKey("agent_policy_versions.id"),
        nullable=False,
        index=True,
    )
    search_space_json: Mapped[str] = mapped_column(Text, nullable=False)
    weights_json: Mapped[str] = mapped_column(Text, nullable=False)
    budget_json: Mapped[str] = mapped_column(Text, nullable=False)
    budget_usage_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    base_policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OptimizationTrial(Base):
    __tablename__ = "optimization_trials"
    __table_args__ = (
        UniqueConstraint("study_id", "ordinal", name="uq_optimization_trials_study_ordinal"),
        UniqueConstraint("evaluation_id", name="uq_optimization_trials_evaluation_id"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completing', 'completed', 'failed', 'cancelled')",
            name="ck_optimization_trials_status",
        ),
        CheckConstraint("ordinal >= 1", name="ck_optimization_trials_ordinal_positive"),
        CheckConstraint("attempt >= 0", name="ck_optimization_trials_attempt_non_negative"),
        CheckConstraint("is_baseline IN (0, 1)", name="ck_optimization_trials_baseline_flag"),
        CheckConstraint("dominated IN (0, 1)", name="ck_optimization_trials_dominated_flag"),
        CheckConstraint(
            "score_millis IS NULL OR (score_millis >= 0 AND score_millis <= 1000)",
            name="ck_optimization_trials_score_millis",
        ),
        CheckConstraint(
            "external_provider_calls IS NULL OR external_provider_calls = 0",
            name="ck_optimization_trials_provider_calls_zero",
        ),
        CheckConstraint(
            "recommendation_rank IS NULL OR recommendation_rank >= 1",
            name="ck_optimization_trials_recommendation_rank",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_studies.id"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_policy_versions.id"),
        nullable=True,
        index=True,
    )
    evaluation_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_evaluations.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    config_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_baseline: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_millis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_provider_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dominated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendation_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
