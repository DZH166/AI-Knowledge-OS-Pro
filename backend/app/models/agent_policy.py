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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentPolicyVersion(Base):
    __tablename__ = "agent_policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_key", "version", name="uq_agent_policy_versions_key_version"),
        CheckConstraint("version >= 1", name="ck_agent_policy_versions_version_positive"),
        CheckConstraint("config_schema_version = 1", name="ck_agent_policy_versions_config_schema"),
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_agent_policy_versions_status",
        ),
        CheckConstraint(
            "has_been_active IN (0, 1)",
            name="ck_agent_policy_versions_active_flag",
        ),
        Index(
            "uq_agent_policy_versions_single_active",
            "status",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    config_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    config_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_policy_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_policy_versions.id"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    has_been_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentPolicyCommand(Base):
    __tablename__ = "agent_policy_commands"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_agent_policy_commands_request_id"),
        CheckConstraint(
            "command_type IN ('create', 'activate', 'rollback')",
            name="ck_agent_policy_commands_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class AgentPolicyActivation(Base):
    __tablename__ = "agent_policy_activations"
    __table_args__ = (
        UniqueConstraint("command_id", name="uq_agent_policy_activations_command_id"),
        CheckConstraint(
            "action IN ('activate', 'rollback')",
            name="ck_agent_policy_activations_action",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    command_id: Mapped[str] = mapped_column(
        ForeignKey("agent_policy_commands.id"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("agent_policy_versions.id"),
        nullable=False,
        index=True,
    )
    previous_policy_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_policy_versions.id"),
        nullable=True,
        index=True,
    )
    evaluation_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_evaluations.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
