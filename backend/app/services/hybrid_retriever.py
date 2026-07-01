from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import MultimodalChunk, Source
from app.services.rerank_provider import RerankInput, RerankProvider, get_rerank_provider
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
        limit: int | None = None,
        score_threshold: float | None = None,
    ) -> list[HybridSearchResult]:
        top_k = limit or settings.retrieval_top_k
        dense_hits = self.vector_store.search(
            space_id=space_id,
            query_vector=query_vector,
            limit=max(top_k * 2, top_k),
            score_threshold=score_threshold if score_threshold is not None else settings.retrieval_score_threshold,
        )
        keyword_hits = self._keyword_search(db, space_id=space_id, query=query, limit=max(top_k * 4, top_k))
        fused = self._fuse(dense_hits, keyword_hits)
        reranked = self._maybe_rerank(query, fused)
        return reranked[:top_k]

    def _keyword_search(self, db: Session, *, space_id: int, query: str, limit: int) -> list[HybridSearchResult]:
        tokens = self._tokens(query)
        if not tokens:
            return []

        results: list[HybridSearchResult] = []
        document_chunks = db.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Chunk.space_id == space_id,
                Document.status == "ready",
                Document.vector_status == "indexed",
            )
            .order_by(Chunk.created_at.desc())
            .limit(limit * 4)
        ).all()
        for chunk, document in document_chunks:
            score = self._keyword_score(tokens, chunk.content)
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

        multimodal_chunks = db.execute(
            select(MultimodalChunk, Source)
            .join(Source, MultimodalChunk.source_id == Source.id)
            .where(
                Source.space_id == space_id,
                Source.status == "ready",
                MultimodalChunk.status.in_(("active", "ready")),
            )
            .order_by(MultimodalChunk.created_at.desc())
            .limit(limit * 4)
        ).all()
        for chunk, source in multimodal_chunks:
            score = self._keyword_score(tokens, chunk.search_text or chunk.content_text)
            if score <= 0:
                continue
            locator = self._json_dict(chunk.locator_json)
            payload = {
                "space_id": space_id,
                "source_id": source.id,
                "document_id": source.document_id,
                "document_name": source.title or source.original_filename or f"Source #{source.id}",
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content_text,
                "content_preview": chunk.content_text[:220],
                "source_type": chunk.source_type,
                "modality": chunk.modality,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "locator": locator,
            }
            results.append(
                HybridSearchResult(
                    source_id=source.id,
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

        return sorted(results, key=lambda item: (-(item.keyword_score or 0), self._position_sort_value(item.payload)))[:limit]

    def _fuse(
        self,
        dense_hits: list[VectorSearchResult],
        keyword_hits: list[HybridSearchResult],
    ) -> list[HybridSearchResult]:
        by_key: dict[str, HybridSearchResult] = {}

        for dense_hit in dense_hits:
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
            by_key[self._key(result.payload)] = result

        for keyword_hit in keyword_hits:
            key = self._key(keyword_hit.payload)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = keyword_hit
                continue
            existing.keyword_score = keyword_hit.keyword_score
            existing.locator = existing.locator or keyword_hit.locator
            existing.payload.update({key: value for key, value in keyword_hit.payload.items() if value is not None})
            existing.reason = "dense_keyword_fusion"

        for item in by_key.values():
            dense = item.dense_score or 0.0
            keyword = item.keyword_score or 0.0
            if item.dense_score is not None and item.keyword_score is not None:
                fused_score = min(1.0, 0.68 * dense + 0.32 * keyword + 0.05)
                item.final_score = round(max(dense, fused_score), 4)
            elif item.dense_score is not None:
                item.final_score = round(dense, 4)
            else:
                item.final_score = round(min(0.85, keyword * 0.82), 4)
                item.reason = "keyword_only_fallback"
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
            item.final_score = round(min(1.0, 0.55 * item.final_score + 0.45 * item.rerank_score), 4)
            item.reason = f"{item.reason}; rerank:{output.reason}"
            item.payload.update(
                {
                    "rerank_score": item.rerank_score,
                    "final_score": item.final_score,
                    "retrieval_reason": item.reason,
                }
            )
        return sorted(fused, key=lambda item: (-item.final_score, self._position_sort_value(item.payload)))

    def _keyword_score(self, tokens: list[str], content: str) -> float:
        text = content.lower()
        if not text:
            return 0.0
        matched = 0.0
        for token in tokens:
            count = text.count(token)
            if count:
                matched += 1.0 + min(2.0, math.log1p(count))
        if matched <= 0:
            return 0.0
        coverage = matched / max(1.0, len(tokens) * 2.1)
        return round(min(1.0, coverage), 4)

    def _tokens(self, query: str) -> list[str]:
        raw = query.lower().strip()
        tokens = re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", raw)
        if not tokens and raw:
            tokens = [raw]
        return list(dict.fromkeys(tokens))

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
