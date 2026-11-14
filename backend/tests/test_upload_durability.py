from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.config import settings
from app.models.document import Document
from app.services.ingestion_service import ingestion_service


def test_upload_is_removed_when_durable_flush_fails(
    db_session, knowledge_space, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", upload_root)
    monkeypatch.setattr("app.services.ingestion_service.os.fsync", lambda _fd: (_ for _ in ()).throw(OSError("disk")))

    upload = UploadFile(filename="evidence.txt", file=BytesIO(b"durable evidence"))
    with pytest.raises(ValueError, match="安全写入"):
        ingestion_service.ingest_upload(
            db=db_session,
            space_id=knowledge_space.id,
            upload_file=upload,
            process_immediately=False,
        )

    assert db_session.query(Document).count() == 0
    assert list(upload_root.glob("*")) == []


def test_upload_flushes_and_records_exact_written_size(
    db_session, knowledge_space, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", upload_root)
    flushed: list[int] = []
    monkeypatch.setattr("app.services.ingestion_service.os.fsync", lambda fd: flushed.append(fd))

    upload = UploadFile(filename="evidence.txt", file=BytesIO(b"durable evidence"))
    document, _job = ingestion_service.ingest_upload(
        db=db_session,
        space_id=knowledge_space.id,
        upload_file=upload,
        process_immediately=False,
    )

    assert flushed
    stored = Path(document.storage_path)
    assert stored.read_bytes() == b"durable evidence"
    assert document.file_size == stored.stat().st_size
