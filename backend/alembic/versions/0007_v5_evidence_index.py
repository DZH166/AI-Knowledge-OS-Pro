"""V5 canonical evidence index lifecycle and durable dispatch foundation.

Revision ID: 0007_v5_evidence_index
Revises: 0006_v3_6_unified_media_tasks
Create Date: 2026-08-15

This migration is deliberately database-only.  Legacy Qdrant points are made
traceable through manifests and marked ``legacy_payload_pending``; repairing
their remote payload is a post-upgrade reconciler responsibility.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "0007_v5_evidence_index"
down_revision = "0006_v3_6_unified_media_tasks"
branch_labels = None
depends_on = None


LEGACY_DOCUMENT_PARSER = "v5_legacy_document_backfill"
LEGACY_COLLECTION_UNKNOWN = "legacy_payload_pending"
LEGACY_PAYLOAD_STATUS = "legacy_payload_pending"
ROLLBACK_JOURNAL_ID = "v5-evidence-rollback-0007"
ROLLBACK_JOURNAL_TOPIC = "migration.internal.v5_evidence_rollback"
NEW_DATA_DOWNGRADE_POLICY = {
    "unjournaled_post_upgrade_legacy_rows": "preserve",
    "post_upgrade_changes_to_journaled_legacy_rows": "preserve",
    "pristine_migration_backfill_rows": "delete_when_unreferenced",
    "v5_only_rows_and_columns": "drop_on_downgrade",
}

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


def upgrade() -> None:
    _add_lifecycle_columns()
    _create_durable_index_tables()
    _capture_legacy_rollback_snapshot()
    _repair_duplicate_document_sources()
    _repair_revision_numbers()
    _backfill_multimodal_content_hashes()
    _backfill_document_evidence()
    _backfill_typed_locators()
    _normalize_active_lifecycle()
    _backfill_legacy_point_manifests()
    _finalize_legacy_rollback_snapshot()
    _create_lifecycle_constraints()


def downgrade() -> None:
    rollback_journal = _require_legacy_rollback_journal()
    _drop_lifecycle_constraints()

    tables = _table_names()
    if "vector_point_manifests" in tables:
        op.drop_table("vector_point_manifests")
    if "index_operations" in tables:
        op.drop_table("index_operations")
    _restore_legacy_semantics(rollback_journal)
    if "outbox_messages" in tables:
        op.drop_table("outbox_messages")

    _drop_index_if_exists("ix_multimodal_chunks_content_hash", "multimodal_chunks")
    _drop_index_if_exists("ix_source_revisions_supersedes_revision_id", "source_revisions")
    _drop_index_if_exists("ix_sources_active_index_revision_id", "sources")

    if "index_revisions" in _table_names():
        with op.batch_alter_table("index_revisions") as batch_op:
            if "retired_at" in _column_names("index_revisions"):
                batch_op.drop_column("retired_at")
            if "manifest_digest" in _column_names("index_revisions"):
                batch_op.drop_column("manifest_digest")

    if "multimodal_chunks" in _table_names():
        with op.batch_alter_table("multimodal_chunks") as batch_op:
            if "retired_at" in _column_names("multimodal_chunks"):
                batch_op.drop_column("retired_at")
            if "content_hash" in _column_names("multimodal_chunks"):
                batch_op.drop_column("content_hash")

    if "source_revisions" in _table_names():
        with op.batch_alter_table("source_revisions") as batch_op:
            if "retired_at" in _column_names("source_revisions"):
                batch_op.drop_column("retired_at")
            if "supersedes_revision_id" in _column_names("source_revisions"):
                if (
                    "fk_source_revisions_supersedes_revision_id"
                    in _foreign_key_names("source_revisions")
                ):
                    batch_op.drop_constraint(
                        "fk_source_revisions_supersedes_revision_id",
                        type_="foreignkey",
                    )
                batch_op.drop_column("supersedes_revision_id")

    if "sources" in _table_names():
        with op.batch_alter_table("sources") as batch_op:
            if "retired_at" in _column_names("sources"):
                batch_op.drop_column("retired_at")
            if "active_index_revision_id" in _column_names("sources"):
                batch_op.drop_column("active_index_revision_id")

    if "documents" in _table_names() and "retired_at" in _column_names("documents"):
        with op.batch_alter_table("documents") as batch_op:
            batch_op.drop_column("retired_at")


def _add_lifecycle_columns() -> None:
    _add_column_if_missing("documents", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(
        "sources",
        sa.Column("active_index_revision_id", sa.Integer(), nullable=True),
    )
    _add_column_if_missing("sources", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    if "supersedes_revision_id" not in _column_names("source_revisions"):
        with op.batch_alter_table("source_revisions") as batch_op:
            batch_op.add_column(
                sa.Column("supersedes_revision_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_source_revisions_supersedes_revision_id",
                "source_revisions",
                ["supersedes_revision_id"],
                ["id"],
            )
    _add_column_if_missing(
        "source_revisions",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        "multimodal_chunks",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    _add_column_if_missing(
        "multimodal_chunks",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        "index_revisions",
        sa.Column("manifest_digest", sa.String(length=64), nullable=True),
    )
    _add_column_if_missing(
        "index_revisions",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )

    _create_index_if_missing(
        "ix_sources_active_index_revision_id",
        "sources",
        ["active_index_revision_id"],
    )
    _create_index_if_missing(
        "ix_source_revisions_supersedes_revision_id",
        "source_revisions",
        ["supersedes_revision_id"],
    )
    _create_index_if_missing(
        "ix_multimodal_chunks_content_hash",
        "multimodal_chunks",
        ["content_hash"],
    )


def _create_durable_index_tables() -> None:
    tables = _table_names()
    if "index_operations" not in tables:
        op.create_table(
            "index_operations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("command_id", sa.String(length=120), nullable=False),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=True),
            sa.Column("index_revision_id", sa.Integer(), sa.ForeignKey("index_revisions.id"), nullable=True),
            sa.Column("operation_type", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("draft_hash", sa.String(length=64), nullable=False),
            sa.Column("parser_name", sa.String(length=80), nullable=True),
            sa.Column("parser_version", sa.String(length=80), nullable=True),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        for name, columns, unique in [
            ("ix_index_operations_command_id", ["command_id"], True),
            ("ix_index_operations_source_id", ["source_id"], False),
            ("ix_index_operations_revision_id", ["revision_id"], False),
            ("ix_index_operations_index_revision_id", ["index_revision_id"], False),
            ("ix_index_operations_operation_type", ["operation_type"], False),
            ("ix_index_operations_status", ["status"], False),
            ("ix_index_operations_draft_hash", ["draft_hash"], False),
        ]:
            op.create_index(name, "index_operations", columns, unique=unique)

    tables = _table_names()
    if "vector_point_manifests" not in tables:
        op.create_table(
            "vector_point_manifests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "operation_id",
                sa.String(length=36),
                sa.ForeignKey("index_operations.id"),
                nullable=False,
            ),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("revision_id", sa.Integer(), sa.ForeignKey("source_revisions.id"), nullable=False),
            sa.Column(
                "index_revision_id",
                sa.Integer(),
                sa.ForeignKey("index_revisions.id"),
                nullable=False,
            ),
            sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("multimodal_chunks.id"), nullable=False),
            sa.Column("collection_name", sa.String(length=160), nullable=False),
            sa.Column("point_id", sa.String(length=80), nullable=False),
            sa.Column("payload_digest", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="expected"),
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "collection_name",
                "point_id",
                name="uq_vector_manifest_collection_point",
            ),
        )
        for name, columns in [
            ("ix_vector_point_manifests_id", ["id"]),
            ("ix_vector_point_manifests_operation_id", ["operation_id"]),
            ("ix_vector_point_manifests_source_id", ["source_id"]),
            ("ix_vector_point_manifests_revision_id", ["revision_id"]),
            ("ix_vector_point_manifests_index_revision_id", ["index_revision_id"]),
            ("ix_vector_point_manifests_chunk_id", ["chunk_id"]),
            ("ix_vector_point_manifests_point_id", ["point_id"]),
            ("ix_vector_point_manifests_status", ["status"]),
        ]:
            op.create_index(name, "vector_point_manifests", columns)

    tables = _table_names()
    if "outbox_messages" not in tables:
        op.create_table(
            "outbox_messages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("topic", sa.String(length=120), nullable=False),
            sa.Column("aggregate_type", sa.String(length=80), nullable=False),
            sa.Column("aggregate_id", sa.String(length=80), nullable=False),
            sa.Column("dedupe_key", sa.String(length=200), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("lease_owner", sa.String(length=120), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        for name, columns, unique in [
            ("ix_outbox_messages_topic", ["topic"], False),
            ("ix_outbox_messages_aggregate_type", ["aggregate_type"], False),
            ("ix_outbox_messages_aggregate_id", ["aggregate_id"], False),
            ("ix_outbox_messages_dedupe_key", ["dedupe_key"], True),
            ("ix_outbox_messages_status", ["status"], False),
            ("ix_outbox_messages_lease_expires_at", ["lease_expires_at"], False),
        ]:
            op.create_index(name, "outbox_messages", columns, unique=unique)


def _capture_legacy_rollback_snapshot() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM outbox_messages WHERE id=:journal_id"),
        {"journal_id": ROLLBACK_JOURNAL_ID},
    ).scalar()
    if existing is not None:
        return
    payload = {
        "schema_version": 1,
        "migration_revision": revision,
        "phase": "captured",
        "tables": {
            table_name: _semantic_rows(table_name)
            for table_name in LEGACY_SEMANTIC_COLUMNS
        },
    }
    bind.execute(
        sa.text(
            """
            INSERT INTO outbox_messages (
                id, topic, aggregate_type, aggregate_id, dedupe_key,
                payload_json, status, published_at
            ) VALUES (
                :id, :topic, 'alembic_migration', :aggregate_id, :dedupe_key,
                :payload_json, 'published', CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": ROLLBACK_JOURNAL_ID,
            "topic": ROLLBACK_JOURNAL_TOPIC,
            "aggregate_id": revision,
            "dedupe_key": f"{ROLLBACK_JOURNAL_TOPIC}:{revision}",
            "payload_json": _canonical_json(payload),
        },
    )


