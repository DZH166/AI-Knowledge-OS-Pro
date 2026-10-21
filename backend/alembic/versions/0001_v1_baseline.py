"""V1 baseline schema.

Revision ID: 0001_v1_baseline
Revises:
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_v1_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "knowledge_spaces" not in tables:
        op.create_table(
            "knowledge_spaces",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "documents" not in tables:
        op.create_table(
            "documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("file_type", sa.String(length=20), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("storage_path", sa.String(length=500), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="uploaded"),
            sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("chunk_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("vector_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "chunks" not in tables:
        op.create_table(
            "chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_preview", sa.Text(), nullable=False),
            sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("qdrant_point_id", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "qa_logs" not in tables:
        op.create_table(
            "qa_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("answer_mode", sa.String(length=30), nullable=False, server_default="normal"),
            sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("related_chunks_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "learning_logs" not in tables:
        op.create_table(
            "learning_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("version_name", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("implemented_features_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("major_files_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("knowledge_points_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("focus", sa.Text(), nullable=False),
            sa.Column("review_suggestions", sa.Text(), nullable=False),
            sa.Column("interview_expression", sa.Text(), nullable=False),
            sa.Column("next_version_suggestion", sa.Text(), nullable=False),
            sa.Column("markdown_content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade() -> None:
    for table_name in ["learning_logs", "qa_logs", "chunks", "documents", "knowledge_spaces"]:
        if table_name in _tables():
            op.drop_table(table_name)
