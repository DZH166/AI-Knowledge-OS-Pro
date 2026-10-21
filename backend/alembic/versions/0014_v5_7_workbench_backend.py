"""V5.7 workbench backend: study events and agent run share links.

Revision ID: 0014_v5_7_workbench_backend
Revises: 0013_v5_6_bayesian_optimizer
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_v5_7_workbench_backend"
down_revision = "0013_v5_6_bayesian_optimizer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_study_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "event_type IN ('study_created','study_started','trial_created','trial_completed',"
            "'trial_failed','trial_cancelled','round_started','recommendation_updated',"
            "'study_completed','study_failed','study_cancelled','draft_converted')",
            name="ck_optimization_study_events_type",
        ),
        sa.CheckConstraint("round_no >= 1", name="ck_optimization_study_events_round_no"),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["optimization_studies.id"],
            name="fk_optimization_study_events_study_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_optimization_study_events_study_id",
        "optimization_study_events",
        ["study_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_study_events_created_at",
        "optimization_study_events",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "agent_run_share_links",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_agent_run_share_links_expiry_after_creation"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name="fk_agent_run_share_links_run_id",
        ),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_agent_run_share_links_run_id",
        "agent_run_share_links",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_share_links_run_id", table_name="agent_run_share_links")
    op.drop_table("agent_run_share_links")
    op.drop_index("ix_optimization_study_events_created_at", table_name="optimization_study_events")
    op.drop_index("ix_optimization_study_events_study_id", table_name="optimization_study_events")
    op.drop_table("optimization_study_events")
