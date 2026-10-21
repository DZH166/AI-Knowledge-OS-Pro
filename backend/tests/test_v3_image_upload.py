from io import BytesIO
import json

from fastapi import UploadFile
from PIL import Image
import pytest

from app.core.errors import DuplicateDocumentError
from app.models.source import MediaAsset, Source
from app.services.media_service import MediaService


def make_png_upload(name: str = "screen.png", color: str = "teal") -> UploadFile:
    buffer = BytesIO()
    image = Image.new("RGB", (12, 8), color=color)
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return UploadFile(filename=name, file=buffer, headers={"content-type": "image/png"})


def test_image_upload_creates_source_and_media_asset(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    service = MediaService()

    source = service.upload_image(db_session, knowledge_space.id, make_png_upload())

    metadata = json.loads(source.metadata_json)
    assert source.source_type == "image"
    assert source.status == "ready"
    assert source.width == 12
    assert source.height == 8
    assert source.active_revision_id == source.latest_revision_id
    assert metadata["ocr_status"] == "not_configured"
    assert metadata["vision_description_status"] == "not_configured"
    assert "不会生成伪识别结果" in metadata["capability_note"]
    assert db_session.query(Source).count() == 1
    assert db_session.query(MediaAsset).count() == 1
    assert source.media_assets[0].asset_type == "original_image"


def test_image_upload_rejects_duplicate_in_same_space(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    service = MediaService()
    service.upload_image(db_session, knowledge_space.id, make_png_upload())

    with pytest.raises(DuplicateDocumentError):
        service.upload_image(db_session, knowledge_space.id, make_png_upload())
