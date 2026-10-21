from pathlib import Path

from app.models.document import Document
from app.services.ingestion_service import DocumentIngestionService


def test_document_delete_removes_file_chunks_and_points(db_session, knowledge_space, fake_embedding, fake_vector_store, upload_factory) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, _job = service.ingest_upload(db_session, knowledge_space.id, upload_factory())
    storage_path = Path(document.storage_path)
    point_ids = list(fake_vector_store.points)

    service.delete_document(db_session, document.id)

    assert not storage_path.exists()
    assert fake_vector_store.deleted == point_ids
    assert db_session.get(Document, document.id) is None
