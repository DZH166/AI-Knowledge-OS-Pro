from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.session import create_database_engine
from scripts import migrate_v5_evidence_data, verify_v5_migration


ROOT = Path(__file__).resolve().parents[2]
V4_9_REVISION = "0006_v3_6_unified_media_tasks"
V5_HEAD = "0014_v5_7_workbench_backend"


def _upgrade(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision)


def _populate_v49(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _upgrade(database_url, V4_9_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            space_id = connection.execute(
                text("INSERT INTO knowledge_spaces (name, description) VALUES ('CLI fixture', 'V4.9')")
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
                        :space_id, 'fixture.md', 'fixture.md', 'md', 20,
                        'fixture.md', 'ready', 'parsed', 'chunked', 'indexed',
                        'completed', :content_hash, 1, 'fixture::8d', 'v4.9'
                    )
                    """
                ),
                {
                    "space_id": space_id,
                    "content_hash": sha256(b"fixture document").hexdigest(),
                },
            ).lastrowid
            connection.execute(
                text(
                    """
                    INSERT INTO chunks (
                        document_id, space_id, chunk_index, content, content_preview,
                        char_count, metadata_json, qdrant_point_id
                    ) VALUES (
                        :document_id, :space_id, 0, 'fixture exact evidence',
                        'fixture exact evidence', 22, '{}', 'fixture-point'
                    )
                    """
                ),
                {"document_id": document_id, "space_id": space_id},
            )
    finally:
        engine.dispose()


def test_migrate_cli_defaults_to_read_only_preflight_and_apply_is_idempotent(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v49-cli.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _populate_v49(database_url, monkeypatch)

    dry_run = migrate_v5_evidence_data.run(database_url=database_url, apply=False)
    direct_cli = subprocess.run(
        [
            sys.executable,
            "scripts/migrate_v5_evidence_data.py",
            "--database-url",
            database_url,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert dry_run["mode"] == "dry-run"
    assert dry_run["changed"] is False
    assert dry_run["before"]["current_revisions"] == [V4_9_REVISION]
    assert direct_cli.returncode == 0, direct_cli.stderr or direct_cli.stdout
    direct_report = json.loads(direct_cli.stdout)
    assert direct_report["mode"] == "dry-run"
    assert direct_report["external_access"] is False
    engine = create_database_engine(database_url)
    try:
        assert "index_operations" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    first_apply_cli = subprocess.run(
        [
            sys.executable,
            "scripts/migrate_v5_evidence_data.py",
            "--database-url",
            database_url,
            "--apply",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first_apply_cli.returncode == 0, first_apply_cli.stderr or first_apply_cli.stdout
    first_apply = json.loads(first_apply_cli.stdout)
    first_verification = verify_v5_migration.verify_database(database_url)
    second_apply_cli = subprocess.run(
        [
            sys.executable,
            "scripts/migrate_v5_evidence_data.py",
            "--database-url",
            database_url,
            "--apply",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert second_apply_cli.returncode == 0, second_apply_cli.stderr or second_apply_cli.stdout
    second_apply = json.loads(second_apply_cli.stdout)
    second_verification = verify_v5_migration.verify_database(database_url)

    assert first_apply["mode"] == "apply"
    assert first_apply["changed"] is True
    assert first_apply["after"]["current_revisions"] == [V5_HEAD]
    assert first_verification["ok"] is True
    assert first_verification["metrics"]["invalid_active_locators"] == 0
    assert second_apply["changed"] is False
    assert second_apply["after"]["current_revisions"] == [V5_HEAD]
    assert second_verification == first_verification


def test_verify_cli_runs_populated_v49_upgrade_downgrade_upgrade_matrix() -> None:
    report = verify_v5_migration.run_roundtrip()

    assert report["ok"] is True
    assert report["first_upgrade"]["ok"] is True
    assert report["first_upgrade"]["metrics"]["invalid_active_locators"] == 0
    assert report["downgrade"]["current_revisions"] == [V4_9_REVISION]
    assert report["downgrade"]["legacy_document_count"] == 1
    assert report["downgrade"]["v5_tables_absent"] is True
    assert report["downgrade"]["semantic_snapshot_matches"] is True
    assert report["downgrade"]["pre_upgrade_semantic_digest"] == (
        report["downgrade"]["post_downgrade_semantic_digest"]
    )
    assert report["first_upgrade"]["rollback_journal"]["phase"] == "finalized"
    assert report["first_upgrade"]["rollback_journal"]["restore_entry_count"] > 0
    assert report["first_upgrade"]["rollback_journal"]["migration_created_entry_count"] > 0
    assert (
        report["first_upgrade"]["rollback_journal"]["new_data_policy"]
        == report["new_data_downgrade_policy"]
    )
    assert report["new_data_downgrade_policy"]["unjournaled_post_upgrade_legacy_rows"] == (
        "preserve"
    )
    assert report["new_data_downgrade_policy"]["v5_only_rows_and_columns"] == (
        "drop_on_downgrade"
    )
    assert report["second_upgrade"]["ok"] is True
    assert report["second_upgrade"] == report["first_upgrade"]


def test_verify_cli_rejects_a_rollback_journal_with_invalid_entry_snapshots(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-invalid-rollback-entry.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _populate_v49(database_url, monkeypatch)
    _upgrade(database_url, "head", monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            raw_payload = connection.execute(
                text(
                    "SELECT payload_json FROM outbox_messages "
                    "WHERE id='v5-evidence-rollback-0007'"
                )
            ).scalar_one()
            payload = json.loads(raw_payload)
            payload["entries"][0]["after"].pop("status")
            connection.execute(
                text(
                    "UPDATE outbox_messages SET payload_json=:payload_json "
                    "WHERE id='v5-evidence-rollback-0007'"
                ),
                {
                    "payload_json": json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                },
            )
    finally:
        engine.dispose()

    report = verify_v5_migration.verify_database(database_url)

    assert report["ok"] is False
    assert report["rollback_journal"]["valid_for_downgrade"] is False
    assert any("rollback journal" in error.lower() for error in report["errors"])


def test_verify_script_is_directly_executable_from_repository_root() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_v5_migration.py", "--roundtrip"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["external_access"] is False
    assert report["downgrade"]["semantic_snapshot_matches"] is True
