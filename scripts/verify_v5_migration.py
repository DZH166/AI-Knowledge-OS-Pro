from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Iterator

from alembic import command
from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from scripts.migrate_v5_evidence_data import (  # noqa: E402
    _alembic_config,
    _read_only_connection,
    _table_names,
    inspect_database,
)


V4_9_REVISION = "0006_v3_6_unified_media_tasks"
ROLLBACK_JOURNAL_ID = "v5-evidence-rollback-0007"
ROLLBACK_JOURNAL_TOPIC = "migration.internal.v5_evidence_rollback"
ROLLBACK_JOURNAL_REVISION = "0007_v5_evidence_index"

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

NEW_DATA_DOWNGRADE_POLICY = {
    "unjournaled_post_upgrade_legacy_rows": "preserve",
    "post_upgrade_changes_to_journaled_legacy_rows": "preserve",
    "pristine_migration_backfill_rows": "delete_when_unreferenced",
    "v5_only_rows_and_columns": "drop_on_downgrade",
}

REQUIRED_V5_TABLES = {
    "index_operations",
    "vector_point_manifests",
    "outbox_messages",
    "agent_runs",
    "agent_plans",
    "agent_requirements",
    "agent_gates",
    "agent_tool_calls",
    "agent_model_calls",
    "agent_commands",
    "agent_events",
    "agent_checkpoints",
    "agent_evidence",
    "requirement_evidence",
    "agent_artifacts",
    "agent_claims",
    "claim_evidence",
}


def _scalar(connection, statement: str, parameters: tuple[Any, ...] = ()) -> int:
    return int(connection.execute(statement, parameters).fetchone()[0])


def _invalid_locator_count(connection) -> int:
    invalid = 0
    for row in connection.execute(
        "SELECT locator_json FROM multimodal_chunks WHERE status='active' ORDER BY id"
    ):
        try:
            locator = json.loads(row[0] or "{}")
        except (TypeError, json.JSONDecodeError):
            invalid += 1
            continue
        if not isinstance(locator, dict) or not locator.get("kind"):
            invalid += 1
    return invalid


