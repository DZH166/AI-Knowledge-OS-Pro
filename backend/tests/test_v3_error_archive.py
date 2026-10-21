from app.services.error_archive_service import ErrorArchiveService
from app.services.media_service import MediaService
from tests.conftest import FakeEmbeddingService, FakeVectorStore
from tests.test_v3_image_ocr import FakeOCRProvider
from tests.test_v3_image_upload import make_png_upload


def test_error_archive_extracts_from_ocr_and_deduplicates(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    media_service = MediaService(
        ocr_provider=FakeOCRProvider(),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(),
    )
    source = media_service.upload_image(
        db_session,
        knowledge_space.id,
        make_png_upload(name="module-error.png"),
    )
    media_service.process_image_ocr(db_session, source.id)

    service = ErrorArchiveService()
    archive, created = service.extract_from_source(db_session, source.id)
    duplicate, duplicate_created = service.extract_from_source(db_session, source.id)

    assert created is True
    assert duplicate_created is False
    assert duplicate.id == archive.id
    assert archive.error_type == "ModuleNotFoundError"
    assert "qdrant_client" in archive.error_message
    assert archive.status == "open"
    assert archive.confidence == 95
    assert "确认当前 Python 虚拟环境" in archive.suggested_actions
    assert archive.source_id == source.id

    resolved = service.update_archive(
        db_session,
        archive.id,
        status="resolved",
        resolution_notes="已安装缺失依赖并完成回归测试。",
        tags=["依赖问题", "已复盘"],
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None
    assert resolved.tags == ["依赖问题", "已复盘"]


def test_error_archive_refuses_when_source_has_no_ocr_text(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    source = MediaService().upload_image(
        db_session,
        knowledge_space.id,
        make_png_upload(name="plain.png"),
    )

    service = ErrorArchiveService()
    try:
        service.extract_from_source(db_session, source.id)
    except ValueError as exc:
        assert "先执行真实 OCR" in str(exc)
    else:
        raise AssertionError("没有 OCR 文本时不应创建报错档案")
