from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_agent_runs_version_positive"),
        CheckConstraint("execution_epoch >= 0", name="ck_agent_runs_epoch_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    requested_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    effective_mode: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scope_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    scope_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    deliverable_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    policy_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    budget_limits_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    budget_usage_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    provider_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    current_plan_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_gate_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    final_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    termination_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    active_elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentPlan(Base):
    __tablename__ = "agent_plans"
    __table_args__ = (UniqueConstraint("run_id", "version", name="uq_agent_plan_run_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRequirement(Base):
    __tablename__ = "agent_requirements"
    __table_args__ = (
        UniqueConstraint("run_id", "plan_version", "ordinal", name="uq_agent_requirement_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    depends_on_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uncovered", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentGate(Base):
    __tablename__ = "agent_gates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    proposed_tool_call_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    arguments_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    __table_args__ = (UniqueConstraint("run_id", "invocation_key", name="uq_agent_tool_invocation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    invocation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    tool_version: Mapped[str] = mapped_column(String(40), nullable=False)
    effect: Mapped[str] = mapped_column(String(40), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    execution_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentModelCall(Base):
    __tablename__ = "agent_model_calls"
    __table_args__ = (UniqueConstraint("run_id", "invocation_key", name="uq_agent_model_invocation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    invocation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_estimated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
