from app.services.rag_service import RAGService
from app.core.config import settings
from app.models.document import Document


def test_rag_refuses_when_no_ready_documents(db_session, knowledge_space, fake_embedding, fake_vector_store) -> None:
    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store

    response = service.ask_question(db_session, knowledge_space.id, "什么是 RAG？", "normal")

    assert response.retrieval_status == "no_ready_documents"
    assert response.answer_confidence == "low"
    assert response.qa_log_id


def test_rag_does_not_treat_stale_ready_metadata_as_searchable_document(
    db_session, knowledge_space, fake_embedding, fake_vector_store
) -> None:
    db_session.add(
        Document(
            space_id=knowledge_space.id,
            filename="stale.md",
            original_filename="stale.md",
            file_type="md",
            content_type="text/markdown",
            file_size=10,
            storage_path="/tmp/stale.md",
            status="ready",
            parse_status="parsed",
            chunk_status="chunked",
            vector_status="indexed",
            processing_status="completed",
            processing_progress=100,
            chunk_count=3,
            embedding_fingerprint=fake_embedding.fingerprint(),
            index_version=settings.index_version,
            title="Stale metadata",
        )
    )
    db_session.commit()

    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store

    response = service.ask_question(db_session, knowledge_space.id, "What is in stale.md?", "normal")

    assert response.retrieval_status == "insufficient_context"
