"""V2 schema extensions.

Revision ID: 0002_v2_schema
Revises: 0001_v1_baseline
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_v2_schema"
down_revision = "0001_v1_baseline"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _drop_column(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column(column_name)


def upgrade() -> None:
    for column in [
        sa.Column("processing_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("processing_progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="upload"),
        sa.Column("extractive_preview", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_provider", sa.String(length=80), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("embedding_fingerprint", sa.String(length=160), nullable=True),
        sa.Column("index_version", sa.String(length=80), nullable=True),
    ]:
        _add_column("documents", column)

    for column in [
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("heading_path", sa.String(length=500), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
    ]:
        _add_column("chunks", column)

    for column in [
        sa.Column("used_citation_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("answer_confidence", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("retrieval_score", sa.Float(), nullable=True),
        sa.Column("retrieval_status", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("runtime_mode", sa.String(length=20), nullable=False, server_default="real"),
    ]:
        _add_column("qa_logs", column)

    tables = _tables()
    if "ingestion_jobs" not in tables:
        op.create_table(
            "ingestion_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
            sa.Column("job_type", sa.String(length=40), nullable=False, server_default="ingest"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "version_learning_packages" not in tables:
        op.create_table(
            "version_learning_packages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("version_name", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("implemented_features_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("major_files_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("focus", sa.Text(), nullable=False),
            sa.Column("review_suggestions", sa.Text(), nullable=False),
            sa.Column("interview_expression", sa.Text(), nullable=False),
            sa.Column("next_version_suggestion", sa.Text(), nullable=False),
            sa.Column("markdown_content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "knowledge_points" not in tables:
        op.create_table(
            "knowledge_points",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("package_id", sa.Integer(), sa.ForeignKey("version_learning_packages.id"), nullable=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("beginner_explanation", sa.Text(), nullable=False),
            sa.Column("project_usage", sa.Text(), nullable=False),
            sa.Column("code_locations_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("review_suggestion", sa.Text(), nullable=False),
            sa.Column("interview_expression", sa.Text(), nullable=False),
            sa.Column("mastery_status", sa.String(length=30), nullable=False, server_default="not_started"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "learning_cards" not in tables:
        op.create_table(
            "learning_cards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("package_id", sa.Integer(), sa.ForeignKey("version_learning_packages.id"), nullable=True),
            sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id"), nullable=True),
            sa.Column("front", sa.Text(), nullable=False),
            sa.Column("back", sa.Text(), nullable=False),
            sa.Column("mastery_status", sa.String(length=30), nullable=False, server_default="unclear"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "quiz_questions" not in tables:
        op.create_table(
            "quiz_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("package_id", sa.Integer(), sa.ForeignKey("version_learning_packages.id"), nullable=True),
            sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id"), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("options_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("correct_answer", sa.String(length=200), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "learning_progress" not in tables:
        op.create_table(
            "learning_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id"), nullable=False),
            sa.Column("mastery_status", sa.String(length=30), nullable=False),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade() -> None:
    for table_name in [
        "learning_progress",
        "quiz_questions",
        "learning_cards",
        "knowledge_points",
        "version_learning_packages",
        "ingestion_jobs",
    ]:
        if table_name in _tables():
            op.drop_table(table_name)

    for column_name in [
        "used_citation_ids_json",
        "answer_confidence",
        "retrieval_score",
        "retrieval_status",
        "runtime_mode",
    ]:
        _drop_column("qa_logs", column_name)

    for column_name in ["metadata_json", "token_count", "section_title", "heading_path", "page_number"]:
        _drop_column("chunks", column_name)

    for column_name in [
        "index_version",
        "embedding_fingerprint",
        "embedding_dimensions",
        "embedding_model",
        "embedding_provider",
        "indexed_at",
        "ai_summary",
        "extractive_preview",
        "source_type",
        "tags_json",
        "title",
        "content_hash",
        "retry_count",
        "processing_progress",
        "processing_status",
    ]:
        _drop_column("documents", column_name)
