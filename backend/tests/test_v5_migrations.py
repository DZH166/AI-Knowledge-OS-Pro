from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect
from sqlalchemy import text

from app.core.config import settings
from app.db.session import create_database_engine


ROOT = Path(__file__).resolve().parents[2]
V4_9_REVISION = "0006_v3_6_unified_media_tasks"

LEGACY_SEMANTIC_COLUMNS = {
    "sources": (
        "id", "space_id", "document_id", "source_type", "title", "original_filename",
        "mime_type", "file_size", "storage_path", "content_hash", "status", "language",
        "duration_ms", "page_count", "width", "height", "metadata_json",
        "active_revision_id", "latest_revision_id", "created_at", "updated_at",
    ),
    "source_revisions": (
        "id", "source_id", "document_id", "revision_number", "status", "parser_name",
        "parser_version", "content_hash", "chunk_count", "vector_count",
        "validation_status", "error_message", "metadata_json", "created_at", "activated_at",
    ),
    "multimodal_chunks": (
        "id", "source_id", "revision_id", "legacy_chunk_id", "chunk_index", "modality",
        "source_type", "content_text", "search_text", "raw_payload_json", "locator_json",
        "parent_chunk_id", "start_ms", "end_ms", "page_number", "slide_number", "frame_id",
        "speaker", "language", "status", "qdrant_point_id", "created_at",
    ),
    "index_revisions": (
        "id", "source_id", "revision_id", "status", "index_version", "embedding_provider",
        "embedding_model", "embedding_dimensions", "embedding_fingerprint",
        "qdrant_collection", "point_count", "validation_status", "created_at", "activated_at",
    ),
}


def _upgrade(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision)


def _downgrade(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, revision)


def _semantic_snapshot(engine) -> dict[str, list[dict[str, object]]]:
    snapshot: dict[str, list[dict[str, object]]] = {}
    with engine.connect() as connection:
        for table_name, columns in LEGACY_SEMANTIC_COLUMNS.items():
            selected = ", ".join(columns)
            snapshot[table_name] = [
                dict(row)
                for row in connection.execute(
                    text(f"SELECT {selected} FROM {table_name} ORDER BY id")
                ).mappings()
            ]
    return snapshot


def _sqlite_database_snapshot(engine) -> dict[str, object]:
    with engine.connect() as connection:
        schema = [
            tuple(row)
            for row in connection.execute(
                text(
                    """
                    SELECT type, name, tbl_name, sql
                    FROM sqlite_master
                    WHERE name NOT LIKE 'sqlite_%'
                    ORDER BY type, name
                    """
                )
            )
        ]
        table_names = [
            row[1] for row in schema if row[0] == "table" and row[1] != "sqlite_sequence"
        ]
        rows = {}
        for table_name in table_names:
            quoted_name = table_name.replace('"', '""')
            rows[table_name] = [
                tuple(row)
                for row in connection.execute(
                    text(f'SELECT * FROM "{quoted_name}" ORDER BY rowid')
                )
            ]
    return {"schema": schema, "rows": rows}


def test_sqlite_engine_enforces_integrity_and_concurrency_pragmas(tmp_path) -> None:
    database_path = tmp_path / "v5-runtime.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")

    try:
        with engine.connect() as connection:
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
            busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
    finally:
        engine.dispose()

    assert foreign_keys == 1
    assert busy_timeout >= 5_000
    assert str(journal_mode).lower() == "wal"


