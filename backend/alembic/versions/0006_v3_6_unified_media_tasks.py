"""V3.6 unified document and media tasks.

Revision ID: 0006_v3_6_unified_media_tasks
Revises: 0005_v3_3_error_archive
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_v3_6_unified_media_tasks"
down_revision = "0005_v3_3_error_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("ingestion_jobs")}
    indexes = {index["name"] for index in inspector.get_indexes("ingestion_jobs")}

    if "source_id" not in columns:
        op.add_column("ingestion_jobs", sa.Column("source_id", sa.Integer(), nullable=True))
        op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])
    if "target_type" not in columns:
        op.add_column(
            "ingestion_jobs",
            sa.Column("target_type", sa.String(length=30), nullable=False, server_default="document"),
        )
        op.create_index("ix_ingestion_jobs_target_type", "ingestion_jobs", ["target_type"])

    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.alter_column("document_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "fk_ingestion_jobs_source_id_sources",
            "sources",
            ["source_id"],
            ["id"],
        )

    if "ix_ingestion_jobs_document_id" not in indexes:
        op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])

    inspector = sa.inspect(op.get_bind())
    if "learning_artifacts" not in inspector.get_table_names():
        op.create_table(
            "learning_artifacts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("artifact_type", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
            sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("multimodal_chunks.id"), nullable=True),
            sa.Column("document_chunk_id", sa.Integer(), sa.ForeignKey("chunks.id"), nullable=True),
            sa.Column("locator_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id"), nullable=True),
            sa.Column("card_id", sa.Integer(), sa.ForeignKey("learning_cards.id"), nullable=True),
            sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("quiz_questions.id"), nullable=True),
            sa.Column("note_id", sa.Integer(), sa.ForeignKey("learning_notes.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        for name, columns in [
            ("ix_learning_artifacts_artifact_type", ["artifact_type"]),
            ("ix_learning_artifacts_source_id", ["source_id"]),
            ("ix_learning_artifacts_document_id", ["document_id"]),
            ("ix_learning_artifacts_chunk_id", ["chunk_id"]),
            ("ix_learning_artifacts_document_chunk_id", ["document_chunk_id"]),
        ]:
            op.create_index(name, "learning_artifacts", columns)


def downgrade() -> None:
    bind = op.get_bind()
    media_jobs = bind.execute(
        sa.text("SELECT COUNT(*) FROM ingestion_jobs WHERE source_id IS NOT NULL AND document_id IS NULL")
    ).scalar_one()
    if media_jobs:
        raise RuntimeError("Cannot downgrade while media jobs without document_id exist.")

    if "learning_artifacts" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("learning_artifacts")

    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.drop_constraint("fk_ingestion_jobs_source_id_sources", type_="foreignkey")
        batch_op.alter_column("document_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_ingestion_jobs_target_type", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_source_id", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "target_type")
    op.drop_column("ingestion_jobs", "source_id")
