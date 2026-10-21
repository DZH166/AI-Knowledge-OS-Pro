"""V3 task engine and multimodal source foundation.

Revision ID: 0004_v3_task_multimodal_foundation
Revises: 0003_v2_5_product_learning
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_v3_task_multimodal_foundation"
down_revision = "0003_v2_5_product_learning"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if table_name in _tables() and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _drop_column(table_name: str, column_name: str) -> None:
    if table_name in _tables() and column_name in _columns(table_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column(column_name)


def _create_index(name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if table_name in _tables():
        existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
        if name not in existing:
            op.create_index(name, table_name, columns, unique=unique)


def _drop_index(name: str, table_name: str) -> None:
    if table_name in _tables():
        existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
        if name in existing:
            op.drop_index(name, table_name=table_name)


def upgrade() -> None:
    _upgrade_jobs()
    _create_multimodal_tables()
    _migrate_documents_to_sources()


def downgrade() -> None:
    for table_name in [
        "citation_locators",
        "index_revisions",
        "multimodal_chunks",
        "visual_frames",
        "transcript_segments",
        "media_assets",
        "source_revisions",
        "sources",
        "job_events",
    ]:
        if table_name in _tables():
            op.drop_table(table_name)

    for index_name in [
        "ix_ingestion_jobs_parent_job_id",
        "ix_ingestion_jobs_status",
        "ix_ingestion_jobs_queue_name",
    ]:
        _drop_index(index_name, "ingestion_jobs")

    for column_name in [
        "duration_ms",
        "cancel_requested_at",
        "finished_at",
        "heartbeat_at",
        "started_at",
        "parent_job_id",
        "result_json",
        "error_details_json",
        "error_code",
        "max_attempts",
        "attempt",
        "priority",
        "queue_name",
        "worker_id",
        "step_total",
        "step_index",
        "current_step",
    ]:
        _drop_column("ingestion_jobs", column_name)


def _upgrade_jobs() -> None:
    for column in [
        sa.Column("current_step", sa.String(length=80), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker_id", sa.String(length=120), nullable=True),
        sa.Column("queue_name", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("parent_job_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    ]:
        _add_column("ingestion_jobs", column)
    _create_index("ix_ingestion_jobs_parent_job_id", "ingestion_jobs", ["parent_job_id"])
    _create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    _create_index("ix_ingestion_jobs_queue_name", "ingestion_jobs", ["queue_name"])

    if "job_events" not in _tables():
        op.create_table(
            "job_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("ingestion_jobs.id"), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("step", sa.String(length=80), nullable=True),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("technical_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
        op.create_index("ix_job_events_event_type", "job_events", ["event_type"])
        op.create_index("ix_job_events_created_at", "job_events", ["created_at"])


def _create_multimodal_tables() -> None:
    tables = _tables()
    if "sources" not in tables:
        op.create_table(
            "sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("original_filename", sa.String(length=255), nullable=True),
            sa.Column("mime_type", sa.String(length=120), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("storage_path", sa.String(length=500), nullable=True),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="uploaded"),
            sa.Column("language", sa.String(length=40), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("active_revision_id", sa.Integer(), nullable=True),
            sa.Column("latest_revision_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        for name, columns in [
            ("ix_sources_space_id", ["space_id"]),
            ("ix_sources_document_id", ["document_id"]),
            ("ix_sources_source_type", ["source_type"]),
            ("ix_sources_content_hash", ["content_hash"]),
            ("ix_sources_status", ["status"]),
            ("ix_sources_active_revision_id", ["active_revision_id"]),
            ("ix_sources_latest_revision_id", ["latest_revision_id"]),
        ]:
            op.create_index(name, "sources", columns)

    if "source_revisions" not in tables:
        op.create_table(
            "source_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
            sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="staging"),
            sa.Column("parser_name", sa.String(length=80), nullable=True),
            sa.Column("parser_version", sa.String(length=80), nullable=True),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("vector_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_source_revisions_source_id", "source_revisions", ["source_id"])
        op.create_index("ix_source_revisions_document_id", "source_revisions", ["document_id"])
        op.create_index("ix_source_revisions_status", "source_revisions", ["status"])

    if "media_assets" not in tables:
        op.create_table(
            "media_assets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("asset_type", sa.String(length=40), nullable=False),
            sa.Column("storage_path", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=120), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_media_assets_source_id", "media_assets", ["source_id"])
        op.create_index("ix_media_assets_asset_type", "media_assets", ["asset_type"])

    if "transcript_segments" not in tables:
        op.create_table(
            "transcript_segments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=False),
            sa.Column("segment_index", sa.Integer(), nullable=False),
            sa.Column("start_ms", sa.Integer(), nullable=False),
            sa.Column("end_ms", sa.Integer(), nullable=False),
            sa.Column("speaker", sa.String(length=80), nullable=True),
            sa.Column("language", sa.String(length=40), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_transcript_segments_source_id", "transcript_segments", ["source_id"])
        op.create_index("ix_transcript_segments_revision_id", "transcript_segments", ["revision_id"])

    if "visual_frames" not in tables:
        op.create_table(
            "visual_frames",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=False),
            sa.Column("frame_index", sa.Integer(), nullable=False),
            sa.Column("timestamp_ms", sa.Integer(), nullable=True),
            sa.Column("storage_path", sa.String(length=500), nullable=True),
            sa.Column("ocr_text", sa.Text(), nullable=True),
            sa.Column("visual_description", sa.Text(), nullable=True),
            sa.Column("scene_score", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_visual_frames_source_id", "visual_frames", ["source_id"])
        op.create_index("ix_visual_frames_revision_id", "visual_frames", ["revision_id"])

    if "multimodal_chunks" not in tables:
        op.create_table(
            "multimodal_chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=False),
            sa.Column("legacy_chunk_id", sa.Integer(), sa.ForeignKey("chunks.id"), nullable=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("modality", sa.String(length=40), nullable=False),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("content_text", sa.Text(), nullable=False),
            sa.Column("search_text", sa.Text(), nullable=False),
            sa.Column("raw_payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("locator_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("parent_chunk_id", sa.Integer(), nullable=True),
            sa.Column("start_ms", sa.Integer(), nullable=True),
            sa.Column("end_ms", sa.Integer(), nullable=True),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("slide_number", sa.Integer(), nullable=True),
            sa.Column("frame_id", sa.Integer(), sa.ForeignKey("visual_frames.id"), nullable=True),
            sa.Column("speaker", sa.String(length=80), nullable=True),
            sa.Column("language", sa.String(length=40), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="staging"),
            sa.Column("qdrant_point_id", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        for name, columns in [
            ("ix_multimodal_chunks_source_id", ["source_id"]),
            ("ix_multimodal_chunks_revision_id", ["revision_id"]),
            ("ix_multimodal_chunks_legacy_chunk_id", ["legacy_chunk_id"]),
            ("ix_multimodal_chunks_modality", ["modality"]),
            ("ix_multimodal_chunks_source_type", ["source_type"]),
            ("ix_multimodal_chunks_parent_chunk_id", ["parent_chunk_id"]),
            ("ix_multimodal_chunks_frame_id", ["frame_id"]),
            ("ix_multimodal_chunks_status", ["status"]),
            ("ix_multimodal_chunks_qdrant_point_id", ["qdrant_point_id"]),
        ]:
            op.create_index(name, "multimodal_chunks", columns)

    if "citation_locators" not in tables:
        op.create_table(
            "citation_locators",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=True),
            sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("multimodal_chunks.id"), nullable=True),
            sa.Column("locator_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("display_text", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_citation_locators_source_id", "citation_locators", ["source_id"])
        op.create_index("ix_citation_locators_revision_id", "citation_locators", ["revision_id"])
        op.create_index("ix_citation_locators_chunk_id", "citation_locators", ["chunk_id"])

    if "index_revisions" not in tables:
        op.create_table(
            "index_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="staging"),
            sa.Column("index_version", sa.String(length=80), nullable=False),
            sa.Column("embedding_provider", sa.String(length=80), nullable=True),
            sa.Column("embedding_model", sa.String(length=160), nullable=True),
            sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
            sa.Column("embedding_fingerprint", sa.String(length=160), nullable=True),
            sa.Column("qdrant_collection", sa.String(length=160), nullable=True),
            sa.Column("point_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_index_revisions_source_id", "index_revisions", ["source_id"])
        op.create_index("ix_index_revisions_revision_id", "index_revisions", ["revision_id"])
        op.create_index("ix_index_revisions_status", "index_revisions", ["status"])
        op.create_index("ix_index_revisions_embedding_fingerprint", "index_revisions", ["embedding_fingerprint"])


def _migrate_documents_to_sources() -> None:
    bind = op.get_bind()
    tables = _tables()
    if not {"documents", "chunks", "sources", "source_revisions", "multimodal_chunks", "index_revisions"}.issubset(tables):
        return
    documents = bind.execute(
        sa.text(
            """
            SELECT id, space_id, file_type, title, original_filename, content_type, file_size,
                   storage_path, content_hash, status, chunk_count, embedding_provider,
                   embedding_model, embedding_dimensions, embedding_fingerprint, index_version
            FROM documents
            """
        )
    ).mappings()
    for document in documents:
        existing = bind.execute(
            sa.text("SELECT id FROM sources WHERE document_id = :document_id"),
            {"document_id": document["id"]},
        ).first()
        if existing:
            continue
        source_type = _source_type_for_document(document["file_type"])
        result = bind.execute(
            sa.text(
                """
                INSERT INTO sources (
                    space_id, document_id, source_type, title, original_filename, mime_type,
                    file_size, storage_path, content_hash, status, metadata_json
                ) VALUES (
                    :space_id, :document_id, :source_type, :title, :original_filename, :mime_type,
                    :file_size, :storage_path, :content_hash, :status, :metadata_json
                )
                """
            ),
            {
                "space_id": document["space_id"],
                "document_id": document["id"],
                "source_type": source_type,
                "title": document["title"] or document["original_filename"],
                "original_filename": document["original_filename"],
                "mime_type": document["content_type"],
                "file_size": document["file_size"] or 0,
                "storage_path": document["storage_path"],
                "content_hash": document["content_hash"],
                "status": document["status"],
                "metadata_json": '{"legacy_document": true}',
            },
        )
        source_id = result.lastrowid
        revision_result = bind.execute(
            sa.text(
                """
                INSERT INTO source_revisions (
                    source_id, document_id, revision_number, status, parser_name,
                    content_hash, chunk_count, validation_status, metadata_json, activated_at
                ) VALUES (
                    :source_id, :document_id, 1, 'active', 'legacy_document_parser',
                    :content_hash, :chunk_count, 'passed', '{"legacy_revision": true}', CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "source_id": source_id,
                "document_id": document["id"],
                "content_hash": document["content_hash"],
                "chunk_count": document["chunk_count"] or 0,
            },
        )
        revision_id = revision_result.lastrowid
        bind.execute(
            sa.text("UPDATE sources SET active_revision_id = :revision_id, latest_revision_id = :revision_id WHERE id = :source_id"),
            {"source_id": source_id, "revision_id": revision_id},
        )
        chunks = bind.execute(
            sa.text(
                """
                SELECT id, chunk_index, content, page_number, heading_path, section_title,
                       token_count, metadata_json, qdrant_point_id
                FROM chunks
                WHERE document_id = :document_id
                ORDER BY chunk_index
                """
            ),
            {"document_id": document["id"]},
        ).mappings()
        for chunk in chunks:
            locator = {
                "page_number": chunk["page_number"],
                "heading_path": chunk["heading_path"],
                "section_title": chunk["section_title"],
            }
            bind.execute(
                sa.text(
                    """
                    INSERT INTO multimodal_chunks (
                        source_id, revision_id, legacy_chunk_id, chunk_index, modality, source_type,
                        content_text, search_text, raw_payload_json, locator_json, page_number,
                        status, qdrant_point_id
                    ) VALUES (
                        :source_id, :revision_id, :legacy_chunk_id, :chunk_index, 'text', :source_type,
                        :content_text, :search_text, :raw_payload_json, :locator_json, :page_number,
                        'active', :qdrant_point_id
                    )
                    """
                ),
                {
                    "source_id": source_id,
                    "revision_id": revision_id,
                    "legacy_chunk_id": chunk["id"],
                    "chunk_index": chunk["chunk_index"],
                    "source_type": source_type,
                    "content_text": chunk["content"],
                    "search_text": chunk["content"],
                    "raw_payload_json": chunk["metadata_json"] or "{}",
                    "locator_json": str(locator).replace("'", '"'),
                    "page_number": chunk["page_number"],
                    "qdrant_point_id": chunk["qdrant_point_id"],
                },
            )
        bind.execute(
            sa.text(
                """
                INSERT INTO index_revisions (
                    source_id, revision_id, status, index_version, embedding_provider,
                    embedding_model, embedding_dimensions, embedding_fingerprint, point_count,
                    validation_status, activated_at
                ) VALUES (
                    :source_id, :revision_id, 'active', :index_version, :embedding_provider,
                    :embedding_model, :embedding_dimensions, :embedding_fingerprint, :point_count,
                    'passed', CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "source_id": source_id,
                "revision_id": revision_id,
                "index_version": document["index_version"] or "legacy",
                "embedding_provider": document["embedding_provider"],
                "embedding_model": document["embedding_model"],
                "embedding_dimensions": document["embedding_dimensions"],
                "embedding_fingerprint": document["embedding_fingerprint"],
                "point_count": document["chunk_count"] or 0,
            },
        )


def _source_type_for_document(file_type: str | None) -> str:
    mapping = {"txt": "text", "md": "markdown", "pdf": "pdf"}
    return mapping.get((file_type or "").lower(), "text")
