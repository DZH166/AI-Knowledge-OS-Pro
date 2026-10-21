from app.services.ingestion_service import DocumentIngestionService


def test_reindex_reuses_existing_chunks(db_session, knowledge_space, fake_embedding, fake_vector_store, upload_factory) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, _job = service.ingest_upload(db_session, knowledge_space.id, upload_factory())
    old_points = set(fake_vector_store.points)

    document, job = service.reindex_document(db_session, document.id)

    assert document.status == "ready"
    assert job.status == "completed"
    assert old_points.issubset(set(fake_vector_store.deleted))
    assert set(fake_vector_store.points) != old_points
