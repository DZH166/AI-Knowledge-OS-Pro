from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentCommand(Base):
    __tablename__ = "agent_commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("run_id", "run_sequence", name="uq_agent_event_run_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    run_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public", index=True)
    step_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    __table_args__ = (UniqueConstraint("run_id", "run_version", name="uq_agent_checkpoint_run_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_event_cursor: Mapped[int] = mapped_column(Integer, nullable=False)
    state_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    execution_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
