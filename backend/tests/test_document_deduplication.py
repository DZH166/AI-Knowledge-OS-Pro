import pytest

from app.core.errors import DuplicateDocumentError
from app.services.ingestion_service import DocumentIngestionService


def test_document_deduplication_same_space(db_session, knowledge_space, fake_embedding, fake_vector_store, upload_factory) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    service.ingest_upload(db_session, knowledge_space.id, upload_factory("same.md", "same content"))

    with pytest.raises(DuplicateDocumentError) as exc_info:
        service.ingest_upload(db_session, knowledge_space.id, upload_factory("again.md", "same content"))

    assert exc_info.value.details["document_id"] == 1
    assert exc_info.value.details["next_action"] == "ask"
