from app.models.document import Document
from app.services.ingestion_service import DocumentIngestionService


def test_document_upload_ingests_chunks(db_session, knowledge_space, fake_embedding, fake_vector_store, upload_factory) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, job = service.ingest_upload(db_session, knowledge_space.id, upload_factory())

    assert document.status == "ready"
    assert document.chunk_count >= 1
    assert job.status == "completed"
    assert fake_vector_store.points
    assert db_session.query(Document).count() == 1
