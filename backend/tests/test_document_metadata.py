from app.services.ingestion_service import DocumentIngestionService


def test_markdown_heading_path_is_saved(db_session, knowledge_space, fake_embedding, fake_vector_store, upload_factory) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, _job = service.ingest_upload(
        db_session,
        knowledge_space.id,
        upload_factory(name="guide.md", content="# RAG\n## 检索\nRAG 会先检索资料。"),
    )
    chunk = document.chunks[0]

    assert document.status == "ready"
    assert chunk.heading_path in {"RAG", "RAG / 检索"}
