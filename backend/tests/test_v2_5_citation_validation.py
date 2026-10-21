from app.models.document import Document
from app.services.rag_service import RAGService


class NoCitationLLM:
    def is_configured(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return "这是一个没有引用编号的回答。"


def test_rag_does_not_force_first_citation(db_session, knowledge_space, fake_embedding, fake_vector_store, upload_factory) -> None:
    from app.services.ingestion_service import DocumentIngestionService

    ingestion = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, _job = ingestion.ingest_upload(db_session, knowledge_space.id, upload_factory())
    assert document.status == "ready"

    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store
    service.llm_service = NoCitationLLM()

    response = service.ask_question(db_session, knowledge_space.id, "什么是 RAG？", "normal")

    assert response.citations
    assert response.used_citation_ids == []
    assert response.retrieval_status == "citation_validation_failed"
    assert "参考来源：[1]" not in response.answer
