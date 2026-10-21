"""V5.3 versioned Agent policy and adaptive retrieval snapshots.

Revision ID: 0010_v5_3_agent_policy
Revises: 0009_v5_2_agent_control
Create Date: 2026-08-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_v5_3_agent_policy"
down_revision = "0009_v5_2_agent_control"
branch_labels = None
depends_on = None

DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_POLICY_JSON = (
    '{"comparative_top_k":14,"factual_top_k":8,"max_hits_per_source":3,'
    '"minimum_score_millis":0,"neighbor_after":1,"neighbor_before":1,'
    '"schema_version":1,"temporal_top_k":12}'
)
DEFAULT_POLICY_SHA256 = "1f6f3b9ca28a2619d1efa22d6a79250306764719403d7092792aad45e130a7a3"


def upgrade() -> None:
    op.create_table(
        "agent_policy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("config_schema_version", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("config_sha256", sa.String(length=64), nullable=False),
        sa.Column("base_policy_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("has_been_active", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "has_been_active IN (0, 1)",
            name="ck_agent_policy_versions_active_flag",
        ),
        sa.CheckConstraint(
            "config_schema_version = 1",
            name="ck_agent_policy_versions_config_schema",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_agent_policy_versions_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_agent_policy_versions_version_positive"),
        sa.ForeignKeyConstraint(
            ["base_policy_id"],
            ["agent_policy_versions.id"],
            name="fk_agent_policy_versions_base_policy_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_key",
            "version",
            name="uq_agent_policy_versions_key_version",
        ),
    )
    for name, columns in (
        ("ix_agent_policy_versions_policy_key", ("policy_key",)),
        ("ix_agent_policy_versions_status", ("status",)),
        ("ix_agent_policy_versions_config_sha256", ("config_sha256",)),
        ("ix_agent_policy_versions_base_policy_id", ("base_policy_id",)),
        ("ix_agent_policy_versions_created_at", ("created_at",)),
    ):
        op.create_index(name, "agent_policy_versions", list(columns), unique=False)
    op.create_index(
        "uq_agent_policy_versions_single_active",
        "agent_policy_versions",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "agent_policy_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("command_type", sa.String(length=20), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "command_type IN ('create', 'activate', 'rollback')",
            name="ck_agent_policy_commands_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_agent_policy_commands_request_id"),
    )
    for name, columns in (
        ("ix_agent_policy_commands_request_id", ("request_id",)),
        ("ix_agent_policy_commands_command_type", ("command_type",)),
        ("ix_agent_policy_commands_created_at", ("created_at",)),
    ):
        op.create_index(name, "agent_policy_commands", list(columns), unique=False)

    op.create_table(
        "agent_policy_activations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("command_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=False),
        sa.Column("previous_policy_id", sa.String(length=36), nullable=True),
        sa.Column("evaluation_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "action IN ('activate', 'rollback')",
            name="ck_agent_policy_activations_action",
        ),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["agent_policy_commands.id"],
            name="fk_agent_policy_activations_command_id",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["agent_evaluations.id"],
            name="fk_agent_policy_activations_evaluation_id",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["agent_policy_versions.id"],
            name="fk_agent_policy_activations_policy_id",
        ),
        sa.ForeignKeyConstraint(
            ["previous_policy_id"],
            ["agent_policy_versions.id"],
            name="fk_agent_policy_activations_previous_policy_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id", name="uq_agent_policy_activations_command_id"),
    )
    for name, columns in (
        ("ix_agent_policy_activations_command_id", ("command_id",)),
        ("ix_agent_policy_activations_action", ("action",)),
        ("ix_agent_policy_activations_policy_id", ("policy_id",)),
        ("ix_agent_policy_activations_previous_policy_id", ("previous_policy_id",)),
        ("ix_agent_policy_activations_evaluation_id", ("evaluation_id",)),
        ("ix_agent_policy_activations_created_at", ("created_at",)),
    ):
        op.create_index(name, "agent_policy_activations", list(columns), unique=False)

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("decision_policy_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("decision_policy_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("decision_policy_fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("decision_policy_snapshot_json", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_runs_decision_policy_id",
            "agent_policy_versions",
            ["decision_policy_id"],
            ["id"],
        )
    op.create_index("ix_agent_runs_decision_policy_id", "agent_runs", ["decision_policy_id"], unique=False)
    op.create_index(
        "ix_agent_runs_decision_policy_fingerprint",
        "agent_runs",
        ["decision_policy_fingerprint"],
        unique=False,
    )

    with op.batch_alter_table("agent_evaluations") as batch_op:
        batch_op.add_column(sa.Column("policy_version_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("policy_snapshot_json", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_evaluations_policy_version_id",
            "agent_policy_versions",
            ["policy_version_id"],
            ["id"],
        )
    op.create_index(
        "ix_agent_evaluations_policy_version_id",
        "agent_evaluations",
        ["policy_version_id"],
        unique=False,
    )

    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO agent_policy_versions (
                id, policy_key, version, label, status, config_schema_version,
                config_json, config_sha256, base_policy_id, created_by,
                has_been_active, activated_at
            ) VALUES (
                :id, 'default-research', 1, 'Balanced evidence retrieval', 'active', 1,
                :config_json, :config_sha256, NULL, 'system:migration', 1, CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": DEFAULT_POLICY_ID,
            "config_json": DEFAULT_POLICY_JSON,
            "config_sha256": DEFAULT_POLICY_SHA256,
        },
    )


def downgrade() -> None:
    op.drop_index("ix_agent_evaluations_policy_version_id", table_name="agent_evaluations")
    with op.batch_alter_table("agent_evaluations") as batch_op:
        batch_op.drop_constraint("fk_agent_evaluations_policy_version_id", type_="foreignkey")
        batch_op.drop_column("policy_snapshot_json")
        batch_op.drop_column("policy_version_id")

    op.drop_index("ix_agent_runs_decision_policy_fingerprint", table_name="agent_runs")
    op.drop_index("ix_agent_runs_decision_policy_id", table_name="agent_runs")
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("fk_agent_runs_decision_policy_id", type_="foreignkey")
        batch_op.drop_column("decision_policy_snapshot_json")
        batch_op.drop_column("decision_policy_fingerprint")
        batch_op.drop_column("decision_policy_version")
        batch_op.drop_column("decision_policy_id")

    op.drop_table("agent_policy_activations")
    op.drop_table("agent_policy_commands")
    op.drop_table("agent_policy_versions")