def _finalize_legacy_rollback_snapshot() -> None:
    journal = _load_legacy_rollback_journal()
    if not journal or journal.get("phase") != "captured":
        return
    entries: list[dict[str, Any]] = []
    before_tables = journal.get("tables") or {}
    for table_name in LEGACY_SEMANTIC_COLUMNS:
        before_rows = {
            int(row["id"]): row
            for row in before_tables.get(table_name, [])
            if isinstance(row, dict) and row.get("id") is not None
        }
        after_rows = {int(row["id"]): row for row in _semantic_rows(table_name)}
        for row_id, before in before_rows.items():
            after = after_rows.get(row_id)
            if after is not None and after != before:
                entries.append(
                    {
                        "action": "restore_if_pristine",
                        "table": table_name,
                        "row_id": row_id,
                        "before": before,
                        "after": after,
                    }
                )
        for row_id in sorted(after_rows.keys() - before_rows.keys()):
            entries.append(
                {
                    "action": "delete_if_pristine_and_unreferenced",
                    "table": table_name,
                    "row_id": row_id,
                    "after": after_rows[row_id],
                }
            )
    finalized = {
        "schema_version": 1,
        "migration_revision": revision,
        "phase": "finalized",
        "new_data_policy": NEW_DATA_DOWNGRADE_POLICY,
        "entries": entries,
    }
    op.get_bind().execute(
        sa.text(
            """
            UPDATE outbox_messages
            SET payload_json=:payload_json, updated_at=CURRENT_TIMESTAMP
            WHERE id=:journal_id
            """
        ),
        {
            "journal_id": ROLLBACK_JOURNAL_ID,
            "payload_json": _canonical_json(finalized),
        },
    )


def _load_legacy_rollback_journal() -> dict[str, Any] | None:
    if "outbox_messages" not in _table_names():
        return None
    raw = op.get_bind().execute(
        sa.text(
            """
            SELECT payload_json
            FROM outbox_messages
            WHERE id=:journal_id AND topic=:topic
            """
        ),
        {"journal_id": ROLLBACK_JOURNAL_ID, "topic": ROLLBACK_JOURNAL_TOPIC},
    ).scalar()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("migration_revision") != revision:
        return None
    return payload