def test_v5_evidence_migration_canonicalizes_v49_documents_and_active_revisions(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v49-upgrade.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _upgrade(database_url, V4_9_REVISION, monkeypatch)
    engine = create_database_engine(database_url)

    try:
        with engine.begin() as connection:
            space_id = connection.execute(
                text("INSERT INTO knowledge_spaces (name, description) VALUES ('V5 migration', 'fixture')")
            ).lastrowid
            document_id = connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        space_id, filename, original_filename, file_type, file_size, storage_path,
                        status, parse_status, chunk_status, vector_status, processing_status,
                        content_hash, chunk_count, embedding_fingerprint, index_version
                    ) VALUES (
                        :space_id, 'late.md', 'late.md', 'md', 10, 'late.md',
                        'ready', 'parsed', 'chunked', 'indexed', 'completed',
                        'document-hash', 1, 'fake::v49', 'v4'
                    )
                    """
                ),
                {"space_id": space_id},
            ).lastrowid
            legacy_chunk_id = connection.execute(
                text(
                    """
                    INSERT INTO chunks (
                        document_id, space_id, chunk_index, content, content_preview,
                        char_count, page_number, metadata_json, qdrant_point_id
                    ) VALUES (
                        :document_id, :space_id, 0, 'late exact evidence', 'late exact evidence',
                        19, 7, '{}', 'legacy-point'
                    )
                    """
                ),
                {"document_id": document_id, "space_id": space_id},
            ).lastrowid

            source_id = connection.execute(
                text(
                    """
                    INSERT INTO sources (
                        space_id, source_type, title, file_size, status, metadata_json
                    ) VALUES (:space_id, 'audio', 'meeting', 10, 'ready', '{}')
                    """
                ),
                {"space_id": space_id},
            ).lastrowid
            first_revision_id = connection.execute(
                text(
                    """
                    INSERT INTO source_revisions (
                        source_id, revision_number, status, content_hash, chunk_count,
                        vector_count, validation_status, metadata_json
                    ) VALUES (:source_id, 1, 'active', 'old-hash', 1, 1, 'passed', '{}')
                    """
                ),
                {"source_id": source_id},
            ).lastrowid
            second_revision_id = connection.execute(
                text(
                    """
                    INSERT INTO source_revisions (
                        source_id, revision_number, status, content_hash, chunk_count,
                        vector_count, validation_status, metadata_json
                    ) VALUES (:source_id, 2, 'active', 'new-hash', 1, 1, 'passed', '{}')
                    """
                ),
                {"source_id": source_id},
            ).lastrowid
            connection.execute(
                text(
                    "UPDATE sources SET active_revision_id=:revision_id, latest_revision_id=:revision_id WHERE id=:source_id"
                ),
                {"revision_id": second_revision_id, "source_id": source_id},
            )
            for revision_id, value, point_id in (
                (first_revision_id, "old transcript", "old-point"),
                (second_revision_id, "new transcript", "new-point"),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO multimodal_chunks (
                            source_id, revision_id, chunk_index, modality, source_type,
                            content_text, search_text, raw_payload_json, locator_json,
                            status, qdrant_point_id
                        ) VALUES (
                            :source_id, :revision_id, 0, 'audio_transcript', 'audio',
                            :value, :value, '{}', '{}', 'active', :point_id
                        )
                        """
                    ),
                    {
                        "source_id": source_id,
                        "revision_id": revision_id,
                        "value": value,
                        "point_id": point_id,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO index_revisions (
                            source_id, revision_id, status, index_version, point_count,
                            validation_status
                        ) VALUES (:source_id, :revision_id, 'active', 'v4', 1, 'passed')
                        """
                    ),
                    {"source_id": source_id, "revision_id": revision_id},
                )

        pre_upgrade_snapshot = _semantic_snapshot(engine)

        _upgrade(database_url, "head", monkeypatch)

        table_names = set(inspect(engine).get_table_names())
        assert {"index_operations", "vector_point_manifests", "outbox_messages"}.issubset(table_names)
        with engine.connect() as connection:
            document_source = connection.execute(
                text("SELECT id, active_revision_id FROM sources WHERE document_id=:document_id"),
                {"document_id": document_id},
            ).mappings().one()
            canonical_chunk = connection.execute(
                text(
                    """
                    SELECT revision_id, legacy_chunk_id, content_hash, status
                    FROM multimodal_chunks
                    WHERE source_id=:source_id AND legacy_chunk_id=:legacy_chunk_id
                    """
                ),
                {"source_id": document_source["id"], "legacy_chunk_id": legacy_chunk_id},
            ).mappings().one()
            active_media_revisions = connection.execute(
                text("SELECT id FROM source_revisions WHERE source_id=:source_id AND status='active'"),
                {"source_id": source_id},
            ).scalars().all()
            active_media_indexes = connection.execute(
                text("SELECT revision_id FROM index_revisions WHERE source_id=:source_id AND status='active'"),
                {"source_id": source_id},
            ).scalars().all()

        assert document_source["active_revision_id"] == canonical_chunk["revision_id"]
        assert canonical_chunk["content_hash"]
        assert canonical_chunk["status"] == "active"
        assert active_media_revisions == [second_revision_id]
        assert active_media_indexes == [second_revision_id]

        _downgrade(database_url, V4_9_REVISION, monkeypatch)
        assert _semantic_snapshot(engine) == pre_upgrade_snapshot

        _upgrade(database_url, "head", monkeypatch)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0015_v5_7_integration"
            )
    finally:
        engine.dispose()


def test_v5_downgrade_preserves_unjournaled_post_upgrade_legacy_rows(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-new-data-downgrade.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _upgrade(database_url, V4_9_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            space_id = connection.execute(
                text("INSERT INTO knowledge_spaces (name, description) VALUES ('New data', 'fixture')")
            ).lastrowid
            document_id = connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        space_id, filename, original_filename, file_type, file_size, storage_path,
                        status, parse_status, chunk_status, vector_status, processing_status
                    ) VALUES (
                        :space_id, 'backfill.md', 'backfill.md', 'md', 10, 'backfill.md',
                        'ready', 'parsed', 'chunked', 'indexed', 'completed'
                    )
                    """
                ),
                {"space_id": space_id},
            ).lastrowid
            connection.execute(
                text(
                    """
                    INSERT INTO chunks (
                        document_id, space_id, chunk_index, content, content_preview,
                        char_count, metadata_json, qdrant_point_id
                    ) VALUES (
                        :document_id, :space_id, 0, 'backfilled evidence',
                        'backfilled evidence', 19, '{}', 'backfill-point'
                    )
                    """
                ),
                {"document_id": document_id, "space_id": space_id},
            )
            adopted_document_id = connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        space_id, filename, original_filename, file_type, file_size, storage_path,
                        status, parse_status, chunk_status, vector_status, processing_status
                    ) VALUES (
                        :space_id, 'adopted.md', 'adopted.md', 'md', 11, 'adopted.md',
                        'ready', 'parsed', 'chunked', 'indexed', 'completed'
                    )
                    """
                ),
                {"space_id": space_id},
            ).lastrowid
            connection.execute(
                text(
                    """
                    INSERT INTO chunks (
                        document_id, space_id, chunk_index, content, content_preview,
                        char_count, metadata_json, qdrant_point_id
                    ) VALUES (
                        :document_id, :space_id, 0, 'adopted evidence',
                        'adopted evidence', 16, '{}', 'adopted-point'
                    )
                    """
                ),
                {"document_id": adopted_document_id, "space_id": space_id},
            )

        _upgrade(database_url, "head", monkeypatch)
        with engine.begin() as connection:
            migration_source_id = connection.execute(
                text("SELECT id FROM sources WHERE document_id=:document_id"),
                {"document_id": document_id},
            ).scalar_one()
            adopted_source = connection.execute(
                text(
                    """
                    SELECT id, active_revision_id, active_index_revision_id
                    FROM sources
                    WHERE document_id=:document_id
                    """
                ),
                {"document_id": adopted_document_id},
            ).mappings().one()
            adopted_chunk_id = connection.execute(
                text("SELECT id FROM multimodal_chunks WHERE source_id=:source_id"),
                {"source_id": adopted_source["id"]},
            ).scalar_one()
            connection.execute(
                text("UPDATE sources SET title='adopted after upgrade' WHERE id=:source_id"),
                {"source_id": adopted_source["id"]},
            )
            post_source_id = connection.execute(
                text(
                    """
                    INSERT INTO sources (
                        space_id, source_type, title, file_size, status, metadata_json
                    ) VALUES (:space_id, 'audio', 'post-upgrade source', 12, 'ready', '{}')
                    """
                ),
                {"space_id": space_id},
            ).lastrowid
            post_revision_id = connection.execute(
                text(
                    """
                    INSERT INTO source_revisions (
                        source_id, revision_number, status, content_hash, chunk_count,
                        vector_count, validation_status, metadata_json
                    ) VALUES (:source_id, 1, 'active', 'post-hash', 1, 1, 'passed', '{}')
                    """
                ),
                {"source_id": post_source_id},
            ).lastrowid
            post_chunk_id = connection.execute(
                text(
                    """
                    INSERT INTO multimodal_chunks (
                        source_id, revision_id, chunk_index, modality, source_type,
                        content_text, content_hash, search_text, raw_payload_json,
                        locator_json, status, qdrant_point_id
                    ) VALUES (
                        :source_id, :revision_id, 0, 'audio_transcript', 'audio',
                        'post-upgrade evidence', :content_hash, 'post-upgrade evidence', '{}',
                        '{"kind":"media_time"}', 'active', 'post-upgrade-point'
                    )
                    """
                ),
                {
                    "source_id": post_source_id,
                    "revision_id": post_revision_id,
                    "content_hash": "a" * 64,
                },
            ).lastrowid
            post_index_id = connection.execute(
                text(
                    """
                    INSERT INTO index_revisions (
                        source_id, revision_id, status, index_version, point_count,
                        validation_status
                    ) VALUES (:source_id, :revision_id, 'active', 'post-v5', 1, 'passed')
                    """
                ),
                {"source_id": post_source_id, "revision_id": post_revision_id},
            ).lastrowid
            connection.execute(
                text(
                    """
                    UPDATE sources
                    SET active_revision_id=:revision_id,
                        latest_revision_id=:revision_id,
                        active_index_revision_id=:index_revision_id
                    WHERE id=:source_id
                    """
                ),
                {
                    "source_id": post_source_id,
                    "revision_id": post_revision_id,
                    "index_revision_id": post_index_id,
                },
            )

        _downgrade(database_url, V4_9_REVISION, monkeypatch)
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM sources WHERE id=:source_id"),
                {"source_id": migration_source_id},
            ).scalar_one() == 0
            assert connection.execute(
                text("SELECT title FROM sources WHERE id=:source_id"),
                {"source_id": post_source_id},
            ).scalar_one() == "post-upgrade source"
            assert connection.execute(
                text("SELECT source_id FROM source_revisions WHERE id=:revision_id"),
                {"revision_id": post_revision_id},
            ).scalar_one() == post_source_id
            assert connection.execute(
                text("SELECT revision_id FROM multimodal_chunks WHERE id=:chunk_id"),
                {"chunk_id": post_chunk_id},
            ).scalar_one() == post_revision_id
            assert connection.execute(
                text("SELECT title FROM sources WHERE id=:source_id"),
                {"source_id": adopted_source["id"]},
            ).scalar_one() == "adopted after upgrade"
            assert connection.execute(
                text("SELECT source_id FROM source_revisions WHERE id=:revision_id"),
                {"revision_id": adopted_source["active_revision_id"]},
            ).scalar_one() == adopted_source["id"]
            assert connection.execute(
                text("SELECT source_id FROM multimodal_chunks WHERE id=:chunk_id"),
                {"chunk_id": adopted_chunk_id},
            ).scalar_one() == adopted_source["id"]
            assert connection.execute(
                text("SELECT source_id FROM index_revisions WHERE id=:index_revision_id"),
                {"index_revision_id": adopted_source["active_index_revision_id"]},
            ).scalar_one() == adopted_source["id"]
            assert connection.execute(
                text("SELECT revision_id FROM index_revisions WHERE id=:index_revision_id"),
                {"index_revision_id": post_index_id},
            ).scalar_one() == post_revision_id
    finally:
        engine.dispose()


@pytest.mark.parametrize("journal_failure", ["missing", "corrupt"])
def test_v5_evidence_downgrade_fails_before_destructive_ddl_without_valid_journal(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    journal_failure: str,
) -> None:
    database_path = tmp_path / f"v5-invalid-journal-{journal_failure}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _upgrade(database_url, V4_9_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            space_id = connection.execute(
                text(
                    "INSERT INTO knowledge_spaces (name, description) "
                    "VALUES ('Rollback guard', 'fixture')"
                )
            ).lastrowid
            connection.execute(
                text(
                    """
                    INSERT INTO sources (
                        space_id, source_type, title, file_size, status, metadata_json
                    ) VALUES (:space_id, 'audio', 'guarded source', 10, 'ready', '{}')
                    """
                ),
                {"space_id": space_id},
            )

        _upgrade(database_url, "0007_v5_evidence_index", monkeypatch)
        with engine.begin() as connection:
            if journal_failure == "missing":
                connection.execute(
                    text(
                        "DELETE FROM outbox_messages "
                        "WHERE id='v5-evidence-rollback-0007'"
                    )
                )
            else:
                connection.execute(
                    text(
                        "UPDATE outbox_messages SET payload_json='not-json' "
                        "WHERE id='v5-evidence-rollback-0007'"
                    )
                )

        before = _sqlite_database_snapshot(engine)
        with pytest.raises(RuntimeError, match="rollback journal"):
            _downgrade(database_url, V4_9_REVISION, monkeypatch)
        after = _sqlite_database_snapshot(engine)

        assert after == before
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0007_v5_evidence_index"
            )
    finally:
        engine.dispose()
