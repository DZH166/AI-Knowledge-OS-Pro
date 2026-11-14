from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from hashlib import sha256

from app.services.storage_backup import (
    StorageBackupError,
    create_backup,
    restore_backup,
    verify_backup,
)


def _seed_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("create table evidence (id integer primary key, title text not null)")
        connection.execute("insert into evidence (title) values ('durable claim')")
        connection.commit()
    finally:
        connection.close()


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _prepare(tmp_path: Path) -> tuple[Path, Path, Path]:
    database = tmp_path / "workspace.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _seed_database(database)
    (uploads / "note.txt").write_text("evidence bytes", encoding="utf-8")
    (uploads / "nested").mkdir()
    (uploads / "nested" / "frame.bin").write_bytes(b"\x00\x01\x02")
    return database, uploads, tmp_path / "backups" / "workspace.zip"


def test_backup_creates_verified_manifest_and_restores(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)

    summary = create_backup(
        database_url=_database_url(database),
        upload_dir=uploads,
        output=archive,
        label="unit",
    )
    result = verify_backup(archive)

    assert summary.upload_files == 2
    assert summary.upload_bytes == len(b"evidence bytes") + 3
    assert result.ok is True
    with zipfile.ZipFile(archive) as handle:
        manifest = json.loads(handle.read("manifest.json"))
    assert manifest["format"] == "evidence-os-storage-backup"
    assert manifest["totals"]["upload_files"] == 2
    assert all(entry["path"].startswith("uploads/") for entry in manifest["uploads"])

    (uploads / "note.txt").write_text("changed after backup", encoding="utf-8")
    connection = sqlite3.connect(database)
    connection.execute("delete from evidence")
    connection.commit()
    connection.close()

    restored = restore_backup(
        archive_path=archive,
        database_url=_database_url(database),
        upload_dir=uploads,
        force=True,
    )

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute("select title from evidence").fetchall()
    finally:
        connection.close()
    assert rows == [("durable claim",)]
    assert (uploads / "note.txt").read_text(encoding="utf-8") == "evidence bytes"
    assert Path(restored["previous_database"]).exists()
    assert Path(restored["previous_uploads"]).exists()


def test_backup_refuses_existing_archive(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"occupied")

    with pytest.raises(StorageBackupError, match="拒绝覆盖"):
        create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)


def test_verification_rejects_tampered_payload(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "uploads/note.txt":
                payload = b"tampered evidence"
            target.writestr(info, payload)

    with pytest.raises(StorageBackupError, match="大小或指纹|大小与 manifest|指纹与 manifest"):
        verify_backup(tampered)


def test_verification_rejects_path_traversal_entries(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)

    malicious = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(malicious, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr("../escaped.txt", b"must never be written")

    with pytest.raises(StorageBackupError, match="不安全路径"):
        verify_backup(malicious)


def test_restore_refuses_non_empty_target_without_force(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)

    with pytest.raises(StorageBackupError, match="非空"):
        restore_backup(archive_path=archive, database_url=_database_url(database), upload_dir=uploads)


def _add_source_reference(database: Path, storage_path: Path, content_hash: str) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("create table sources (id integer primary key, storage_path text, content_hash text)")
        connection.execute(
            "insert into sources (storage_path, content_hash) values (?, ?)",
            (str(storage_path), content_hash),
        )
        connection.commit()
    finally:
        connection.close()


def test_backup_rejects_database_file_hash_mismatch(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    _add_source_reference(database, uploads / "note.txt", sha256(b"a different payload").hexdigest())

    with pytest.raises(StorageBackupError, match="指纹不一致"):
        create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)
    assert not archive.exists()


def test_backup_rejects_missing_database_reference(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    _add_source_reference(database, uploads / "missing.txt", sha256(b"missing").hexdigest())

    with pytest.raises(StorageBackupError, match="缺失"):
        create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)
    assert not archive.exists()


def test_backup_accepts_matching_database_reference(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    _add_source_reference(database, uploads / "note.txt", sha256(b"evidence bytes").hexdigest())

    summary = create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)

    assert summary.upload_files == 2
    assert verify_backup(archive).ok is True


def test_restore_to_a_new_upload_root_rewrites_database_paths(tmp_path: Path) -> None:
    database, uploads, archive = _prepare(tmp_path)
    _add_source_reference(database, uploads / "note.txt", sha256(b"evidence bytes").hexdigest())
    create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)

    target_root = tmp_path / "moved"
    target_database = target_root / "workspace.db"
    target_uploads = target_root / "uploads"
    result = restore_backup(
        archive_path=archive,
        database_url=_database_url(target_database),
        upload_dir=target_uploads,
        force=True,
    )

    assert result["rewritten_storage_paths"] == "1"
    connection = sqlite3.connect(target_database)
    try:
        stored = connection.execute("select storage_path from sources").fetchone()[0]
    finally:
        connection.close()
    assert Path(stored).is_relative_to(target_uploads.resolve())
    assert Path(stored).read_bytes() == b"evidence bytes"


def test_failed_post_write_verification_removes_the_partial_archive(tmp_path: Path, monkeypatch) -> None:
    database, uploads, archive = _prepare(tmp_path)

    def reject(_archive):
        raise StorageBackupError("verification failed")

    monkeypatch.setattr("app.services.storage_backup.verify_backup", reject)

    with pytest.raises(StorageBackupError, match="verification failed"):
        create_backup(database_url=_database_url(database), upload_dir=uploads, output=archive)
    assert not archive.exists()
