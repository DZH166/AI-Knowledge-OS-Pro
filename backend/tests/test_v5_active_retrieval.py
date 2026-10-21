from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.services.hybrid_retriever import HybridRetriever, HybridSearchResult
from app.services.rerank_provider import DisabledRerankProvider
from app.services.vector_store import VectorSearchResult


class OrderedVectorStore:
    def __init__(self, hits: list[VectorSearchResult]) -> None:
        self.hits = hits
        self.requested_limits: list[int | None] = []

    def search(
        self,
        space_id: int,
        query_vector: list[float],
        limit: int | None = None,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        del query_vector, score_threshold
        self.requested_limits.append(limit)
        matching = [hit for hit in self.hits if hit.payload["space_id"] == space_id]
        return matching[: limit or len(matching)]


def test_oldest_exact_keyword_hit_is_not_lost_to_created_at_preselection(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    oldest = _active_source_with_many_chunks(db_session, knowledge_space.id)

    results = _retriever(OrderedVectorStore([])).search(
        db_session,
        space_id=knowledge_space.id,
        query="oldest_exact_marker",
        query_vector=[0.0],
        limit=1,
        score_threshold=0.0,
    )

    assert [result.chunk_id for result in results] == [oldest.id]


@pytest.mark.parametrize("dense_score", [None, 0.4])
def test_keyword_only_and_hybrid_results_share_the_final_threshold(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
    dense_score: float | None,
) -> None:
    document = _legacy_document(db_session, knowledge_space.id)
    chunk = Chunk(
        document_id=document.id,
        space_id=knowledge_space.id,
        chunk_index=0,
        content="needle threshold",
        content_preview="needle threshold",
        char_count=16,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    payload = _legacy_payload(document, chunk)
    hits = [] if dense_score is None else [VectorSearchResult(score=dense_score, payload=payload)]

    results = _retriever(OrderedVectorStore(hits)).search(
        db_session,
        space_id=knowledge_space.id,
        query="needle threshold",
        query_vector=[0.0],
        limit=3,
        score_threshold=0.75,
    )

    assert results == []


def test_active_revision_filters_dense_candidates_before_top_k(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source, versions = _versioned_source(db_session, knowledge_space.id)
    hits = [
        VectorSearchResult(
            score=0.99 - position * 0.01,
            payload=_canonical_payload(source, revision, index_revision, chunk),
        )
        for position, (revision, index_revision, chunk) in enumerate(versions)
    ]
    store = OrderedVectorStore(hits)

    results = _retriever(store).search(
        db_session,
        space_id=knowledge_space.id,
        query="shared revision evidence",
        query_vector=[0.0],
        limit=1,
        score_threshold=0.0,
    )

    active_revision, active_index, active_chunk = versions[-1]
    assert all(requested is not None for requested in store.requested_limits)
    assert max(requested or 0 for requested in store.requested_limits) >= len(versions)
    assert [result.chunk_id for result in results] == [active_chunk.id]
    assert results[0].payload["revision_id"] == active_revision.id
    assert results[0].payload["index_revision_id"] == active_index.id


def test_pinned_revision_filter_is_applied_to_dense_and_keyword_candidates(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source, versions = _versioned_source(db_session, knowledge_space.id)
    hits = [
        VectorSearchResult(
            score=0.99 - position * 0.01,
            payload=_canonical_payload(source, revision, index_revision, chunk),
        )
        for position, (revision, index_revision, chunk) in enumerate(versions)
    ]
    pinned_revision, pinned_index, pinned_chunk = versions[1]

    results = _retriever(OrderedVectorStore(hits)).search(
        db_session,
        space_id=knowledge_space.id,
        query="historical version 2",
        query_vector=[0.0],
        revision_ids=(pinned_revision.id,),
        limit=1,
        score_threshold=0.0,
    )

    assert [result.chunk_id for result in results] == [pinned_chunk.id]
    assert results[0].payload["revision_id"] == pinned_revision.id
    assert results[0].payload["index_revision_id"] == pinned_index.id


def test_fusion_uses_reciprocal_ranks_instead_of_mixing_score_scales() -> None:
    retriever = _retriever(OrderedVectorStore([]))
    dense = [
        VectorSearchResult(score=0.99, payload={"source_id": 1, "chunk_id": 1, "content": "dense only"}),
        VectorSearchResult(score=0.20, payload={"source_id": 2, "chunk_id": 2, "content": "both lists"}),
    ]
    keyword = [
        HybridSearchResult(
            source_id=2,
            chunk_id=2,
            modality="text",
            locator={},
            dense_score=None,
            keyword_score=1.0,
            rerank_score=None,
            final_score=1.0,
            reason="keyword_match",
            citation_ready=True,
            payload={"source_id": 2, "chunk_id": 2, "content": "both lists"},
        )
    ]

    fused = retriever._fuse(dense, keyword)

    assert [item.chunk_id for item in fused] == [2, 1]
    assert fused[0].reason == "dense_keyword_rrf"
    assert fused[0].final_score > fused[1].final_score


def _retriever(vector_store: OrderedVectorStore) -> HybridRetriever:
    return HybridRetriever(
        vector_store=vector_store,
        rerank_provider=DisabledRerankProvider(),
    )


def _legacy_document(db: Session, space_id: int) -> Document:
    document = Document(
        space_id=space_id,
        filename="legacy.md",
        original_filename="legacy.md",
        file_type="md",
        file_size=10,
        storage_path="legacy.md",
        status="ready",
        parse_status="parsed",
        chunk_status="chunked",
        vector_status="indexed",
        processing_status="completed",
    )
    db.add(document)
    db.flush()
    return document


def _legacy_payload(document: Document, chunk: Chunk) -> dict:
    return {
        "space_id": document.space_id,
        "document_id": document.id,
        "document_name": document.original_filename,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_preview": chunk.content_preview,
        "source_type": "document",
        "modality": "text",
    }


def _versioned_source(
    db: Session,
    space_id: int,
) -> tuple[Source, list[tuple[SourceRevision, IndexRevision, MultimodalChunk]]]:
    source = Source(
        space_id=space_id,
        source_type="document",
        title="Versioned source",
        file_size=100,
        status="ready",
    )
    db.add(source)
    db.flush()

    versions: list[tuple[SourceRevision, IndexRevision, MultimodalChunk]] = []
    for number in range(1, 5):
        active = number == 4
        content = (
            "shared revision evidence active version 4"
            if active
            else f"shared revision evidence historical version {number}"
        )
        revision = SourceRevision(
            source_id=source.id,
            revision_number=number,
            status="active" if active else "retired",
            content_hash=sha256(f"revision:{number}".encode()).hexdigest(),
            chunk_count=1,
            vector_count=1,
            validation_status="passed",
        )
        db.add(revision)
        db.flush()
        chunk = MultimodalChunk(
            source_id=source.id,
            revision_id=revision.id,
            chunk_index=0,
            modality="text",
            source_type="document",
            content_text=content,
            content_hash=sha256(content.encode()).hexdigest(),
            search_text=content,
            raw_payload_json="{}",
            locator_json=json.dumps({"kind": "pdf_page", "page": number}),
            status="active" if active else "retired",
            qdrant_point_id=f"point-{number}",
        )
        index_revision = IndexRevision(
            source_id=source.id,
            revision_id=revision.id,
            status="active" if active else "retired",
            index_version="v5-test",
            point_count=1,
            validation_status="passed",
        )
        db.add_all((chunk, index_revision))
        db.flush()
        versions.append((revision, index_revision, chunk))

    source.active_revision_id = versions[-1][0].id
    source.latest_revision_id = versions[-1][0].id
    source.active_index_revision_id = versions[-1][1].id
    db.commit()
    for revision, index_revision, chunk in versions:
        db.refresh(revision)
        db.refresh(index_revision)
        db.refresh(chunk)
    db.refresh(source)
    return source, versions


def _active_source_with_many_chunks(db: Session, space_id: int) -> MultimodalChunk:
    source = Source(
        space_id=space_id,
        source_type="document",
        title="Many active chunks",
        file_size=100,
        status="ready",
    )
    db.add(source)
    db.flush()
    revision = SourceRevision(
        source_id=source.id,
        revision_number=1,
        status="active",
        content_hash=sha256(b"many-active-chunks").hexdigest(),
        chunk_count=35,
        vector_count=35,
        validation_status="passed",
    )
    db.add(revision)
    db.flush()
    index_revision = IndexRevision(
        source_id=source.id,
        revision_id=revision.id,
        status="active",
        index_version="v5-test",
        point_count=35,
        validation_status="passed",
    )
    db.add(index_revision)
    db.flush()
    source.active_revision_id = revision.id
    source.latest_revision_id = revision.id
    source.active_index_revision_id = index_revision.id

    now = datetime.now(timezone.utc)
    oldest: MultimodalChunk | None = None
    for index in range(35):
        content = (
            "oldest_exact_marker belongs in the sparse candidate set"
            if index == 0
            else f"recent unrelated material {index}"
        )
        chunk = MultimodalChunk(
            source_id=source.id,
            revision_id=revision.id,
            chunk_index=index,
            modality="text",
            source_type="document",
            content_text=content,
            content_hash=sha256(content.encode()).hexdigest(),
            search_text=content,
            raw_payload_json="{}",
            locator_json=json.dumps({"kind": "pdf_page", "page": index + 1}),
            status="active",
            qdrant_point_id=f"many-point-{index}",
            created_at=(
                now - timedelta(days=60)
                if index == 0
                else now - timedelta(minutes=index)
            ),
        )
        db.add(chunk)
        if index == 0:
            oldest = chunk
    db.commit()
    assert oldest is not None
    db.refresh(oldest)
    return oldest


def _canonical_payload(
    source: Source,
    revision: SourceRevision,
    index_revision: IndexRevision,
    chunk: MultimodalChunk,
) -> dict:
    return {
        "space_id": source.space_id,
        "source_id": source.id,
        "source_type": source.source_type,
        "document_name": source.title,
        "revision_id": revision.id,
        "index_revision_id": index_revision.id,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content_text,
        "content_preview": chunk.content_text,
        "modality": chunk.modality,
        "locator": json.loads(chunk.locator_json),
    }
