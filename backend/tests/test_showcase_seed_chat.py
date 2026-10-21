from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import DependencyUnavailableError
from app.services.rag_service import RAGService
from app.services.rerank_provider import DisabledRerankProvider
from scripts import seed_showcase


class _ShowcaseEmbedding:
    def fingerprint(self) -> str:
        return seed_showcase.DEMO_EMBEDDING_FINGERPRINT

    def embed_query(self, _text: str) -> list[float]:
        return [0.0] * seed_showcase.DEMO_EMBEDDING_DIMENSIONS


class _UnavailableVectorStore:
    def search(self, **_kwargs):
        raise DependencyUnavailableError("Qdrant is intentionally unavailable in this test.")


class _CitationLLM:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        del system_prompt, user_prompt
        return "Persisted source locators keep the answer traceable [1]."


def test_showcase_chat_keeps_citations_when_qdrant_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "chat-showcase.db"
    monkeypatch.setattr(seed_showcase, "make_video", lambda _path, _cover: None)
    monkeypatch.setattr(settings, "demo_mode", True)
    seed_showcase.seed(database_path, reset=True)

    service = RAGService()
    service.embedding_service = _ShowcaseEmbedding()
    service.vector_store = _UnavailableVectorStore()
    service.llm_service = _CitationLLM()
    service.rerank_provider = DisabledRerankProvider()

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    with Session(engine) as session:
        response = service.ask_question(
            session,
            space_id=1,
            question="How does the system keep multimodal RAG answers traceable?",
            answer_mode="normal",
        )

    assert response.retrieval_status == "success"
    assert response.citations
    assert response.citations[0].source_id is not None
    assert response.citations[0].retrieval_reason
    assert "keyword_only_fallback" in response.citations[0].retrieval_reason
