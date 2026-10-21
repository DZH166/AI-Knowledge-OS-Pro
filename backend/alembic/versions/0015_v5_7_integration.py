"""V5.7 integration: durable optimizer round command receipts.

Revision ID: 0015_v5_7_integration
Revises: 0014_v5_7_workbench_backend
Create Date: 2026-09-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
import json
from uuid import uuid4


revision = "0015_v5_7_integration"
down_revision = "0014_v5_7_workbench_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_round_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("round_no >= 2", name="ck_optimization_round_commands_round_no"),
        sa.CheckConstraint("created_count >= 0", name="ck_optimization_round_commands_created_count"),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["optimization_studies.id"],
            name="fk_optimization_round_commands_study_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_optimization_round_commands_request_id"),
    )
    op.create_index(
        "ix_optimization_round_commands_study_id",
        "optimization_round_commands",
        ["study_id"],
        unique=False,
    )
    _backfill_historical_round_receipts()


def _backfill_historical_round_receipts() -> None:
    """Preserve the one V5.6 next-round receipt stored on each Study.

    V5.6 persisted only the latest request id and resulting round number on the
    study row. V5.7 moves receipts into an append-only command table. Copying
    the available historical fact prevents a replay after upgrade from
    accidentally creating another round.
    """

    connection = op.get_bind()
    studies = sa.table(
        "optimization_studies",
        sa.column("id", sa.String()),
        sa.column("next_round_request_id", sa.String()),
        sa.column("round_no", sa.Integer()),
    )
    trials = sa.table(
        "optimization_trials",
        sa.column("study_id", sa.String()),
        sa.column("round_no", sa.Integer()),
    )
    commands = sa.table(
        "optimization_round_commands",
        sa.column("id", sa.String()),
        sa.column("study_id", sa.String()),
        sa.column("request_id", sa.String()),
        sa.column("round_no", sa.Integer()),
        sa.column("created_count", sa.Integer()),
        sa.column("receipt_json", sa.Text()),
    )
    rows = connection.execute(
        sa.select(studies.c.id, studies.c.next_round_request_id, studies.c.round_no).where(
            studies.c.next_round_request_id.is_not(None),
            studies.c.round_no >= 2,
        )
    ).all()
    for study_id, request_id, round_no in rows:
        created_count = int(
            connection.scalar(
                sa.select(sa.func.count()).select_from(trials).where(
                    trials.c.study_id == study_id,
                    trials.c.round_no == round_no,
                )
            )
            or 0
        )
        receipt = {
            "created": created_count,
            "replayed": False,
            "round_no": int(round_no),
            "study_id": str(study_id),
        }
        connection.execute(
            commands.insert().values(
                id=str(uuid4()),
                study_id=study_id,
                request_id=request_id,
                round_no=round_no,
                created_count=created_count,
                receipt_json=json.dumps(receipt, sort_keys=True, separators=(",", ":")),
            )
        )
    op.create_index(
        "ix_optimization_round_commands_request_id",
        "optimization_round_commands",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_optimization_round_commands_request_id",
        table_name="optimization_round_commands",
    )
    op.drop_index(
        "ix_optimization_round_commands_study_id",
        table_name="optimization_round_commands",
    )
    op.drop_table("optimization_round_commands")
