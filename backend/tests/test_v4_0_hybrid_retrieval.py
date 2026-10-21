from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.hybrid_retriever import HybridRetriever
from app.services.rag_service import RAGService


def test_hybrid_retriever_uses_keyword_fallback_when_dense_misses(
    db_session,
    knowledge_space,
    fake_vector_store,
    fake_embedding,
) -> None:
    document, chunk = _seed_indexed_document(db_session, knowledge_space.id, fake_embedding.fingerprint())

    retriever = HybridRetriever(vector_store=fake_vector_store)
    results = retriever.search(
        db_session,
        space_id=knowledge_space.id,
        query="SQLite FTS5 混合检索",
        query_vector=fake_embedding.embed_query("SQLite FTS5 混合检索"),
        limit=3,
    )

    assert results
    top = results[0]
    assert top.chunk_id == chunk.id
    assert top.payload["document_id"] == document.id
    assert top.dense_score is None
    assert top.keyword_score and top.keyword_score > 0
    assert top.rerank_score is None
    assert top.final_score > 0
    assert "keyword_only_fallback" in top.reason
    assert "rerank_not_configured" in top.reason
    assert top.citation_ready is True


def test_rag_response_exposes_hybrid_trace_without_fake_rerank(
    db_session,
    knowledge_space,
    fake_vector_store,
    fake_embedding,
) -> None:
    _seed_indexed_document(db_session, knowledge_space.id, fake_embedding.fingerprint())
    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store
    service.llm_service.provider = type("Provider", (), {"is_configured": lambda self: True})()
    service.llm_service.complete = lambda system_prompt, user_prompt: "混合检索可以补齐关键词漏召回 [1]"

    response = service.ask_question(db_session, knowledge_space.id, "SQLite FTS5 混合检索是什么？", "normal")

    assert response.retrieval_status == "success"
    assert response.used_citation_ids == ["[1]"]
    assert response.citations[0].keyword_score is not None
    assert response.citations[0].dense_score is None
    assert response.citations[0].rerank_score is None
    assert response.citations[0].final_score == response.retrieval_score
    assert response.citations[0].retrieval_reason
    assert "rerank_not_configured" in response.citations[0].retrieval_reason
    assert response.related_chunks[0].citation_ready is True


def _seed_indexed_document(db_session, space_id: int, fingerprint: str) -> tuple[Document, Chunk]:
    document = Document(
        space_id=space_id,
        filename="hybrid.md",
        original_filename="hybrid.md",
        file_type="md",
        content_type="text/markdown",
        file_size=512,
        storage_path="/tmp/hybrid.md",
        status="ready",
        parse_status="parsed",
        chunk_status="chunked",
        vector_status="indexed",
        processing_status="completed",
        embedding_fingerprint=fingerprint,
        index_version=settings.index_version,
    )
    db_session.add(document)
    db_session.flush()
    chunk = Chunk(
        document_id=document.id,
        space_id=space_id,
        chunk_index=0,
        content="SQLite FTS5 可以作为关键词召回层，与 dense vector retrieval 融合，减少术语漏召回。",
        content_preview="SQLite FTS5 可以作为关键词召回层",
        char_count=48,
        section_title="Hybrid Retrieval",
        heading_path="V4.0 / Hybrid Retrieval",
        qdrant_point_id="fake-point",
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(document)
    db_session.refresh(chunk)
    return document, chunk