def _require_legacy_rollback_journal() -> dict[str, Any]:
    journal = _load_legacy_rollback_journal()
    invalid_reason: str | None = None
    if journal is None:
        invalid_reason = "missing, unreadable, or belongs to another migration"
    elif journal.get("schema_version") != 1:
        invalid_reason = "unsupported schema_version"
    elif journal.get("phase") != "finalized":
        invalid_reason = f"phase is {journal.get('phase')!r}, expected 'finalized'"
    elif journal.get("new_data_policy") != NEW_DATA_DOWNGRADE_POLICY:
        invalid_reason = "new-data downgrade policy does not match this migration"
    elif not isinstance(journal.get("entries"), list):
        invalid_reason = "entries is not a list"
    else:
        seen_rows: set[tuple[str, int]] = set()
        for entry in journal["entries"]:
            if not isinstance(entry, dict):
                invalid_reason = "an entry is not an object"
                break
            action = entry.get("action")
            table_name = entry.get("table")
            row_id = entry.get("row_id")
            if action not in {
                "restore_if_pristine",
                "delete_if_pristine_and_unreferenced",
            }:
                invalid_reason = f"unsupported entry action {action!r}"
                break
            if table_name not in LEGACY_SEMANTIC_COLUMNS:
                invalid_reason = f"unsupported entry table {table_name!r}"
                break
            if not isinstance(row_id, int):
                invalid_reason = "entry row_id is not an integer"
                break
            row_key = (table_name, row_id)
            if row_key in seen_rows:
                invalid_reason = f"duplicate entry for {table_name}[{row_id}]"
                break
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
                    invalid_reason = f"entry {snapshot_name} snapshot is not an object"
                    break
                if set(snapshot) != expected_columns or snapshot.get("id") != row_id:
                    invalid_reason = (
                        f"entry {snapshot_name} snapshot does not match "
                        f"{table_name}[{row_id}]"
                    )
                    break
            if invalid_reason is not None:
                break
    if invalid_reason is not None:
        raise RuntimeError(
            "Refusing 0007 downgrade because the rollback journal is invalid "
            f"({invalid_reason}); no destructive DDL has been executed."
        )
    return journal


def _restore_legacy_semantics(journal: dict[str, Any] | None) -> None:
    if not journal or journal.get("phase") != "finalized":
        raise RuntimeError("A validated rollback journal is required before restoring V4.9 data.")
    entries = [entry for entry in journal.get("entries", []) if isinstance(entry, dict)]
    restore_entries = {
        (entry.get("table"), int(entry["row_id"])): entry
        for entry in entries
        if entry.get("action") == "restore_if_pristine"
        and entry.get("table") in LEGACY_SEMANTIC_COLUMNS
        and entry.get("row_id") is not None
    }
    for table_name in (
        "source_revisions",
        "multimodal_chunks",
        "index_revisions",
        "sources",
    ):
        for (entry_table, row_id), entry in restore_entries.items():
            if entry_table != table_name:
                continue
            current = _semantic_row(table_name, row_id)
            if current is not None and current == entry.get("after"):
                before = entry.get("before")
                if isinstance(before, dict):
                    _update_semantic_row(table_name, row_id, before)

    migration_created: dict[str, set[int]] = {
        table_name: set() for table_name in LEGACY_SEMANTIC_COLUMNS
    }
    created_after: dict[str, dict[int, Any]] = {
        table_name: {} for table_name in LEGACY_SEMANTIC_COLUMNS
    }
    for entry in entries:
        table_name = entry.get("table")
        if (
            entry.get("action") != "delete_if_pristine_and_unreferenced"
            or table_name not in LEGACY_SEMANTIC_COLUMNS
            or entry.get("row_id") is None
        ):
            continue
        row_id = int(entry["row_id"])
        migration_created[table_name].add(row_id)
        created_after[table_name][row_id] = entry.get("after")
    created_candidates = {
        table_name: {
            row_id
            for row_id in row_ids
            if _semantic_row(table_name, row_id)
            == created_after[table_name][row_id]
        }
        for table_name, row_ids in migration_created.items()
    }

    changed = True
    while changed:
        changed = False
        if _cascade_preserved_migration_parents(
            migration_created,
            created_candidates,
        ):
            changed = True
        for table_name in (
            "index_revisions",
            "multimodal_chunks",
            "source_revisions",
            "sources",
        ):
            for row_id in tuple(created_candidates[table_name]):
                if _created_row_has_preserved_dependencies(
                    table_name,
                    row_id,
                    created_candidates,
                ):
                    created_candidates[table_name].remove(row_id)
                    changed = True

    if created_candidates["index_revisions"]:
        _clear_pointer_for_candidates(
            "active_index_revision_id",
            created_candidates["index_revisions"],
        )
        _delete_semantic_rows("index_revisions", created_candidates["index_revisions"])
    if created_candidates["multimodal_chunks"]:
        _delete_semantic_rows("multimodal_chunks", created_candidates["multimodal_chunks"])
    if created_candidates["source_revisions"]:
        for column_name in ("active_revision_id", "latest_revision_id"):
            _clear_pointer_for_candidates(
                column_name,
                created_candidates["source_revisions"],
            )
        _delete_semantic_rows("source_revisions", created_candidates["source_revisions"])
    if created_candidates["sources"]:
        _delete_semantic_rows("sources", created_candidates["sources"])


def _created_row_has_preserved_dependencies(
    table_name: str,
    row_id: int,
    candidates: dict[str, set[int]],
) -> bool:
    if table_name == "index_revisions":
        return _has_reference_outside_candidates(
            "sources",
            "active_index_revision_id",
            row_id,
            candidates["sources"],
        )
    if table_name == "multimodal_chunks":
        if _has_reference_outside_candidates(
            "multimodal_chunks",
            "parent_chunk_id",
            row_id,
            candidates["multimodal_chunks"],
        ):
            return True
        return any(
            _has_any_reference(child_table, foreign_key, row_id)
            for child_table, foreign_key in (
                ("citation_locators", "chunk_id"),
                ("error_archives", "chunk_id"),
                ("learning_artifacts", "chunk_id"),
            )
        )
    if table_name == "source_revisions":
        if _has_reference_outside_candidates(
            "multimodal_chunks",
            "revision_id",
            row_id,
            candidates["multimodal_chunks"],
        ) or _has_reference_outside_candidates(
            "index_revisions",
            "revision_id",
            row_id,
            candidates["index_revisions"],
        ):
            return True
        if any(
            _has_any_reference(child_table, foreign_key, row_id)
            for child_table, foreign_key in (
                ("citation_locators", "revision_id"),
                ("transcript_segments", "revision_id"),
                ("visual_frames", "revision_id"),
            )
        ):
            return True
        return any(
            _has_reference_outside_candidates(
                "sources",
                pointer,
                row_id,
                candidates["sources"],
            )
            for pointer in ("active_revision_id", "latest_revision_id")
        )
    if table_name == "sources":
        if any(
            _has_reference_outside_candidates(
                child_table,
                "source_id",
                row_id,
                candidates[child_table],
            )
            for child_table in (
                "source_revisions",
                "multimodal_chunks",
                "index_revisions",
            )
        ):
            return True
        return any(
            _has_any_reference(child_table, "source_id", row_id)
            for child_table in (
                "citation_locators",
                "error_archives",
                "ingestion_jobs",
                "learning_artifacts",
                "media_assets",
                "transcript_segments",
                "visual_frames",
            )
        )
    return True