def _rollback_journal_validation_errors(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload is not an object"]
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version is not 1")
    if payload.get("migration_revision") != ROLLBACK_JOURNAL_REVISION:
        errors.append("migration_revision does not match 0007")
    if payload.get("phase") != "finalized":
        errors.append("phase is not finalized")
    if payload.get("new_data_policy") != NEW_DATA_DOWNGRADE_POLICY:
        errors.append("new-data downgrade policy does not match the verifier contract")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        errors.append("entries is not a list")
        return errors

    seen_rows: set[tuple[str, int]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entries[{index}] is not an object")
            continue
        action = entry.get("action")
        table_name = entry.get("table")
        row_id = entry.get("row_id")
        if action not in {
            "restore_if_pristine",
            "delete_if_pristine_and_unreferenced",
        }:
            errors.append(f"entries[{index}] has unsupported action")
            continue
        if table_name not in LEGACY_SEMANTIC_COLUMNS:
            errors.append(f"entries[{index}] has unsupported table")
            continue
        if not isinstance(row_id, int):
            errors.append(f"entries[{index}] row_id is not an integer")
            continue
        row_key = (table_name, row_id)
        if row_key in seen_rows:
            errors.append(f"entries[{index}] duplicates {table_name}[{row_id}]")
            continue
        seen_rows.add(row_key)
        snapshot_names = (
            ("before", "after")
            if action == "restore_if_pristine"
            else ("after",)
        )
        expected_columns = set(LEGACY_SEMANTIC_COLUMNS[table_name])
        for snapshot_name in snapshot_names:
            snapshot = entry.get(snapshot_name)
            if not isinstance(snapshot, dict):
                errors.append(f"entries[{index}].{snapshot_name} is not an object")
            elif set(snapshot) != expected_columns or snapshot.get("id") != row_id:
                errors.append(
                    f"entries[{index}].{snapshot_name} does not match "
                    f"{table_name}[{row_id}]"
                )
    return errors


def _rollback_journal_report(connection) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT payload_json
        FROM outbox_messages
        WHERE id=? AND topic=?
        """,
        (ROLLBACK_JOURNAL_ID, ROLLBACK_JOURNAL_TOPIC),
    ).fetchone()
    if row is None:
        return {"present": False}
    try:
        payload = json.loads(row[0] or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        return {
            "present": True,
            "phase": "invalid",
            "error": f"{type(exc).__name__}: {exc}",
            "valid_for_downgrade": False,
            "validation_errors": ["payload is not valid JSON"],
        }
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        entries = []
    valid_entries = [entry for entry in entries if isinstance(entry, dict)]
    validation_errors = _rollback_journal_validation_errors(payload)
    return {
        "present": True,
        "phase": payload.get("phase") if isinstance(payload, dict) else "invalid",
        "restore_entry_count": sum(
            1
            for entry in valid_entries
            if entry.get("action") == "restore_if_pristine"
        ),
        "migration_created_entry_count": sum(
            1
            for entry in valid_entries
            if entry.get("action") == "delete_if_pristine_and_unreferenced"
        ),
        "new_data_policy": (
            payload.get("new_data_policy") if isinstance(payload, dict) else None
        ),
        "valid_for_downgrade": not validation_errors,
        "validation_errors": validation_errors,
    }


def verify_database(database_url: str) -> dict[str, Any]:
    preflight = inspect_database(database_url)
    errors = list(preflight["errors"])
    warnings: list[str] = []
    metrics: dict[str, int] = {}
    rollback_journal: dict[str, Any] = {"present": False}

    if not preflight["at_head"]:
        errors.append(
            "Database is not at the single Alembic head "
            f"{preflight['target_revision']!r}: {preflight['current_revisions']!r}."
        )

    with _read_only_connection(database_url) as connection:
        tables = _table_names(connection)
        missing_tables = sorted(REQUIRED_V5_TABLES - tables)
        if missing_tables:
            errors.append(f"Missing V5 tables: {missing_tables!r}.")

        lifecycle_tables = {
            "sources",
            "source_revisions",
            "multimodal_chunks",
            "index_revisions",
            "vector_point_manifests",
        }
        if lifecycle_tables.issubset(tables):
            metrics = {
                "duplicate_active_revision_sources": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM (
                        SELECT source_id FROM source_revisions
                        WHERE status='active' GROUP BY source_id HAVING COUNT(*) > 1
                    )
                    """,
                ),
                "duplicate_active_index_sources": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM (
                        SELECT source_id FROM index_revisions
                        WHERE status='active' GROUP BY source_id HAVING COUNT(*) > 1
                    )
                    """,
                ),
                "invalid_active_revision_pointers": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM sources AS s
                    LEFT JOIN source_revisions AS sr ON sr.id=s.active_revision_id
                    WHERE s.active_revision_id IS NOT NULL
                      AND (sr.id IS NULL OR sr.source_id != s.id OR sr.status != 'active')
                    """,
                ),
                "invalid_active_index_pointers": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM sources AS s
                    LEFT JOIN index_revisions AS ir ON ir.id=s.active_index_revision_id
                    WHERE s.active_index_revision_id IS NOT NULL
                      AND (
                          ir.id IS NULL OR ir.source_id != s.id OR ir.status != 'active'
                          OR ir.revision_id != s.active_revision_id
                      )
                    """,
                ),
                "active_chunks_missing_hash": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM multimodal_chunks
                    WHERE status='active' AND (content_hash IS NULL OR length(content_hash) != 64)
                    """,
                ),
                "active_chunks_outside_pointer": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM multimodal_chunks AS mc
                    JOIN sources AS s ON s.id=mc.source_id
                    WHERE mc.status='active' AND mc.revision_id != s.active_revision_id
                    """,
                ),
                "orphan_vector_manifests": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM vector_point_manifests AS vm
                    LEFT JOIN multimodal_chunks AS mc ON mc.id=vm.chunk_id
                    LEFT JOIN index_revisions AS ir ON ir.id=vm.index_revision_id
                    WHERE mc.id IS NULL OR ir.id IS NULL
                    """,
                ),
                "documents_without_source": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM documents AS d
                    LEFT JOIN sources AS s ON s.document_id=d.id
                    WHERE d.status != 'deleted' AND s.id IS NULL
                    """,
                ),
                "invalid_active_locators": _invalid_locator_count(connection),
                "legacy_payload_pending_manifests": _scalar(
                    connection,
                    "SELECT COUNT(*) FROM vector_point_manifests WHERE status='legacy_payload_pending'",
                ),
                "legacy_payload_pending_indexes": _scalar(
                    connection,
                    "SELECT COUNT(*) FROM index_revisions WHERE validation_status='legacy_payload_pending'",
                ),
            }
            hard_invariants = (
                "duplicate_active_revision_sources",
                "duplicate_active_index_sources",
                "invalid_active_revision_pointers",
                "invalid_active_index_pointers",
                "active_chunks_missing_hash",
                "active_chunks_outside_pointer",
                "orphan_vector_manifests",
                "documents_without_source",
            )
            for name in hard_invariants:
                if metrics[name]:
                    errors.append(f"{name}={metrics[name]}")
            if metrics["invalid_active_locators"]:
                warnings.append(
                    f"invalid_active_locators={metrics['invalid_active_locators']} require source reprocessing."
                )
            if metrics["legacy_payload_pending_manifests"]:
                warnings.append(
                    "Legacy vector payloads remain pending; run the explicit reconciler after Qdrant is available."
                )
        if "outbox_messages" in tables:
            rollback_journal = _rollback_journal_report(connection)
            if not rollback_journal["present"]:
                errors.append("Missing V5 legacy rollback journal.")
            elif not rollback_journal.get("valid_for_downgrade"):
                errors.append(
                    "V5 legacy rollback journal is invalid for downgrade: "
                    + "; ".join(rollback_journal.get("validation_errors") or [])
                )

    return {
        "ok": not errors,
        "current_revisions": preflight["current_revisions"],
        "target_revision": preflight["target_revision"],
        "required_table_count": len(REQUIRED_V5_TABLES),
        "metrics": metrics,
        "rollback_journal": rollback_journal,
        "new_data_downgrade_policy": NEW_DATA_DOWNGRADE_POLICY,
        "errors": sorted(errors),
        "warnings": sorted(warnings),
    }


@contextmanager
def _database_target(database_url: str) -> Iterator[None]:
    previous = settings.database_url
    settings.database_url = database_url
    try:
        yield
    finally:
        settings.database_url = previous


def _upgrade(database_url: str, revision: str) -> None:
    with _database_target(database_url):
        command.upgrade(_alembic_config(database_url), revision)


def _downgrade(database_url: str, revision: str) -> None:
    with _database_target(database_url):
        command.downgrade(_alembic_config(database_url), revision)


def _seed_populated_v49(database_url: str) -> None:
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            space_id = connection.execute(
                text("INSERT INTO knowledge_spaces (name, description) VALUES ('Roundtrip', 'V4.9 fixture')")
            ).lastrowid
            document_id = connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        space_id, filename, original_filename, file_type, file_size,
                        storage_path, status, parse_status, chunk_status, vector_status,
                        processing_status, content_hash, chunk_count, embedding_fingerprint,
                        index_version
                    ) VALUES (
                        :space_id, 'roundtrip.md', 'roundtrip.md', 'md', 25,
                        'roundtrip.md', 'ready', 'parsed', 'chunked', 'indexed',
                        'completed', :content_hash, 1, 'roundtrip::8d', 'v4.9'
                    )
                    """
                ),
                {
                    "space_id": space_id,
                    "content_hash": sha256(b"roundtrip document").hexdigest(),
                },
            ).lastrowid
            connection.execute(
                text(
                    """
                    INSERT INTO chunks (
                        document_id, space_id, chunk_index, content, content_preview,
                        char_count, page_number, metadata_json, qdrant_point_id
                    ) VALUES (
                        :document_id, :space_id, 0, 'roundtrip exact evidence',
                        'roundtrip exact evidence', 24, 3, '{}', 'roundtrip-point'
                    )
                    """
                ),
                {"document_id": document_id, "space_id": space_id},
            )

            source_id = connection.execute(
                text(
                    """
                    INSERT INTO sources (space_id, source_type, title, file_size, status, metadata_json)
                    VALUES (:space_id, 'audio', 'roundtrip audio', 10, 'ready', '{}')
                    """
                ),
                {"space_id": space_id},
            ).lastrowid
            revision_ids: list[int] = []
            for number, content, point_id in (
                (1, "retire this transcript", "roundtrip-old-point"),
                (2, "keep this transcript", "roundtrip-new-point"),
            ):
                revision_id = connection.execute(
                    text(
                        """
                        INSERT INTO source_revisions (
                            source_id, revision_number, status, content_hash, chunk_count,
                            vector_count, validation_status, metadata_json
                        ) VALUES (:source_id, :number, 'active', :content_hash, 1, 1, 'passed', '{}')
                        """
                    ),
                    {
                        "source_id": source_id,
                        "number": number,
                        "content_hash": sha256(content.encode()).hexdigest(),
                    },
                ).lastrowid
                revision_ids.append(int(revision_id))
                connection.execute(
                    text(
                        """
                        INSERT INTO multimodal_chunks (
                            source_id, revision_id, chunk_index, modality, source_type,
                            content_text, search_text, raw_payload_json, locator_json,
                            status, qdrant_point_id
                        ) VALUES (
                            :source_id, :revision_id, 0, 'audio_transcript', 'audio',
                            :content, :content, '{}', '{}', 'active', :point_id
                        )
                        """
                    ),
                    {
                        "source_id": source_id,
                        "revision_id": revision_id,
                        "content": content,
                        "point_id": point_id,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO index_revisions (
                            source_id, revision_id, status, index_version,
                            point_count, validation_status
                        ) VALUES (:source_id, :revision_id, 'active', 'v4.9', 1, 'passed')
                        """
                    ),
                    {"source_id": source_id, "revision_id": revision_id},
                )
            connection.execute(
                text(
                    """
                    UPDATE sources
                    SET active_revision_id=:revision_id, latest_revision_id=:revision_id
                    WHERE id=:source_id
                    """
                ),
                {"revision_id": revision_ids[-1], "source_id": source_id},
            )
    finally:
        engine.dispose()


def _legacy_semantic_snapshot(database_url: str) -> dict[str, list[dict[str, Any]]]:
    snapshot: dict[str, list[dict[str, Any]]] = {}
    with _read_only_connection(database_url) as connection:
        for table_name, columns in LEGACY_SEMANTIC_COLUMNS.items():
            selected = ", ".join(columns)
            snapshot[table_name] = [
                dict(row)
                for row in connection.execute(
                    f"SELECT {selected} FROM {table_name} ORDER BY id"
                )
            ]
    return snapshot


def _semantic_snapshot_digest(snapshot: dict[str, list[dict[str, Any]]]) -> str:
    encoded = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _downgrade_snapshot(
    database_url: str,
    pre_upgrade_semantics: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    preflight = inspect_database(database_url)
    downgraded_semantics = _legacy_semantic_snapshot(database_url)
    with _read_only_connection(database_url) as connection:
        tables = _table_names(connection)
        legacy_document_count = _scalar(connection, "SELECT COUNT(*) FROM documents")
    return {
        "current_revisions": preflight["current_revisions"],
        "legacy_document_count": legacy_document_count,
        "v5_tables_absent": not bool(REQUIRED_V5_TABLES & tables),
        "semantic_snapshot_matches": downgraded_semantics == pre_upgrade_semantics,
        "pre_upgrade_semantic_digest": _semantic_snapshot_digest(pre_upgrade_semantics),
        "post_downgrade_semantic_digest": _semantic_snapshot_digest(downgraded_semantics),
        "legacy_table_counts": {
            table_name: len(rows) for table_name, rows in downgraded_semantics.items()
        },
    }


def run_roundtrip() -> dict[str, Any]:
    with TemporaryDirectory(prefix="v5-migration-roundtrip-") as directory:
        database_path = Path(directory) / "populated-v49.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        _upgrade(database_url, V4_9_REVISION)
        _seed_populated_v49(database_url)
        pre_upgrade_semantics = _legacy_semantic_snapshot(database_url)
        _upgrade(database_url, "head")
        first_upgrade = verify_database(database_url)
        _downgrade(database_url, V4_9_REVISION)
        downgrade = _downgrade_snapshot(database_url, pre_upgrade_semantics)
        _upgrade(database_url, "head")
        second_upgrade = verify_database(database_url)
        return {
            "ok": bool(
                first_upgrade["ok"]
                and downgrade["current_revisions"] == [V4_9_REVISION]
                and downgrade["legacy_document_count"] == 1
                and downgrade["v5_tables_absent"]
                and downgrade["semantic_snapshot_matches"]
                and second_upgrade["ok"]
                and second_upgrade == first_upgrade
            ),
            "external_access": False,
            "new_data_downgrade_policy": NEW_DATA_DOWNGRADE_POLICY,
            "first_upgrade": first_upgrade,
            "downgrade": downgrade,
            "second_upgrade": second_upgrade,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify V5 SQL migration invariants without accessing Qdrant, Redis, or model providers."
    )
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument(
        "--roundtrip",
        action="store_true",
        help="Create a populated temporary V4.9 SQLite database and run upgrade/downgrade/upgrade.",
    )
    args = parser.parse_args(argv)
    try:
        report = run_roundtrip() if args.roundtrip else verify_database(args.database_url)
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
