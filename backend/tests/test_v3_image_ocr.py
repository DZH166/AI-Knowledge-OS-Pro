from pathlib import Path

import pytest

from app.core.errors import ConfigurationError
from app.models.source import CitationLocator, IndexRevision, MultimodalChunk
from app.services.media_service import MediaService
from app.services.ocr_service import OCRResult, UnconfiguredOCRProvider
from app.services.rag_service import RAGService
from tests.conftest import FakeEmbeddingService, FakeLLMService, FakeVectorStore
from tests.test_v3_image_upload import make_png_upload


class FakeOCRProvider:
    name = "fake_ocr"
    model = "fake-vision"

    def is_configured(self) -> bool:
        return True

    def extract_text(self, image_path: Path, mime_type: str | None = None) -> OCRResult:
        assert image_path.exists()
        return OCRResult(
            text="报错信息：ModuleNotFoundError: No module named qdrant_client\n解决方向：安装依赖并检查虚拟环境。",
            provider=self.name,
            model=self.model,
        )


def test_image_ocr_requires_real_provider(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    service = MediaService(ocr_provider=UnconfiguredOCRProvider())
    source = service.upload_image(db_session, knowledge_space.id, make_png_upload())

    with pytest.raises(ConfigurationError) as exc_info:
        service.process_image_ocr(db_session, source.id)

    assert exc_info.value.code == "OCR_NOT_CONFIGURED"


def test_image_ocr_creates_multimodal_chunk_and_rag_citation(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    fake_embedding = FakeEmbeddingService()
    fake_vector_store = FakeVectorStore()
    service = MediaService(
        ocr_provider=FakeOCRProvider(),
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )
    source = service.upload_image(db_session, knowledge_space.id, make_png_upload(name="error-screen.png"))

    source = service.process_image_ocr(db_session, source.id)

    metadata = source.metadata_data
    chunks = db_session.query(MultimodalChunk).all()
    assert metadata["ocr_status"] == "completed"
    assert metadata["ocr_provider"] == "fake_ocr"
    assert len(chunks) == 1
    assert chunks[0].modality == "image_text"
    assert "ModuleNotFoundError" in chunks[0].content_text
    assert chunks[0].qdrant_point_id
    assert db_session.query(CitationLocator).count() == 1
    assert db_session.query(IndexRevision).count() == 1

    rag = RAGService()
    rag.embedding_service = fake_embedding
    rag.vector_store = fake_vector_store
    rag.llm_service = FakeLLMService()
    response = rag.ask_question(db_session, knowledge_space.id, "截图里是什么报错？", "normal")

    assert response.retrieval_status == "success"
    assert response.citations
    assert response.citations[0].document_name == "error-screen.png"
    assert "ModuleNotFoundError" in response.related_chunks[0].content