def _cascade_preserved_migration_parents(
    migration_created: dict[str, set[int]],
    candidates: dict[str, set[int]],
) -> bool:
    changed = False
    preserved_sources = migration_created["sources"] - candidates["sources"]
    for source_id in preserved_sources:
        for table_name in (
            "source_revisions",
            "multimodal_chunks",
            "index_revisions",
        ):
            child_ids = set(
                int(row_id)
                for row_id in op.get_bind().execute(
                    sa.text(
                        f"SELECT id FROM {table_name} WHERE source_id=:source_id"
                    ),
                    {"source_id": source_id},
                ).scalars()
            )
            removable = child_ids & candidates[table_name]
            if removable:
                candidates[table_name].difference_update(removable)
                changed = True

    preserved_revisions = (
        migration_created["source_revisions"] - candidates["source_revisions"]
    )
    for revision_id in preserved_revisions:
        for table_name in ("multimodal_chunks", "index_revisions"):
            child_ids = set(
                int(row_id)
                for row_id in op.get_bind().execute(
                    sa.text(
                        f"SELECT id FROM {table_name} WHERE revision_id=:revision_id"
                    ),
                    {"revision_id": revision_id},
                ).scalars()
            )
            removable = child_ids & candidates[table_name]
            if removable:
                candidates[table_name].difference_update(removable)
                changed = True
    return changed


def _has_reference_outside_candidates(
    table_name: str,
    foreign_key: str,
    row_id: int,
    candidate_ids: set[int],
) -> bool:
    if table_name not in _table_names() or foreign_key not in _column_names(table_name):
        return False
    referenced_ids = op.get_bind().execute(
        sa.text(
            f"SELECT id FROM {table_name} WHERE {foreign_key}=:row_id ORDER BY id"
        ),
        {"row_id": row_id},
    ).scalars()
    return any(int(referenced_id) not in candidate_ids for referenced_id in referenced_ids)


def _has_any_reference(table_name: str, foreign_key: str, row_id: int) -> bool:
    if table_name not in _table_names() or foreign_key not in _column_names(table_name):
        return False
    return bool(
        op.get_bind().execute(
            sa.text(
                f"SELECT 1 FROM {table_name} WHERE {foreign_key}=:row_id LIMIT 1"
            ),
            {"row_id": row_id},
        ).scalar()
    )


def _clear_pointer_for_candidates(column_name: str, candidate_ids: set[int]) -> None:
    if not candidate_ids or column_name not in _column_names("sources"):
        return
    placeholders = ", ".join(f":candidate_{index}" for index, _ in enumerate(candidate_ids))
    parameters = {
        f"candidate_{index}": row_id
        for index, row_id in enumerate(sorted(candidate_ids))
    }
    op.get_bind().execute(
        sa.text(
            f"UPDATE sources SET {column_name}=NULL WHERE {column_name} IN ({placeholders})"
        ),
        parameters,
    )


def _delete_semantic_rows(table_name: str, row_ids: set[int]) -> None:
    if not row_ids:
        return
    placeholders = ", ".join(f":row_{index}" for index, _ in enumerate(row_ids))
    parameters = {
        f"row_{index}": row_id for index, row_id in enumerate(sorted(row_ids))
    }
    op.get_bind().execute(
        sa.text(f"DELETE FROM {table_name} WHERE id IN ({placeholders})"),
        parameters,
    )


def _semantic_rows(table_name: str) -> list[dict[str, Any]]:
    columns = LEGACY_SEMANTIC_COLUMNS[table_name]
    selected = ", ".join(columns)
    rows = op.get_bind().execute(
        sa.text(f"SELECT {selected} FROM {table_name} ORDER BY id")
    ).mappings()
    return [_normalized_snapshot(row, columns) for row in rows]


def _semantic_row(table_name: str, row_id: int) -> dict[str, Any] | None:
    columns = LEGACY_SEMANTIC_COLUMNS[table_name]
    selected = ", ".join(columns)
    row = op.get_bind().execute(
        sa.text(f"SELECT {selected} FROM {table_name} WHERE id=:row_id"),
        {"row_id": row_id},
    ).mappings().first()
    return _normalized_snapshot(row, columns) if row is not None else None


def _normalized_snapshot(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for column in columns:
        value = row[column]
        if isinstance(value, bytes):
            value = {"bytes_hex": value.hex()}
        elif callable(getattr(value, "isoformat", None)):
            value = value.isoformat()
        normalized[column] = value
    return normalized


def _update_semantic_row(
    table_name: str,
    row_id: int,
    snapshot: dict[str, Any],
) -> None:
    columns = [
        column
        for column in LEGACY_SEMANTIC_COLUMNS[table_name]
        if column != "id"
    ]
    assignments = ", ".join(f"{column}=:{column}" for column in columns)
    parameters = {column: snapshot.get(column) for column in columns}
    parameters["row_id"] = row_id
    op.get_bind().execute(
        sa.text(f"UPDATE {table_name} SET {assignments} WHERE id=:row_id"),
        parameters,
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _repair_duplicate_document_sources() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            """
            SELECT document_id
            FROM sources
            WHERE document_id IS NOT NULL
            GROUP BY document_id
            HAVING COUNT(*) > 1
            """
        )
    ).scalars()
    for document_id in list(duplicates):
        source_ids = list(
            bind.execute(
                sa.text("SELECT id FROM sources WHERE document_id=:document_id ORDER BY id"),
                {"document_id": document_id},
            ).scalars()
        )
        for duplicate_id in source_ids[1:]:
            bind.execute(
                sa.text("UPDATE sources SET document_id=NULL WHERE id=:source_id"),
                {"source_id": duplicate_id},
            )


def _repair_revision_numbers() -> None:
    bind = op.get_bind()
    source_ids = list(bind.execute(sa.text("SELECT id FROM sources ORDER BY id")).scalars())
    for source_id in source_ids:
        revisions = bind.execute(
            sa.text(
                """
                SELECT id, revision_number
                FROM source_revisions
                WHERE source_id=:source_id
                ORDER BY revision_number, id
                """
            ),
            {"source_id": source_id},
        ).mappings()
        used: set[int] = set()
        next_number = 1
        for row in revisions:
            number = int(row["revision_number"] or 0)
            if number <= 0 or number in used:
                while next_number in used:
                    next_number += 1
                number = next_number
                bind.execute(
                    sa.text("UPDATE source_revisions SET revision_number=:number WHERE id=:revision_id"),
                    {"number": number, "revision_id": row["id"]},
                )
            used.add(number)
            next_number = max(next_number, number + 1)


