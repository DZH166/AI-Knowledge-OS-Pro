"""Freeze warm-start observations for reproducible optimization.

Existing V5.7 children did not store creation-time observations. Preserve the
parent facts available at migration, explicitly labeled as migration capture.
No discarded historical observations are reconstructed.
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "0016_optimizer_audit"
down_revision = "0015_v5_7_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("optimization_studies", sa.Column("warm_start_observations_json", sa.Text(), nullable=True))
    connection = op.get_bind()
    children = connection.execute(sa.text(
        "SELECT id, warm_start_study_id FROM optimization_studies WHERE warm_start_study_id IS NOT NULL"
    )).all()
    for child_id, parent_id in children:
        rows = connection.execute(sa.text(
            "SELECT config_json, config_sha256, score_millis FROM optimization_trials "
            "WHERE study_id=:parent_id AND status='completed' AND score_millis IS NOT NULL ORDER BY ordinal, id"
        ), {"parent_id": parent_id}).mappings().all()
        payload = {"captured_at": "migration", "observations": [dict(row) for row in rows]}
        connection.execute(sa.text(
            "UPDATE optimization_studies SET warm_start_observations_json=:payload WHERE id=:child_id"
        ), {"child_id": child_id, "payload": json.dumps(payload, sort_keys=True, separators=(",", ":"))})


def downgrade() -> None:
    with op.batch_alter_table("optimization_studies") as batch:
        batch.drop_column("warm_start_observations_json")
