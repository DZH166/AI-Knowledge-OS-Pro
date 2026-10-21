"""V5.5 optimizer closed loop: draft conversion, diff, and settlement columns.

Revision ID: 0012_v5_5_optimizer_closed_loop
Revises: 0011_v5_4_retrieval_optimizer
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_v5_5_optimizer_closed_loop"
down_revision = "0011_v5_4_retrieval_optimizer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("optimization_trials") as batch_op:
        batch_op.add_column(
            sa.Column("draft_policy_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("request_id", sa.String(length=120), nullable=True))
        batch_op.create_foreign_key(
            "fk_optimization_trials_draft_policy_id",
            "agent_policy_versions",
            ["draft_policy_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_optimization_trials_draft_policy_id", ["draft_policy_id"]
        )
        batch_op.create_unique_constraint("uq_optimization_trials_request_id", ["request_id"])
    op.create_index(
        "ix_optimization_trials_draft_policy_id",
        "optimization_trials",
        ["draft_policy_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_trials_request_id",
        "optimization_trials",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_optimization_trials_request_id", table_name="optimization_trials")
    op.drop_index("ix_optimization_trials_draft_policy_id", table_name="optimization_trials")
    with op.batch_alter_table("optimization_trials") as batch_op:
        batch_op.drop_constraint("uq_optimization_trials_request_id", type_="unique")
        batch_op.drop_constraint("uq_optimization_trials_draft_policy_id", type_="unique")
        batch_op.drop_constraint("fk_optimization_trials_draft_policy_id", type_="foreignkey")
        batch_op.drop_column("request_id")
        batch_op.drop_column("draft_policy_id")