def _backfill_multimodal_content_hashes() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, content_text
            FROM multimodal_chunks
            WHERE content_hash IS NULL OR content_hash = ''
            """
        )
    ).mappings()
    for row in rows:
        bind.execute(
            sa.text("UPDATE multimodal_chunks SET content_hash=:digest WHERE id=:chunk_id"),
            {"digest": _sha256(str(row["content_text"] or "")), "chunk_id": row["id"]},
        )


def _backfill_document_evidence() -> None:
    bind = op.get_bind()
    documents = list(
        bind.execute(
            sa.text(
                """
                SELECT id, space_id, filename, original_filename, file_type, content_type,
                       file_size, storage_path, status, content_hash, title, source_type,
                       embedding_provider, embedding_model, embedding_dimensions,
                       embedding_fingerprint, index_version
                FROM documents
                ORDER BY id
                """
            )
        ).mappings()
    )
    for document in documents:
        source = bind.execute(
            sa.text(
                """
                SELECT * FROM sources
                WHERE document_id=:document_id
                ORDER BY id
                LIMIT 1
                """
            ),
            {"document_id": document["id"]},
        ).mappings().first()
        source_type = _document_source_type(document["file_type"])
        if source is None:
            source_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO sources (
                        space_id, document_id, source_type, title, original_filename,
                        mime_type, file_size, storage_path, content_hash, status,
                        metadata_json
                    ) VALUES (
                        :space_id, :document_id, :source_type, :title, :original_filename,
                        :mime_type, :file_size, :storage_path, :content_hash, :status,
                        :metadata_json
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
                    "status": document["status"] or "uploaded",
                    "metadata_json": json.dumps(
                        {"legacy_document": True, "canonical_backfill": revision},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ).lastrowid
        else:
            source_id = source["id"]
            bind.execute(
                sa.text(
                    """
                    UPDATE sources
                    SET space_id=:space_id,
                        source_type=:source_type,
                        title=COALESCE(title, :title),
                        original_filename=COALESCE(original_filename, :original_filename),
                        mime_type=COALESCE(mime_type, :mime_type),
                        file_size=:file_size,
                        storage_path=COALESCE(storage_path, :storage_path),
                        content_hash=:content_hash,
                        status=:status
                    WHERE id=:source_id
                    """
                ),
                {
                    "space_id": document["space_id"],
                    "source_type": source_type,
                    "title": document["title"] or document["original_filename"],
                    "original_filename": document["original_filename"],
                    "mime_type": document["content_type"],
                    "file_size": document["file_size"] or 0,
                    "storage_path": document["storage_path"],
                    "content_hash": document["content_hash"],
                    "status": document["status"] or "uploaded",
                    "source_id": source_id,
                },
            )

        chunks = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, chunk_index, content, page_number, heading_path,
                           section_title, token_count, metadata_json, qdrant_point_id
                    FROM chunks
                    WHERE document_id=:document_id
                    ORDER BY chunk_index, id
                    """
                ),
                {"document_id": document["id"]},
            ).mappings()
        )
        chunk_hashes = [_sha256(str(chunk["content"] or "")) for chunk in chunks]
        revision_content_hash = document["content_hash"] or _sha256("\n".join(chunk_hashes))
        canonical_revision = bind.execute(
            sa.text(
                """
                SELECT *
                FROM source_revisions
                WHERE source_id=:source_id AND parser_name=:parser_name
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"source_id": source_id, "parser_name": LEGACY_DOCUMENT_PARSER},
        ).mappings().first()
        previous_active_id = bind.execute(
            sa.text(
                """
                SELECT id FROM source_revisions
                WHERE source_id=:source_id AND status='active'
                ORDER BY revision_number DESC, id DESC
                LIMIT 1
                """
            ),
            {"source_id": source_id},
        ).scalar()
        if canonical_revision is None:
            next_revision_number = int(
                bind.execute(
                    sa.text(
                        "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM source_revisions WHERE source_id=:source_id"
                    ),
                    {"source_id": source_id},
                ).scalar_one()
            )
            canonical_revision_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO source_revisions (
                        source_id, document_id, revision_number, status, parser_name,
                        parser_version, content_hash, chunk_count, vector_count,
                        validation_status, metadata_json, supersedes_revision_id,
                        activated_at
                    ) VALUES (
                        :source_id, :document_id, :revision_number, 'active', :parser_name,
                        :parser_version, :content_hash, :chunk_count, :vector_count,
                        :validation_status, :metadata_json, :supersedes_revision_id,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "source_id": source_id,
                    "document_id": document["id"],
                    "revision_number": next_revision_number,
                    "parser_name": LEGACY_DOCUMENT_PARSER,
                    "parser_version": revision,
                    "content_hash": revision_content_hash,
                    "chunk_count": len(chunks),
                    "vector_count": sum(1 for chunk in chunks if chunk["qdrant_point_id"]),
                    "validation_status": "passed" if chunks else "empty",
                    "metadata_json": json.dumps(
                        {"legacy_document": True, "canonical_backfill": revision},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "supersedes_revision_id": previous_active_id,
                },
            ).lastrowid
        else:
            canonical_revision_id = canonical_revision["id"]
            bind.execute(
                sa.text(
                    """
                    UPDATE source_revisions
                    SET document_id=:document_id,
                        status='active',
                        content_hash=:content_hash,
                        chunk_count=:chunk_count,
                        vector_count=:vector_count,
                        validation_status=:validation_status,
                        parser_version=:parser_version,
                        activated_at=COALESCE(activated_at, CURRENT_TIMESTAMP)
                    WHERE id=:revision_id
                    """
                ),
                {
                    "document_id": document["id"],
                    "content_hash": revision_content_hash,
                    "chunk_count": len(chunks),
                    "vector_count": sum(1 for chunk in chunks if chunk["qdrant_point_id"]),
                    "validation_status": "passed" if chunks else "empty",
                    "parser_version": revision,
                    "revision_id": canonical_revision_id,
                },
            )

        active_legacy_chunk_ids: set[int] = set()
        for chunk, chunk_hash in zip(chunks, chunk_hashes, strict=True):
            active_legacy_chunk_ids.add(int(chunk["id"]))
            locator = {
                "kind": "document_page" if chunk["page_number"] is not None else "document_chunk",
                "source_type": "document",
                "source_id": source_id,
                "document_id": document["id"],
                "document_name": document["original_filename"],
                "legacy_chunk_id": chunk["id"],
                "page_number": chunk["page_number"],
                "heading_path": chunk["heading_path"],
                "section_title": chunk["section_title"],
            }
            canonical_chunk_id = bind.execute(
                sa.text(
                    """
                    SELECT id
                    FROM multimodal_chunks
                    WHERE revision_id=:revision_id AND legacy_chunk_id=:legacy_chunk_id
                    ORDER BY id
                    LIMIT 1
                    """
                ),
                {
                    "revision_id": canonical_revision_id,
                    "legacy_chunk_id": chunk["id"],
                },
            ).scalar()
            values = {
                "source_id": source_id,
                "revision_id": canonical_revision_id,
                "legacy_chunk_id": chunk["id"],
                "chunk_index": chunk["chunk_index"],
                "source_type": source_type,
                "content": chunk["content"],
                "content_hash": chunk_hash,
                "raw_payload_json": chunk["metadata_json"] or "{}",
                "locator_json": json.dumps(locator, ensure_ascii=False, sort_keys=True),
                "page_number": chunk["page_number"],
                "qdrant_point_id": chunk["qdrant_point_id"],
            }
            if canonical_chunk_id is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO multimodal_chunks (
                            source_id, revision_id, legacy_chunk_id, chunk_index,
                            modality, source_type, content_text, content_hash,
                            search_text, raw_payload_json, locator_json, page_number,
                            status, qdrant_point_id
                        ) VALUES (
                            :source_id, :revision_id, :legacy_chunk_id, :chunk_index,
                            'text', :source_type, :content, :content_hash,
                            :content, :raw_payload_json, :locator_json, :page_number,
                            'active', :qdrant_point_id
                        )
                        """
                    ),
                    values,
                )
            else:
                values["chunk_id"] = canonical_chunk_id
                bind.execute(
                    sa.text(
                        """
                        UPDATE multimodal_chunks
                        SET source_id=:source_id,
                            chunk_index=:chunk_index,
                            modality='text',
                            source_type=:source_type,
                            content_text=:content,
                            content_hash=:content_hash,
                            search_text=:content,
                            raw_payload_json=:raw_payload_json,
                            locator_json=:locator_json,
                            page_number=:page_number,
                            status='active',
                            qdrant_point_id=:qdrant_point_id,
                            retired_at=NULL
                        WHERE id=:chunk_id
                        """
                    ),
                    values,
                )

        stale_rows = bind.execute(
            sa.text(
                """
                SELECT id, legacy_chunk_id
                FROM multimodal_chunks
                WHERE revision_id=:revision_id
                """
            ),
            {"revision_id": canonical_revision_id},
        ).mappings()
        for stale in stale_rows:
            if stale["legacy_chunk_id"] is None or int(stale["legacy_chunk_id"]) not in active_legacy_chunk_ids:
                bind.execute(
                    sa.text(
                        """
                        UPDATE multimodal_chunks
                        SET status='retired', retired_at=COALESCE(retired_at, CURRENT_TIMESTAMP)
                        WHERE id=:chunk_id
                        """
                    ),
                    {"chunk_id": stale["id"]},
                )

        point_count = sum(1 for chunk in chunks if chunk["qdrant_point_id"])
        manifest_digest = _sha256(
            "|".join(
                sorted(
                    f"{chunk['id']}:{chunk['qdrant_point_id']}:{chunk_hash}"
                    for chunk, chunk_hash in zip(chunks, chunk_hashes, strict=True)
                )
            )
        )
        canonical_index_id = bind.execute(
            sa.text(
                """
                SELECT id
                FROM index_revisions
                WHERE revision_id=:revision_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"revision_id": canonical_revision_id},
        ).scalar()
        index_status = "active" if point_count else "empty"
        validation_status = LEGACY_PAYLOAD_STATUS if point_count else "empty"
        if canonical_index_id is None:
            canonical_index_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO index_revisions (
                        source_id, revision_id, status, index_version,
                        embedding_provider, embedding_model, embedding_dimensions,
                        embedding_fingerprint, qdrant_collection, point_count,
                        validation_status, manifest_digest, activated_at
                    ) VALUES (
                        :source_id, :revision_id, :status, :index_version,
                        :embedding_provider, :embedding_model, :embedding_dimensions,
                        :embedding_fingerprint, NULL, :point_count,
                        :validation_status, :manifest_digest,
                        CASE WHEN :status = 'active' THEN CURRENT_TIMESTAMP ELSE NULL END
                    )
                    """
                ),
                {
                    "source_id": source_id,
                    "revision_id": canonical_revision_id,
                    "status": index_status,
                    "index_version": document["index_version"] or "legacy",
                    "embedding_provider": document["embedding_provider"],
                    "embedding_model": document["embedding_model"],
                    "embedding_dimensions": document["embedding_dimensions"],
                    "embedding_fingerprint": document["embedding_fingerprint"],
                    "point_count": point_count,
                    "validation_status": validation_status,
                    "manifest_digest": manifest_digest,
                },
            ).lastrowid
        else:
            bind.execute(
                sa.text(
                    """
                    UPDATE index_revisions
                    SET source_id=:source_id,
                        status=:status,
                        index_version=:index_version,
                        embedding_provider=:embedding_provider,
                        embedding_model=:embedding_model,
                        embedding_dimensions=:embedding_dimensions,
                        embedding_fingerprint=:embedding_fingerprint,
                        point_count=:point_count,
                        validation_status=:validation_status,
                        manifest_digest=:manifest_digest,
                        activated_at=CASE
                            WHEN :status = 'active' THEN COALESCE(activated_at, CURRENT_TIMESTAMP)
                            ELSE activated_at
                        END
                    WHERE id=:index_revision_id
                    """
                ),
                {
                    "source_id": source_id,
                    "status": index_status,
                    "index_version": document["index_version"] or "legacy",
                    "embedding_provider": document["embedding_provider"],
                    "embedding_model": document["embedding_model"],
                    "embedding_dimensions": document["embedding_dimensions"],
                    "embedding_fingerprint": document["embedding_fingerprint"],
                    "point_count": point_count,
                    "validation_status": validation_status,
                    "manifest_digest": manifest_digest,
                    "index_revision_id": canonical_index_id,
                },
            )

        bind.execute(
            sa.text(
                """
                UPDATE sources
                SET active_revision_id=:revision_id,
                    latest_revision_id=:revision_id,
                    active_index_revision_id=:index_revision_id
                WHERE id=:source_id
                """
            ),
            {
                "revision_id": canonical_revision_id,
                "index_revision_id": canonical_index_id if point_count else None,
                "source_id": source_id,
            },
        )


