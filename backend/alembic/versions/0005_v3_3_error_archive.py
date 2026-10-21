"""V3.3 screenshot error archive.

Revision ID: 0005_v3_3_error_archive
Revises: 0004_v3_task_multimodal_foundation
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_v3_3_error_archive"
down_revision = "0004_v3_task_multimodal_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "error_archives" in inspector.get_table_names():
        return
    op.create_table(
        "error_archives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("multimodal_chunks.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("error_type", sa.String(length=160), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("stack_excerpt", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=40), nullable=True),
        sa.Column("severity", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("detection_method", sa.String(length=80), nullable=False, server_default="ocr_pattern"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suggested_actions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    for name, columns in [
        ("ix_error_archives_space_id", ["space_id"]),
        ("ix_error_archives_source_id", ["source_id"]),
        ("ix_error_archives_chunk_id", ["chunk_id"]),
        ("ix_error_archives_error_type", ["error_type"]),
        ("ix_error_archives_language", ["language"]),
        ("ix_error_archives_severity", ["severity"]),
        ("ix_error_archives_status", ["status"]),
        ("ix_error_archives_fingerprint", ["fingerprint"]),
    ]:
        op.create_index(name, "error_archives", columns)
    op.create_index(
        "uq_error_archives_source_fingerprint",
        "error_archives",
        ["source_id", "fingerprint"],
        unique=True,
    )


def downgrade() -> None:
    if "error_archives" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_table("error_archives")
