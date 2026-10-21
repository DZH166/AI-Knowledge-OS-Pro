"""V5.2 durable Agent evaluation control center.

Revision ID: 0009_v5_2_agent_control
Revises: 0008_v5_agent_runtime
Create Date: 2026-08-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_v5_2_agent_control"
down_revision = "0008_v5_agent_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=True),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("dataset_name", sa.String(length=120), nullable=True),
        sa.Column("dataset_path", sa.String(length=255), nullable=True),
        sa.Column("dataset_sha256", sa.String(length=64), nullable=True),
        sa.Column("evaluator_sha256", sa.String(length=64), nullable=True),
        sa.Column("report_sha256", sa.String(length=64), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("case_pass_rate_millis", sa.Integer(), nullable=True),
        sa.Column("external_provider_calls", sa.Integer(), nullable=True),
        sa.Column("failure_case_count", sa.Integer(), nullable=False),
        sa.Column("category_counts_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("hard_gates_json", sa.Text(), nullable=False),
        sa.Column("failure_case_ids_json", sa.Text(), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=True),
        sa.Column("provider_boundary", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'passed', 'failed')",
            name="ck_agent_evaluations_status",
        ),
        sa.CheckConstraint("attempt >= 0", name="ck_agent_evaluations_attempt_non_negative"),
        sa.CheckConstraint("case_count >= 0", name="ck_agent_evaluations_case_count_non_negative"),
        sa.CheckConstraint(
            "external_provider_calls IS NULL OR external_provider_calls >= 0",
            name="ck_agent_evaluations_provider_calls_non_negative",
        ),
        sa.CheckConstraint(
            "case_pass_rate_millis IS NULL OR "
            "(case_pass_rate_millis >= 0 AND case_pass_rate_millis <= 1000)",
            name="ck_agent_evaluations_pass_rate_millis",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_agent_evaluations_request_id"),
    )
    for name, columns in (
        ("ix_agent_evaluations_request_id", ("request_id",)),
        ("ix_agent_evaluations_status", ("status",)),
        ("ix_agent_evaluations_policy_fingerprint", ("policy_fingerprint",)),
        ("ix_agent_evaluations_dataset_sha256", ("dataset_sha256",)),
        ("ix_agent_evaluations_lease_expires_at", ("lease_expires_at",)),
        ("ix_agent_evaluations_created_at", ("created_at",)),
    ):
        op.create_index(name, "agent_evaluations", list(columns), unique=False)


def downgrade() -> None:
    op.drop_table("agent_evaluations")