def _backfill_typed_locators() -> None:
    bind = op.get_bind()
    chunks = bind.execute(
        sa.text(
            """
            SELECT id, source_id, revision_id, modality, source_type, locator_json,
                   page_number
            FROM multimodal_chunks
            ORDER BY id
            """
        )
    ).mappings()
    for chunk in chunks:
        try:
            locator = json.loads(chunk["locator_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            locator = {}
        if not isinstance(locator, dict):
            locator = {}
        locator.setdefault(
            "kind",
            _legacy_locator_kind(
                modality=str(chunk["modality"] or ""),
                source_type=str(chunk["source_type"] or ""),
                page_number=chunk["page_number"],
            ),
        )
        locator.setdefault("source_type", chunk["source_type"] or "unknown")
        locator.setdefault("source_id", chunk["source_id"])
        locator.setdefault("revision_id", chunk["revision_id"])
        locator.setdefault("chunk_id", chunk["id"])
        bind.execute(
            sa.text(
                "UPDATE multimodal_chunks SET locator_json=:locator_json WHERE id=:chunk_id"
            ),
            {
                "chunk_id": chunk["id"],
                "locator_json": json.dumps(
                    locator,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        )


def _normalize_active_lifecycle() -> None:
    bind = op.get_bind()
    source_ids = list(bind.execute(sa.text("SELECT id FROM sources ORDER BY id")).scalars())
    for source_id in source_ids:
        source = bind.execute(
            sa.text(
                "SELECT active_revision_id, active_index_revision_id FROM sources WHERE id=:source_id"
            ),
            {"source_id": source_id},
        ).mappings().one()
        revisions = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, revision_number, status, validation_status
                    FROM source_revisions
                    WHERE source_id=:source_id
                    ORDER BY revision_number DESC, id DESC
                    """
                ),
                {"source_id": source_id},
            ).mappings()
        )
        revision_by_id = {row["id"]: row for row in revisions}
        canonical_revision_id: int | None = None
        pointed_revision = revision_by_id.get(source["active_revision_id"])
        if pointed_revision is not None and pointed_revision["status"] in {"active", "ready"}:
            canonical_revision_id = int(pointed_revision["id"])
        if canonical_revision_id is None:
            active_revision = next((row for row in revisions if row["status"] == "active"), None)
            if active_revision is not None:
                canonical_revision_id = int(active_revision["id"])

        latest_revision_id = int(revisions[0]["id"]) if revisions else None
        for row in revisions:
            if row["id"] == canonical_revision_id:
                bind.execute(
                    sa.text(
                        """
                        UPDATE source_revisions
                        SET status='active',
                            activated_at=COALESCE(activated_at, CURRENT_TIMESTAMP),
                            retired_at=NULL
                        WHERE id=:revision_id
                        """
                    ),
                    {"revision_id": row["id"]},
                )
            elif row["status"] in {"active", "ready", "superseded", "retiring", "retired"}:
                bind.execute(
                    sa.text(
                        """
                        UPDATE source_revisions
                        SET status='retired', retired_at=COALESCE(retired_at, CURRENT_TIMESTAMP)
                        WHERE id=:revision_id
                        """
                    ),
                    {"revision_id": row["id"]},
                )

        bind.execute(
            sa.text(
                """
                UPDATE multimodal_chunks
                SET status='retired', retired_at=COALESCE(retired_at, CURRENT_TIMESTAMP)
                WHERE source_id=:source_id
                  AND (:revision_id IS NULL OR revision_id != :revision_id)
                """
            ),
            {"source_id": source_id, "revision_id": canonical_revision_id},
        )
        if canonical_revision_id is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE multimodal_chunks
                    SET status='retired', retired_at=COALESCE(retired_at, CURRENT_TIMESTAMP)
                    WHERE revision_id=:revision_id
                      AND status IN ('superseded', 'retiring', 'retired')
                    """
                ),
                {"revision_id": canonical_revision_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE multimodal_chunks
                    SET status='active', retired_at=NULL
                    WHERE revision_id=:revision_id AND status IN ('active', 'ready')
                    """
                ),
                {"revision_id": canonical_revision_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE source_revisions
                    SET chunk_count=(
                            SELECT COUNT(*)
                            FROM multimodal_chunks
                            WHERE revision_id=:revision_id AND status='active'
                        ),
                        vector_count=(
                            SELECT COUNT(*)
                            FROM multimodal_chunks
                            WHERE revision_id=:revision_id
                              AND status='active'
                              AND qdrant_point_id IS NOT NULL
                              AND qdrant_point_id != ''
                        )
                    WHERE id=:revision_id
                    """
                ),
                {"revision_id": canonical_revision_id},
            )

        indexes = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, revision_id, status, point_count, validation_status
                    FROM index_revisions
                    WHERE source_id=:source_id
                    ORDER BY id DESC
                    """
                ),
                {"source_id": source_id},
            ).mappings()
        )
        index_by_id = {row["id"]: row for row in indexes}
        canonical_index_id: int | None = None
        pointed_index = index_by_id.get(source["active_index_revision_id"])
        if (
            pointed_index is not None
            and pointed_index["revision_id"] == canonical_revision_id
            and pointed_index["status"] == "active"
        ):
            canonical_index_id = int(pointed_index["id"])
        if canonical_index_id is None and canonical_revision_id is not None:
            active_index = next(
                (
                    row
                    for row in indexes
                    if row["revision_id"] == canonical_revision_id and row["status"] == "active"
                ),
                None,
            )
            if active_index is not None:
                canonical_index_id = int(active_index["id"])

        for row in indexes:
            if row["id"] == canonical_index_id:
                bind.execute(
                    sa.text(
                        """
                        UPDATE index_revisions
                        SET status='active',
                            activated_at=COALESCE(activated_at, CURRENT_TIMESTAMP),
                            retired_at=NULL
                        WHERE id=:index_revision_id
                        """
                    ),
                    {"index_revision_id": row["id"]},
                )
            elif row["status"] in {"active", "ready", "superseded", "retiring", "retired"}:
                bind.execute(
                    sa.text(
                        """
                        UPDATE index_revisions
                        SET status='retired', retired_at=COALESCE(retired_at, CURRENT_TIMESTAMP)
                        WHERE id=:index_revision_id
                        """
                    ),
                    {"index_revision_id": row["id"]},
                )

        bind.execute(
            sa.text(
                """
                UPDATE sources
                SET active_revision_id=:revision_id,
                    latest_revision_id=:latest_revision_id,
                    active_index_revision_id=:index_revision_id
                WHERE id=:source_id
                """
            ),
            {
                "revision_id": canonical_revision_id,
                "latest_revision_id": latest_revision_id,
                "index_revision_id": canonical_index_id,
                "source_id": source_id,
            },
        )


def _backfill_legacy_point_manifests() -> None:
    bind = op.get_bind()
    indexes = list(
        bind.execute(
            sa.text(
                """
                SELECT ir.id, ir.source_id, ir.revision_id, ir.qdrant_collection,
                       ir.status, sr.content_hash AS revision_content_hash
                FROM index_revisions AS ir
                JOIN source_revisions AS sr ON sr.id = ir.revision_id
                ORDER BY CASE WHEN ir.status='active' THEN 0 ELSE 1 END, ir.id DESC
                """
            )
        ).mappings()
    )
    for index in indexes:
        chunks = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, qdrant_point_id, content_hash, locator_json
                    FROM multimodal_chunks
                    WHERE revision_id=:revision_id
                      AND qdrant_point_id IS NOT NULL
                      AND qdrant_point_id != ''
                    ORDER BY id
                    """
                ),
                {"revision_id": index["revision_id"]},
            ).mappings()
        )
        if not chunks:
            continue
        collection_name = index["qdrant_collection"] or LEGACY_COLLECTION_UNKNOWN
        digest_source = "|".join(
            f"{chunk['id']}:{chunk['qdrant_point_id']}:{chunk['content_hash']}"
            for chunk in chunks
        )
        operation_id = f"legacy-index-{index['id']}"
        command_id = f"legacy-backfill-index-{index['id']}"
        bind.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO index_operations (
                    id, command_id, source_id, revision_id, index_revision_id,
                    operation_type, status, draft_hash, parser_name,
                    parser_version, started_at, finished_at
                ) VALUES (
                    :id, :command_id, :source_id, :revision_id, :index_revision_id,
                    'legacy_backfill', 'completed', :draft_hash, :parser_name,
                    :parser_version, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": operation_id,
                "command_id": command_id,
                "source_id": index["source_id"],
                "revision_id": index["revision_id"],
                "index_revision_id": index["id"],
                "draft_hash": _sha256(digest_source),
                "parser_name": LEGACY_DOCUMENT_PARSER,
                "parser_version": revision,
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE index_revisions
                SET validation_status=:status,
                    manifest_digest=:manifest_digest,
                    point_count=CASE
                        WHEN status='active' THEN :point_count
                        ELSE point_count
                    END
                WHERE id=:index_revision_id
                """
            ),
            {
                "status": LEGACY_PAYLOAD_STATUS,
                "manifest_digest": _sha256(digest_source),
                "point_count": len(chunks),
                "index_revision_id": index["id"],
            },
        )
        for chunk in chunks:
            payload_digest = _sha256(
                json.dumps(
                    {
                        "source_id": index["source_id"],
                        "revision_id": index["revision_id"],
                        "index_revision_id": index["id"],
                        "chunk_id": chunk["id"],
                        "content_hash": chunk["content_hash"],
                        "locator_json": chunk["locator_json"] or "{}",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            bind.execute(
                sa.text(
                    """
                    INSERT OR IGNORE INTO vector_point_manifests (
                        operation_id, source_id, revision_id, index_revision_id,
                        chunk_id, collection_name, point_id, payload_digest, status
                    ) VALUES (
                        :operation_id, :source_id, :revision_id, :index_revision_id,
                        :chunk_id, :collection_name, :point_id, :payload_digest,
                        :status
                    )
                    """
                ),
                {
                    "operation_id": operation_id,
                    "source_id": index["source_id"],
                    "revision_id": index["revision_id"],
                    "index_revision_id": index["id"],
                    "chunk_id": chunk["id"],
                    "collection_name": collection_name,
                    "point_id": chunk["qdrant_point_id"],
                    "payload_digest": payload_digest,
                    "status": LEGACY_PAYLOAD_STATUS,
                },
            )


def _create_lifecycle_constraints() -> None:
    if "uq_source_revision_number" not in _unique_constraint_names("source_revisions"):
        with op.batch_alter_table("source_revisions") as batch_op:
            batch_op.create_unique_constraint(
                "uq_source_revision_number",
                ["source_id", "revision_number"],
            )

    _create_index_if_missing(
        "uq_sources_document_id_not_null",
        "sources",
        ["document_id"],
        unique=True,
        sqlite_where=sa.text("document_id IS NOT NULL"),
    )
    _create_index_if_missing(
        "uq_source_revisions_one_active",
        "source_revisions",
        ["source_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
    )
    _create_index_if_missing(
        "uq_index_revisions_one_active",
        "index_revisions",
        ["source_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
    )


def _drop_lifecycle_constraints() -> None:
    _drop_index_if_exists("uq_index_revisions_one_active", "index_revisions")
    _drop_index_if_exists("uq_source_revisions_one_active", "source_revisions")
    _drop_index_if_exists("uq_sources_document_id_not_null", "sources")
    if "source_revisions" in _table_names() and "uq_source_revision_number" in _unique_constraint_names(
        "source_revisions"
    ):
        with op.batch_alter_table("source_revisions") as batch_op:
            batch_op.drop_constraint("uq_source_revision_number", type_="unique")


def _document_source_type(file_type: str | None) -> str:
    mapping = {"txt": "text", "md": "markdown", "pdf": "pdf"}
    return mapping.get((file_type or "").lower(), "text")


def _legacy_locator_kind(*, modality: str, source_type: str, page_number: Any) -> str:
    normalized = f"{modality} {source_type}".lower()
    if any(token in normalized for token in ("transcript", "audio", "video")):
        return "media_time"
    if any(token in normalized for token in ("image", "frame", "visual")):
        return "image_region"
    if "code" in normalized:
        return "code_range"
    if source_type.lower() in {"document", "markdown", "pdf", "text"}:
        return "document_page" if page_number is not None else "document_chunk"
    return "text"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    if table_name not in _table_names():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if table_name not in _table_names():
        return set()
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _unique_constraint_names(table_name: str) -> set[str]:
    if table_name not in _table_names():
        return set()
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _foreign_key_names(table_name: str) -> set[str]:
    if table_name not in _table_names():
        return set()
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if constraint.get("name")
    }


def _add_column_if_missing(table_name: str, column: sa.Column[Any]) -> None:
    if table_name in _table_names() and column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(
    name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
    sqlite_where: sa.ColumnElement[Any] | None = None,
) -> None:
    if table_name not in _table_names() or name in _index_names(table_name):
        return
    kwargs: dict[str, Any] = {}
    if sqlite_where is not None and op.get_bind().dialect.name == "sqlite":
        kwargs["sqlite_where"] = sqlite_where
    elif sqlite_where is not None and op.get_bind().dialect.name == "postgresql":
        kwargs["postgresql_where"] = sqlite_where
    op.create_index(name, table_name, columns, unique=unique, **kwargs)


def _drop_index_if_exists(name: str, table_name: str) -> None:
    if table_name in _table_names() and name in _index_names(table_name):
        op.drop_index(name, table_name=table_name)
