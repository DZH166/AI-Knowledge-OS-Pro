from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import create_database_engine, get_db
from app.main import app
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.services.storage_integrity import storage_integrity_service


def _seed_source(
    db_session,
    knowledge_space,
    tmp_path: Path,
    *,
    content: bytes = b"durable evidence bytes",
    declared_chunk_count: int = 1,
    create_file: bool = True,
) -> Source:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir(exist_ok=True)
    file_path = upload_root / "evidence.txt"
    if create_file:
        file_path.write_bytes(content)
    source = Source(
        space_id=knowledge_space.id,
        source_type="document",
        title="Storage fixture",
        original_filename="evidence.txt",
        mime_type="text/plain",
        file_size=len(content),
        storage_path=str(file_path),
        content_hash=sha256(content).hexdigest(),
        status="ready",
    )
    db_session.add(source)
    db_session.flush()
    revision = SourceRevision(
        source_id=source.id,
        revision_number=1,
        status="active",
        parser_name="fixture",
        parser_version="1",
        content_hash=sha256(content).hexdigest(),
        chunk_count=declared_chunk_count,
        vector_count=declared_chunk_count,
        validation_status="passed",
    )
    db_session.add(revision)
    db_session.flush()
    index_revision = IndexRevision(
        source_id=source.id,
        revision_id=revision.id,
        status="active",
        index_version="fixture-index",
        point_count=declared_chunk_count,
        validation_status="passed",
    )
    db_session.add(index_revision)
    db_session.flush()
    db_session.add(MultimodalChunk(
        source_id=source.id,
        revision_id=revision.id,
        chunk_index=0,
        modality="text",
        source_type="document",
        content_text="durable evidence bytes",
        content_hash=sha256(content).hexdigest(),
        search_text="durable evidence bytes",
        locator_json="{}",
        status="active",
    ))
    source.active_revision_id = revision.id
    source.latest_revision_id = revision.id
    source.active_index_revision_id = index_revision.id
    db_session.commit()
    db_session.refresh(source)
    return source


def test_healthy_workspace_passes_and_counts_referenced_files(db_session, knowledge_space, tmp_path: Path) -> None:
    _seed_source(db_session, knowledge_space, tmp_path)

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is True
    assert report.files["referenced"] == 1
    assert report.files["missing"] == 0
    assert report.evidence["active_sources"] == 1
    assert report.metrics["sources"] == 1
    assert [finding.code for finding in report.findings if finding.severity == "error"] == []


def test_missing_upload_is_an_error(db_session, knowledge_space, tmp_path: Path) -> None:
    _seed_source(db_session, knowledge_space, tmp_path, create_file=False)

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is False
    assert any(finding.code == "file_missing" for finding in report.findings)


def test_declared_size_mismatch_is_reported_without_blocking(db_session, knowledge_space, tmp_path: Path) -> None:
    source = _seed_source(db_session, knowledge_space, tmp_path)
    source.file_size = 1
    db_session.commit()

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is True
    assert any(finding.code == "file_size_mismatch" and finding.severity == "warning" for finding in report.findings)


def test_deep_hash_detects_changed_upload_bytes(db_session, knowledge_space, tmp_path: Path) -> None:
    source = _seed_source(db_session, knowledge_space, tmp_path)
    Path(source.storage_path).write_bytes(b"tampered")

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads", deep_hash=True)

    assert report.ok is False
    assert any(finding.code == "file_hash_mismatch" for finding in report.findings)


def test_chunk_count_drift_is_a_warning(db_session, knowledge_space, tmp_path: Path) -> None:
    _seed_source(db_session, knowledge_space, tmp_path, declared_chunk_count=3)

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is True
    assert any(finding.code == "revision_chunk_count_mismatch" for finding in report.findings)


def test_active_revision_from_another_source_is_an_error(db_session, knowledge_space, tmp_path: Path) -> None:
    first = _seed_source(db_session, knowledge_space, tmp_path)
    second = _seed_source(db_session, knowledge_space, tmp_path)
    first.active_revision_id = second.active_revision_id
    db_session.commit()

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is False
    assert any(finding.code == "active_revision_source_mismatch" for finding in report.findings)


def test_unreferenced_upload_files_are_reported(db_session, knowledge_space, tmp_path: Path) -> None:
    _seed_source(db_session, knowledge_space, tmp_path)
    (tmp_path / "uploads" / "orphan.bin").write_bytes(b"left behind")

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is True
    assert any(finding.code == "unreferenced_files" for finding in report.findings)


def test_storage_health_route_returns_read_only_report(
    db_session, knowledge_space, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_source(db_session, knowledge_space, tmp_path)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/system/storage-health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["ok"] is True
    assert payload["files"]["referenced"] == 1
    assert payload["metrics"]["sources"] == 1


def test_active_index_revision_belonging_to_another_source_is_an_error(db_session, knowledge_space, tmp_path: Path) -> None:
    first = _seed_source(db_session, knowledge_space, tmp_path)
    second = _seed_source(db_session, knowledge_space, tmp_path)
    first.active_index_revision_id = second.active_index_revision_id
    db_session.commit()

    report = storage_integrity_service.check(db_session, upload_dir=tmp_path / "uploads")

    assert report.ok is False
    assert any(finding.code == "active_index_revision_mismatch" for finding in report.findings)


def test_sqlite_engine_uses_wal_and_full_synchronous(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'durable.db').as_posix()}")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert int(connection.exec_driver_sql("PRAGMA synchronous").scalar()) == 2
    finally:
        engine.dispose()


def test_unreadable_database_is_reported_as_a_finding(tmp_path: Path) -> None:
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"this is not a sqlite database")
    engine = create_engine(f"sqlite:///{broken.as_posix()}")
    try:
        with sessionmaker(bind=engine)() as session:
            report = storage_integrity_service.check(session, upload_dir=tmp_path / "uploads", scan_orphans=False)
    finally:
        engine.dispose()

    assert report.ok is False
    assert any(finding.code == "database_unreadable" for finding in report.findings)


def test_empty_database_reports_missing_schema_instead_of_raising(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{empty.as_posix()}")
    try:
        with sessionmaker(bind=engine)() as session:
            report = storage_integrity_service.check(session, upload_dir=tmp_path / "uploads", scan_orphans=False)
    finally:
        engine.dispose()

    assert report.ok is False
    assert any(finding.code == "database_schema_incomplete" for finding in report.findings)
