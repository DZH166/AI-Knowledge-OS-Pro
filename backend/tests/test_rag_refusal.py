from app.services.rag_service import RAGService


def test_rag_refuses_when_no_ready_documents(db_session, knowledge_space, fake_embedding, fake_vector_store) -> None:
    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store

    response = service.ask_question(db_session, knowledge_space.id, "什么是 RAG？", "normal")

    assert response.retrieval_status == "no_ready_documents"
    assert response.answer_confidence == "low"
    assert response.qa_log_id
