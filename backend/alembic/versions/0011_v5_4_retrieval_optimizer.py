"""V5.4A offline retrieval optimizer studies and trials.

Revision ID: 0011_v5_4_retrieval_optimizer
Revises: 0010_v5_3_agent_policy
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_v5_4_retrieval_optimizer"
down_revision = "0010_v5_3_agent_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_studies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("objective", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("base_policy_id", sa.String(length=36), nullable=False),
        sa.Column("search_space_json", sa.Text(), nullable=False),
        sa.Column("weights_json", sa.Text(), nullable=False),
        sa.Column("budget_json", sa.Text(), nullable=False),
        sa.Column("budget_usage_json", sa.Text(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column("base_policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'cancelled', 'failed')",
            name="ck_optimization_studies_status",
        ),
        sa.CheckConstraint(
            "objective IN ('quality_first', 'balanced', 'cost_first')",
            name="ck_optimization_studies_objective",
        ),
        sa.CheckConstraint("seed >= 0", name="ck_optimization_studies_seed_non_negative"),
        sa.ForeignKeyConstraint(
            ["base_policy_id"],
            ["agent_policy_versions.id"],
            name="fk_optimization_studies_base_policy_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_optimization_studies_request_id"),
    )
    for name, columns in (
        ("ix_optimization_studies_request_id", ("request_id",)),
        ("ix_optimization_studies_status", ("status",)),
        ("ix_optimization_studies_base_policy_id", ("base_policy_id",)),
        ("ix_optimization_studies_lease_expires_at", ("lease_expires_at",)),
        ("ix_optimization_studies_created_at", ("created_at",)),
    ):
        op.create_index(name, "optimization_studies", list(columns), unique=False)

    op.create_table(
        "optimization_trials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=True),
        sa.Column("evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("config_sha256", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("is_baseline", sa.Integer(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("normalized_metrics_json", sa.Text(), nullable=True),
        sa.Column("score_millis", sa.Integer(), nullable=True),
        sa.Column("external_provider_calls", sa.Integer(), nullable=True),
        sa.Column("dominated", sa.Integer(), nullable=False),
        sa.Column("recommendation_rank", sa.Integer(), nullable=True),
        sa.Column("recommendation_json", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completing', 'completed', 'failed', 'cancelled')",
            name="ck_optimization_trials_status",
        ),
        sa.CheckConstraint("ordinal >= 1", name="ck_optimization_trials_ordinal_positive"),
        sa.CheckConstraint("attempt >= 0", name="ck_optimization_trials_attempt_non_negative"),
        sa.CheckConstraint(
            "score_millis IS NULL OR (score_millis >= 0 AND score_millis <= 1000)",
            name="ck_optimization_trials_score_millis",
        ),
        sa.CheckConstraint(
            "external_provider_calls IS NULL OR external_provider_calls = 0",
            name="ck_optimization_trials_provider_calls_zero",
        ),
        sa.CheckConstraint("is_baseline IN (0, 1)", name="ck_optimization_trials_baseline_flag"),
        sa.CheckConstraint("dominated IN (0, 1)", name="ck_optimization_trials_dominated_flag"),
        sa.CheckConstraint(
            "recommendation_rank IS NULL OR recommendation_rank >= 1",
            name="ck_optimization_trials_recommendation_rank",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["optimization_studies.id"],
            name="fk_optimization_trials_study_id",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["agent_policy_versions.id"],
            name="fk_optimization_trials_policy_id",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["agent_evaluations.id"],
            name="fk_optimization_trials_evaluation_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "ordinal", name="uq_optimization_trials_study_ordinal"),
        sa.UniqueConstraint("evaluation_id", name="uq_optimization_trials_evaluation_id"),
    )
    for name, columns in (
        ("ix_optimization_trials_study_id", ("study_id",)),
        ("ix_optimization_trials_status", ("status",)),
        ("ix_optimization_trials_policy_id", ("policy_id",)),
        ("ix_optimization_trials_evaluation_id", ("evaluation_id",)),
        ("ix_optimization_trials_config_sha256", ("config_sha256",)),
        ("ix_optimization_trials_lease_expires_at", ("lease_expires_at",)),
        ("ix_optimization_trials_created_at", ("created_at",)),
    ):
        op.create_index(name, "optimization_trials", list(columns), unique=False)


def downgrade() -> None:
    op.drop_table("optimization_trials")
    op.drop_table("optimization_studies")
