from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.source import Source
from app.modules.evidence_index import (
    ActiveEvidenceRef,
    ActiveScope,
    EvidenceQuery,
    EvidenceQueryResult,
    EvidenceHit,
    EvidenceSearchResult,
    PinnedEvidenceRef,
    PinnedScope,
    SearchEvidence,
    SqlEvidenceIndex,
)
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever, HybridSearchResult


SessionFactory = Callable[[], Session]


class SqlAgentEvidenceQuery:
    """Short-session adapter for immutable open/neighbor EvidenceIndex queries."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def __call__(self, query: EvidenceQuery) -> EvidenceQueryResult:
        with self._sessions() as session:
            return SqlEvidenceIndex(session).query(query)


class HybridAgentSearch:
    """Adapts production hybrid retrieval to the immutable EvidenceIndex seam.

    Embedding happens before a SQL session is opened. If embedding is not
    configured, the adapter makes the sparse-only fallback explicit by using
    the same active/pinned EvidenceIndex query rather than inventing a vector.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        embedding_service: EmbeddingService | None = None,
        hybrid_retriever: HybridRetriever | None = None,
    ) -> None:
        self._sessions = session_factory
        self._embedding = embedding_service or EmbeddingService()
        self._hybrid = hybrid_retriever or HybridRetriever()

    def __call__(self, request: SearchEvidence) -> EvidenceSearchResult:
        if not self._embedding.is_configured():
            with self._sessions() as session:
                return SqlEvidenceIndex(session).search(request)

        query_vector = self._embedding.embed_query(request.text)
        source_ids = request.scope.source_ids if isinstance(request.scope, ActiveScope) else ()
        revision_ids = request.scope.revision_ids if isinstance(request.scope, PinnedScope) else None
        with self._sessions() as session:
            raw_hits = self._hybrid.search(
                session,
                space_id=request.scope.space_id,
                query=request.text,
                query_vector=query_vector,
                source_ids=source_ids,
                revision_ids=revision_ids,
                limit=request.limit,
            )
            hits = tuple(
                hit
                for raw in raw_hits
                if (hit := self._evidence_hit(session, raw, request.scope)) is not None
            )
        return EvidenceSearchResult(hits=hits)

    @staticmethod
    def _evidence_hit(
        session: Session,
        raw: HybridSearchResult,
        scope: ActiveScope | PinnedScope,
    ) -> EvidenceHit | None:
        payload = raw.payload
        try:
            source_id = int(payload["source_id"])
            revision_id = int(payload["revision_id"])
            index_revision_id = int(payload["index_revision_id"])
            chunk_id = int(payload["chunk_id"])
        except (KeyError, TypeError, ValueError):
            return None
        content_hash = str(payload.get("content_hash") or "")
        excerpt = str(payload.get("content") or payload.get("content_preview") or "").strip()
        locator = payload.get("locator") if isinstance(payload.get("locator"), dict) else raw.locator
        if not raw.citation_ready or len(content_hash) != 64 or not excerpt or not locator.get("kind"):
            return None
        source_type = str(payload.get("source_type") or "unknown")
        modality = str(payload.get("modality") or source_type)
        common = {
            "source_id": source_id,
            "revision_id": revision_id,
            "index_revision_id": index_revision_id,
            "chunk_id": chunk_id,
            "source_type": source_type,
            "modality": modality,
            "content_hash": content_hash,
            "locator": locator,
            "excerpt": excerpt,
        }
        if isinstance(scope, PinnedScope):
            source = session.get(Source, source_id)
            evidence = PinnedEvidenceRef(
                **common,
                currently_active=bool(source and source.active_revision_id == revision_id),
            )
        else:
            evidence = ActiveEvidenceRef(**common)
        return EvidenceHit(evidence=evidence, score=float(raw.final_score))
