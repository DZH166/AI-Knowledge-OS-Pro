"""V5.6 bayesian optimizer: round tracking, warm start, category statistics.

Revision ID: 0013_v5_6_bayesian_optimizer
Revises: 0012_v5_5_optimizer_closed_loop
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_v5_6_bayesian_optimizer"
down_revision = "0012_v5_5_optimizer_closed_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("optimization_trials") as batch_op:
        batch_op.add_column(sa.Column("category_stats_json", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("round_no", sa.Integer(), nullable=False, server_default=sa.text("1"))
        )
        batch_op.create_check_constraint(
            "ck_optimization_trials_round_no", "round_no >= 1"
        )

    with op.batch_alter_table("optimization_studies") as batch_op:
        batch_op.add_column(
            sa.Column("round_no", sa.Integer(), nullable=False, server_default=sa.text("1"))
        )
        batch_op.add_column(sa.Column("next_round_request_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("warm_start_study_id", sa.String(length=36), nullable=True))
        batch_op.create_check_constraint("ck_optimization_studies_round_no", "round_no >= 1")
        batch_op.create_unique_constraint(
            "uq_optimization_studies_next_round_request_id", ["next_round_request_id"]
        )
        batch_op.create_foreign_key(
            "fk_optimization_studies_warm_start_study_id",
            "optimization_studies",
            ["warm_start_study_id"],
            ["id"],
        )
    op.create_index(
        "ix_optimization_studies_next_round_request_id",
        "optimization_studies",
        ["next_round_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_studies_warm_start_study_id",
        "optimization_studies",
        ["warm_start_study_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_optimization_studies_warm_start_study_id", table_name="optimization_studies"
    )
    op.drop_index(
        "ix_optimization_studies_next_round_request_id", table_name="optimization_studies"
    )
    with op.batch_alter_table("optimization_studies") as batch_op:
        batch_op.drop_constraint("fk_optimization_studies_warm_start_study_id", type_="foreignkey")
        batch_op.drop_constraint("uq_optimization_studies_next_round_request_id", type_="unique")
        batch_op.drop_constraint("ck_optimization_studies_round_no", type_="check")
        batch_op.drop_column("warm_start_study_id")
        batch_op.drop_column("next_round_request_id")
        batch_op.drop_column("round_no")

    with op.batch_alter_table("optimization_trials") as batch_op:
        batch_op.drop_constraint("ck_optimization_trials_round_no", type_="check")
        batch_op.drop_column("round_no")
        batch_op.drop_column("category_stats_json")
