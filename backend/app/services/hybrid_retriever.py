from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import DependencyUnavailableError
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.modules.evidence_index import (
    ActiveScope,
    PinnedScope,
    SearchEvidence,
    SqlEvidenceIndex,
)
from app.services.rerank_provider import RerankInput, RerankProvider, get_rerank_provider
from app.services.lexical_retrieval import LexicalQuery
from app.services.vector_store import VectorSearchResult, VectorStore


@dataclass
class HybridSearchResult:
    source_id: int | None
    chunk_id: int
    modality: str | None
    locator: dict[str, Any]
    dense_score: float | None
    keyword_score: float | None
    rerank_score: float | None
    final_score: float
    reason: str
    citation_ready: bool
    payload: dict[str, Any]

    @property
    def score(self) -> float:
        return self.final_score


@dataclass(frozen=True, slots=True)
class _CanonicalDenseCandidate:
    chunk: MultimodalChunk
    source: Source
    index_revision: IndexRevision


class HybridRetriever:
    def __init__(
        self,
        *,
        vector_store: VectorStore | None = None,
        rerank_provider: RerankProvider | None = None,
    ) -> None:
        self.vector_store = vector_store or VectorStore()
        self.rerank_provider = rerank_provider or get_rerank_provider()

    def search(
        self,
        db: Session,
        *,
        space_id: int,
        query: str,
        query_vector: list[float],
        source_ids: tuple[int, ...] = (),
        revision_ids: tuple[int, ...] | None = None,
        limit: int | None = None,
        score_threshold: float | None = None,
        dense_score_threshold: float | None = None,
    ) -> list[HybridSearchResult]:
        top_k = limit or settings.retrieval_top_k
        effective_threshold = (
            score_threshold
            if score_threshold is not None
            else settings.retrieval_score_threshold
        )
        effective_dense_threshold = (
            dense_score_threshold
            if dense_score_threshold is not None
            else score_threshold
            if score_threshold is not None
            else settings.retrieval_dense_score_threshold
        )
        dense_ceiling = self._dense_candidate_ceiling(
            db,
            space_id=space_id,
            source_ids=source_ids,
            revision_ids=revision_ids,
            top_k=top_k,
        )
        try:
            dense_hits = self._search_dense_candidates(
                db,
                space_id=space_id,
                query_vector=query_vector,
                source_ids=source_ids,
                revision_ids=revision_ids,
                top_k=top_k,
                candidate_ceiling=dense_ceiling,
                score_threshold=effective_dense_threshold,
            )
        except DependencyUnavailableError:
            if not settings.demo_mode:
                raise
            dense_hits = []
        keyword_hits = self._keyword_search(
            db,
            space_id=space_id,
            query=query,
            source_ids=source_ids,
            revision_ids=revision_ids,
            limit=max(top_k * 4, top_k),
        )
        fused = self._fuse(dense_hits, keyword_hits)
        reranked = self._maybe_rerank(query, fused)
        return [item for item in reranked if item.final_score >= effective_threshold][
            :top_k
        ]

    def _dense_candidate_ceiling(
        self,
        db: Session,
        *,
        space_id: int,
        source_ids: tuple[int, ...],
        revision_ids: tuple[int, ...] | None,
        top_k: int,
    ) -> int:
        # The legacy VectorStore adapter can only filter by space. This ceiling
        # lets the progressive search below expand through every SQL-tracked
        # point when stale revisions consume the first candidate window.
        del source_ids, revision_ids
        canonical_count = int(
            db.scalar(
                select(func.count(MultimodalChunk.id))
                .join(Source, Source.id == MultimodalChunk.source_id)
                .where(Source.space_id == space_id)
            )
            or 0
        )
        legacy_count = int(
            db.scalar(
                select(func.count(Chunk.id)).where(Chunk.space_id == space_id)
            )
            or 0
        )
        return max(top_k, top_k * 2, canonical_count + legacy_count)

    def _search_dense_candidates(
        self,
        db: Session,
        *,
        space_id: int,
        query_vector: list[float],
        source_ids: tuple[int, ...],
        revision_ids: tuple[int, ...] | None,
        top_k: int,
        candidate_ceiling: int,
        score_threshold: float,
    ) -> list[VectorSearchResult]:
        target_count = max(top_k, top_k * 2)
        request_limit = min(candidate_ceiling, target_count)
        while True:
            raw_hits = self.vector_store.search(
                space_id=space_id,
                query_vector=query_vector,
                limit=request_limit,
                score_threshold=score_threshold,
            )
            # Treat the adapter-side threshold as an optimization, not a trust
            # boundary. Custom/legacy stores may return lower-scored rows.
            raw_hits = [hit for hit in raw_hits if hit.score >= score_threshold]
            filtered = self._filter_dense_candidates(
                db,
                raw_hits,
                space_id=space_id,
                source_ids=source_ids,
                revision_ids=revision_ids,
            )
            if (
                len(filtered) >= target_count
                or len(raw_hits) < request_limit
                or request_limit >= candidate_ceiling
            ):
                return filtered
            request_limit = min(candidate_ceiling, request_limit * 2)

    def _filter_dense_candidates(
        self,
        db: Session,
        dense_hits: list[VectorSearchResult],
        *,
        space_id: int,
        source_ids: tuple[int, ...],
        revision_ids: tuple[int, ...] | None,
    ) -> list[VectorSearchResult]:
        if not dense_hits:
            return []

        candidates = self._canonical_dense_candidates(
            db,
            space_id=space_id,
            source_ids=source_ids,
            revision_ids=revision_ids,
        )
        by_source_chunk: dict[tuple[int, int], list[_CanonicalDenseCandidate]] = {}
        by_document_chunk: dict[tuple[int, int], list[_CanonicalDenseCandidate]] = {}
        for candidate in candidates:
            by_source_chunk.setdefault(
                (candidate.source.id, candidate.chunk.id), []
            ).append(candidate)
            if (
                candidate.source.document_id is not None
                and candidate.chunk.legacy_chunk_id is not None
            ):
                by_document_chunk.setdefault(
                    (
                        candidate.source.document_id,
                        candidate.chunk.legacy_chunk_id,
                    ),
                    [],
                ).append(candidate)

        legacy_keys = self._legacy_dense_keys(
            db,
            space_id=space_id,
            source_ids=source_ids,
            revision_ids=revision_ids,
        )
        filtered: list[VectorSearchResult] = []
        for hit in dense_hits:
            payload = dict(hit.payload)
            payload_space_id = self._optional_int(payload.get("space_id"))
            if payload_space_id is not None and payload_space_id != space_id:
                continue
            chunk_id = self._optional_int(payload.get("chunk_id"))
            if chunk_id is None:
                continue

            source_id = self._optional_int(payload.get("source_id"))
            document_id = self._optional_int(payload.get("document_id"))
            choices: list[_CanonicalDenseCandidate] = []
            if source_id is not None:
                choices = by_source_chunk.get((source_id, chunk_id), [])
            if not choices and document_id is not None:
                choices = by_document_chunk.get((document_id, chunk_id), [])
            candidate = self._pick_canonical_candidate(payload, choices)
            if candidate is not None:
                filtered.append(
                    VectorSearchResult(
                        score=hit.score,
                        payload=self._canonical_payload(payload, candidate),
                    )
                )
                continue

            if document_id is not None and (document_id, chunk_id) in legacy_keys:
                filtered.append(VectorSearchResult(score=hit.score, payload=payload))
        return filtered

    def _canonical_dense_candidates(
        self,
        db: Session,
        *,
        space_id: int,
        source_ids: tuple[int, ...],
        revision_ids: tuple[int, ...] | None,
    ) -> list[_CanonicalDenseCandidate]:
        statement = (
            select(MultimodalChunk, Source, IndexRevision)
            .join(Source, Source.id == MultimodalChunk.source_id)
            .join(
                SourceRevision,
                and_(
                    SourceRevision.id == MultimodalChunk.revision_id,
                    SourceRevision.source_id == Source.id,
                ),
            )
            .join(
                IndexRevision,
                and_(
                    IndexRevision.revision_id == MultimodalChunk.revision_id,
                    IndexRevision.source_id == Source.id,
                ),
            )
            .where(Source.space_id == space_id)
        )
        if source_ids:
            statement = statement.where(Source.id.in_(source_ids))
        if revision_ids is None:
            statement = statement.where(
                Source.active_revision_id == MultimodalChunk.revision_id,
                or_(
                    Source.active_index_revision_id == IndexRevision.id,
                    and_(
                        Source.active_index_revision_id.is_(None),
                        IndexRevision.status == "active",
                        IndexRevision.validation_status == "passed",
                    ),
                ),
                Source.retired_at.is_(None),
                SourceRevision.status == "active",
                IndexRevision.status == "active",
                MultimodalChunk.status == "active",
            )
        else:
            statement = statement.where(
                MultimodalChunk.revision_id.in_(revision_ids),
                SourceRevision.status.in_(("active", "retired")),
                SourceRevision.validation_status == "passed",
                IndexRevision.status.in_(("active", "retired")),
                IndexRevision.validation_status == "passed",
                MultimodalChunk.status.in_(("active", "retired")),
            )
        return [
            _CanonicalDenseCandidate(
                chunk=chunk,
                source=source,
                index_revision=index_revision,
            )
            for chunk, source, index_revision in db.execute(statement)
        ]

    def _legacy_dense_keys(
        self,
        db: Session,
        *,
        space_id: int,
        source_ids: tuple[int, ...],
        revision_ids: tuple[int, ...] | None,
    ) -> set[tuple[int, int]]:
        if revision_ids is not None or source_ids:
            return set()
        return {
            (document_id, chunk_id)
            for document_id, chunk_id in db.execute(
                select(Document.id, Chunk.id)
                .join(Chunk, Chunk.document_id == Document.id)
                .outerjoin(Source, Source.document_id == Document.id)
                .where(
                    Document.space_id == space_id,
                    Document.status == "ready",
                    Document.vector_status == "indexed",
                    Document.retired_at.is_(None),
                    Source.id.is_(None),
                )
            )
        }

    def _pick_canonical_candidate(
        self,
        payload: dict[str, Any],
        candidates: list[_CanonicalDenseCandidate],
    ) -> _CanonicalDenseCandidate | None:
        revision_id = self._optional_int(payload.get("revision_id"))
        index_revision_id = self._optional_int(payload.get("index_revision_id"))
        for candidate in candidates:
            if revision_id is not None and revision_id != candidate.chunk.revision_id:
                continue
            if (
                index_revision_id is not None
                and index_revision_id != candidate.index_revision.id
            ):
                continue
            return candidate
        return None

    def _canonical_payload(
        self,
        payload: dict[str, Any],
        candidate: _CanonicalDenseCandidate,
    ) -> dict[str, Any]:
        chunk = candidate.chunk
        source = candidate.source
        locator = self._json_dict(chunk.locator_json)
        canonical = dict(payload)
        if source.document_id is not None and chunk.legacy_chunk_id is not None:
            canonical["legacy_chunk_id"] = chunk.legacy_chunk_id
        canonical.update(
            {
                "space_id": source.space_id,
                "source_id": source.id,
                "document_id": source.document_id,
                "document_name": canonical.get("document_name")
                or source.original_filename
                or source.title
                or f"Source #{source.id}",
                "revision_id": chunk.revision_id,
                "index_revision_id": candidate.index_revision.id,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content_hash": chunk.content_hash,
                "content": chunk.content_text,
                "content_preview": chunk.content_text[:220],
                "source_type": chunk.source_type,
                "modality": chunk.modality,
                "page_number": chunk.page_number
                or locator.get("page_number")
                or locator.get("page"),
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "locator": locator,
            }
        )
        return canonical

    def _keyword_search(
        self,
        db: Session,
        *,
        space_id: int,
        query: str,
        source_ids: tuple[int, ...],
        revision_ids: tuple[int, ...] | None,
        limit: int,
    ) -> list[HybridSearchResult]:
        if not query.strip():
            return []
        lexical = LexicalQuery(query)

        results: list[HybridSearchResult] = []
        if revision_ids is not None and source_ids:
            # PinnedScope intentionally exposes revision IDs only. Intersect
            # this adapter's additional source restriction before the public
            # seam ranks/caps candidates, rather than dropping valid hits late.
            revision_ids = tuple(db.scalars(
                select(SourceRevision.id)
                .join(Source, Source.id == SourceRevision.source_id)
                .where(Source.space_id == space_id, Source.id.in_(source_ids),
                       SourceRevision.id.in_(revision_ids))
            ))
        scope = (
            PinnedScope(space_id=space_id, revision_ids=revision_ids)
            if revision_ids is not None
            else ActiveScope(space_id=space_id, source_ids=source_ids)
        )
        canonical = SqlEvidenceIndex(db).search(
            SearchEvidence(
                text=query,
                scope=scope,
                # The seam scores the full eligible SQL scope before applying
                # this cap, so creation time can never preselect candidates.
                limit=100,
            )
        )
        sources: dict[int, Source] = {}
        canonical_chunk_ids: set[int] = set()
        for hit in canonical.hits:
            evidence = hit.evidence
            if source_ids and evidence.source_id not in source_ids:
                continue
            canonical_chunk_ids.add(evidence.chunk_id)
            source = sources.get(evidence.source_id)
            if source is None:
                source = db.get(Source, evidence.source_id)
                if source is None:
                    continue
                sources[source.id] = source
            score = hit.score
            if score <= 0:
                continue
            locator = dict(evidence.locator)
            payload = {
                "space_id": space_id,
                "source_id": source.id,
                "document_id": source.document_id,
                "document_name": source.original_filename
                or source.title
                or f"Source #{source.id}",
                "revision_id": evidence.revision_id,
                "index_revision_id": evidence.index_revision_id,
                "chunk_id": evidence.chunk_id,
                "content_hash": evidence.content_hash,
                "content": evidence.excerpt,
                "content_preview": evidence.excerpt[:220],
                "source_type": evidence.source_type,
                "modality": evidence.modality,
                "page_number": locator.get("page_number") or locator.get("page"),
                "start_ms": locator.get("start_ms"),
                "end_ms": locator.get("end_ms"),
                "file_path": locator.get("file_path"),
                "line_start": locator.get("line_start"),
                "line_end": locator.get("line_end"),
                "symbol_name": locator.get("symbol_name"),
                "locator": locator,
            }
            results.append(
                HybridSearchResult(
                    source_id=source.id,
                    chunk_id=evidence.chunk_id,
                    modality=evidence.modality,
                    locator=locator,
                    dense_score=None,
                    keyword_score=score,
                    rerank_score=None,
                    final_score=score,
                    reason="keyword_match",
                    citation_ready=True,
                    payload=payload,
                )
            )

        # V4 media/code writers created a unique active IndexRevision before
        # Source.active_index_revision_id existed. Keep those rows readable
        # without weakening revision safety: every chunk must still belong to
        # Source.active_revision_id and the derived index is active/passed.
        if revision_ids is None:
            for candidate in self._canonical_dense_candidates(
                db,
                space_id=space_id,
                source_ids=source_ids,
                revision_ids=None,
            ):
                chunk = candidate.chunk
                if chunk.id in canonical_chunk_ids:
                    continue
                score = lexical.score(chunk.search_text or chunk.content_text)
                if score <= 0:
                    continue
                payload = self._canonical_payload({}, candidate)
                locator = self._locator_from_payload(payload)
                results.append(
                    HybridSearchResult(
                        source_id=candidate.source.id,
                        chunk_id=chunk.id,
                        modality=chunk.modality,
                        locator=locator,
                        dense_score=None,
                        keyword_score=score,
                        rerank_score=None,
                        final_score=score,
                        reason="keyword_match",
                        citation_ready=True,
                        payload=payload,
                    )
                )

        # A V4 database can still contain ready Document/Chunk rows before the
        # canonical Source backfill has run.  Keep that compatibility path, but
        # only for documents with no canonical source and scan the full set.
        if revision_ids is None and not source_ids:
            document_chunks = db.execute(
                select(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .outerjoin(Source, Source.document_id == Document.id)
                .where(
                    Chunk.space_id == space_id,
                    Document.status == "ready",
                    Document.vector_status == "indexed",
                    Document.retired_at.is_(None),
                    Source.id.is_(None),
                )
            ).all()
            for chunk, document in document_chunks:
                score = lexical.score(chunk.content)
                if score <= 0:
                    continue
                payload = {
                    "space_id": space_id,
                    "document_id": document.id,
                    "document_name": document.original_filename,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "content_preview": chunk.content_preview,
                    "page_number": chunk.page_number,
                    "heading_path": chunk.heading_path,
                    "section_title": chunk.section_title,
                    "source_type": "document",
                    "modality": "text",
                }
                results.append(
                    HybridSearchResult(
                        source_id=None,
                        chunk_id=chunk.id,
                        modality="text",
                        locator=self._locator_from_payload(payload),
                        dense_score=None,
                        keyword_score=score,
                        rerank_score=None,
                        final_score=score,
                        reason="keyword_match",
                        citation_ready=True,
                        payload=payload,
                    )
                )

        return sorted(results, key=lambda item: (-(item.keyword_score or 0), self._position_sort_value(item.payload)))[:limit]

    def _fuse(
        self,
        dense_hits: list[VectorSearchResult],
        keyword_hits: list[HybridSearchResult],
    ) -> list[HybridSearchResult]:
        by_key: dict[str, HybridSearchResult] = {}
        ranks: dict[str, dict[str, int]] = {}
        rrf_k = 60

        for rank, dense_hit in enumerate(dense_hits, start=1):
            payload = dict(dense_hit.payload)
            result = HybridSearchResult(
                source_id=self._optional_int(payload.get("source_id")),
                chunk_id=self._optional_int(payload.get("chunk_id")) or 0,
                modality=self._optional_str(payload.get("modality")),
                locator=self._locator_from_payload(payload),
                dense_score=round(float(dense_hit.score), 4),
                keyword_score=None,
                rerank_score=None,
                final_score=0,
                reason="dense_match",
                citation_ready=bool(payload.get("chunk_id") and payload.get("content")),
                payload=payload,
            )
            key = self._key(result.payload)
            by_key[key] = result
            ranks.setdefault(key, {})["dense"] = rank

        for rank, keyword_hit in enumerate(keyword_hits, start=1):
            key = self._key(keyword_hit.payload)
            ranks.setdefault(key, {})["keyword"] = rank
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = keyword_hit
                continue
            existing.keyword_score = keyword_hit.keyword_score
            existing.locator = existing.locator or keyword_hit.locator
            existing.payload.update({key: value for key, value in keyword_hit.payload.items() if value is not None})
            existing.reason = "dense_keyword_rrf"

        maximum_rrf = 2.0 / (rrf_k + 1)
        for key, item in by_key.items():
            item_ranks = ranks[key]
            reciprocal_rank = sum(1.0 / (rrf_k + rank) for rank in item_ranks.values())
            item.final_score = round(min(1.0, reciprocal_rank / maximum_rrf), 4)
            if "dense" in item_ranks and "keyword" in item_ranks:
                item.reason = "dense_keyword_rrf"
            elif "dense" in item_ranks:
                item.reason = "dense_rrf"
            else:
                item.reason = "keyword_only_fallback; rrf"
            item.payload.update(
                {
                    "dense_score": item.dense_score,
                    "keyword_score": item.keyword_score,
                    "rerank_score": item.rerank_score,
                    "final_score": item.final_score,
                    "retrieval_reason": item.reason,
                    "citation_ready": item.citation_ready,
                    "locator": item.locator,
                }
            )

        return sorted(by_key.values(), key=lambda item: (-item.final_score, self._position_sort_value(item.payload)))

    def _maybe_rerank(self, query: str, fused: list[HybridSearchResult]) -> list[HybridSearchResult]:
        if not fused:
            return []
        if not self.rerank_provider.is_configured():
            for item in fused:
                item.reason = f"{item.reason}; rerank_not_configured"
                item.payload["retrieval_reason"] = item.reason
            return fused

        rerank_inputs = [
            RerankInput(query=query, content=str(item.payload.get("content", "")), metadata=item.payload)
            for item in fused
        ]
        outputs = self.rerank_provider.rerank(query, rerank_inputs)
        if len(outputs) != len(fused):
            return fused
        for item, output in zip(fused, outputs, strict=True):
            item.rerank_score = round(output.score, 4)
            # A configured reranker is the final relevance gate. Multiplying
            # preserves retrieval confidence while allowing an explicit zero
            # relevance score to remove a lexical/entity-only false positive.
            item.final_score = round(item.final_score * item.rerank_score, 4)
            item.reason = f"{item.reason}; rerank:{output.reason}"
            item.payload.update(
                {
                    "rerank_score": item.rerank_score,
                    "final_score": item.final_score,
                    "retrieval_reason": item.reason,
                }
            )
        return sorted(fused, key=lambda item: (-item.final_score, self._position_sort_value(item.payload)))

    def _key(self, payload: dict[str, Any]) -> str:
        source_id = payload.get("source_id")
        document_id = payload.get("document_id")
        chunk_id = payload.get("chunk_id")
        source_type = payload.get("source_type") or "document"
        return f"{source_type}:{source_id or document_id}:{chunk_id}"

    def _position_sort_value(self, payload: dict[str, Any]) -> int:
        for key in ("start_ms", "page_number", "chunk_index"):
            value = self._optional_int(payload.get(key))
            if value is not None:
                return value
        return 0

    def _locator_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        locator = payload.get("locator")
        if isinstance(locator, dict):
            return locator
        return {
            key: value
            for key, value in {
                "source_type": payload.get("source_type"),
                "source_id": payload.get("source_id"),
                "document_id": payload.get("document_id"),
                "page_number": payload.get("page_number"),
                "heading_path": payload.get("heading_path"),
                "section_title": payload.get("section_title"),
                "start_ms": payload.get("start_ms"),
                "end_ms": payload.get("end_ms"),
                "file_path": payload.get("file_path"),
                "line_start": payload.get("line_start"),
                "line_end": payload.get("line_end"),
                "symbol_name": payload.get("symbol_name"),
            }.items()
            if value is not None
        }

    def _json_dict(self, raw: str | None) -> dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _optional_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
