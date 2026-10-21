from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.modules.evidence_agent.search_adapter import HybridAgentSearch
from app.modules.evidence_index import PinnedScope, SearchEvidence
from app.services.hybrid_retriever import HybridSearchResult


class RecordingEmbedding:
    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.queries: list[str] = []

    def is_configured(self) -> bool:
        return self.configured

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2]


class RecordingHybrid:
    def __init__(self, result: HybridSearchResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def search(self, _session, **kwargs):
        self.calls.append(kwargs)
        return [self.result]


def test_agent_search_uses_hybrid_retrieval_and_preserves_pinned_revision_scope() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    content_hash = "a" * 64
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="hybrid agent"))
            source = Source(id=1, space_id=1, source_type="document", title="Pinned", file_size=10, status="ready")
            session.add(source)
            revision = SourceRevision(
                id=2,
                source_id=1,
                revision_number=1,
                status="active",
                content_hash=content_hash,
                validation_status="passed",
            )
            session.add(revision)
            index = IndexRevision(
                id=3,
                source_id=1,
                revision_id=2,
                status="active",
                index_version="v5-test",
                validation_status="passed",
            )
            session.add(index)
            session.add(
                MultimodalChunk(
                    id=4,
                    source_id=1,
                    revision_id=2,
                    chunk_index=0,
                    modality="text",
                    source_type="document",
                    content_text="pinned hybrid evidence",
                    search_text="pinned hybrid evidence",
                    raw_payload_json="{}",
                    locator_json='{"kind":"document_chunk"}',
                    content_hash=content_hash,
                    status="active",
                )
            )
            source.active_revision_id = revision.id
            source.latest_revision_id = revision.id
            source.active_index_revision_id = index.id

        embedding = RecordingEmbedding()
        hybrid = RecordingHybrid(
            HybridSearchResult(
                source_id=1,
                chunk_id=4,
                modality="text",
                locator={"kind": "document_chunk"},
                dense_score=0.9,
                keyword_score=0.8,
                rerank_score=None,
                final_score=0.91,
                reason="dense_keyword_fusion; rerank_not_configured",
                citation_ready=True,
                payload={
                    "source_id": 1,
                    "revision_id": 2,
                    "index_revision_id": 3,
                    "chunk_id": 4,
                    "source_type": "document",
                    "modality": "text",
                    "content_hash": content_hash,
                    "content": "pinned hybrid evidence",
                    "locator": {"kind": "document_chunk"},
                },
            )
        )
        search = HybridAgentSearch(factory, embedding_service=embedding, hybrid_retriever=hybrid)

        result = search(
            SearchEvidence(
                text="hybrid evidence",
                scope=PinnedScope(space_id=1, revision_ids=(2,)),
                limit=5,
            )
        )

        assert embedding.queries == ["hybrid evidence"]
        assert hybrid.calls[0]["revision_ids"] == (2,)
        assert hybrid.calls[0]["source_ids"] == ()
        assert result.hits[0].score == 0.91
        assert result.hits[0].evidence.revision_id == 2
        assert result.hits[0].evidence.index_revision_id == 3
        assert result.hits[0].evidence.scope == "pinned"
        assert result.hits[0].evidence.currently_active is True
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
