from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.core.config import settings
from app.core.errors import DependencyUnavailableError


@dataclass(frozen=True)
class VectorSearchResult:
    score: float
    payload: dict


class VectorStore:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout_seconds,
            # Compatibility is reported by the explicit status endpoint. Avoid
            # hidden network I/O merely by importing a service in tests/workers.
            check_compatibility=False,
        )
        self.collection_name = settings.qdrant_collection

    def status(self) -> dict:
        try:
            collections = self.client.get_collections()
            exists = self.client.collection_exists(self.collection_name)
        except Exception as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "message": f"Qdrant 不可用：{exc}",
                "collection_exists": False,
            }
        return {
            "ok": True,
            "status": "ready",
            "message": "Qdrant 连接正常。",
            "collection_exists": exists,
            "collection_count": len(collections.collections),
        }

    def ensure_collection(self) -> None:
        try:
            if self.client.collection_exists(self.collection_name):
                return
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=settings.embedding_dimensions,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
        except Exception as exc:
            raise DependencyUnavailableError(f"Qdrant collection 初始化失败：{exc}", code="QDRANT_UNAVAILABLE") from exc

    def upsert_chunks(
        self,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        self.ensure_collection()
        points = [
            qdrant_models.PointStruct(id=point_id, vector=vector, payload=payload)
            for point_id, vector, payload in zip(point_ids, vectors, payloads, strict=True)
        ]
        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as exc:
            raise DependencyUnavailableError(f"Qdrant 写入失败：{exc}", code="QDRANT_UPSERT_FAILED") from exc

    def search(
        self,
        space_id: int,
        query_vector: list[float],
        limit: int | None = None,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        self.ensure_collection()
        query_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="space_id",
                    match=qdrant_models.MatchValue(value=space_id),
                )
            ]
        )
        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit or settings.retrieval_top_k,
                score_threshold=score_threshold if score_threshold is not None else settings.retrieval_score_threshold,
                with_payload=True,
            )
        except Exception as exc:
            raise DependencyUnavailableError(f"Qdrant 检索失败：{exc}", code="QDRANT_SEARCH_FAILED") from exc
        hits = response.points
        return [VectorSearchResult(score=float(hit.score), payload=hit.payload or {}) for hit in hits]

    def delete_points(self, point_ids: list[str]) -> None:
        if not point_ids:
            return
        self.ensure_collection()
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qdrant_models.PointIdsList(points=point_ids),
            )
        except Exception as exc:
            raise DependencyUnavailableError(f"Qdrant 删除 point 失败：{exc}", code="QDRANT_DELETE_FAILED") from exc

    def count_points(self) -> int | None:
        try:
            if not self.client.collection_exists(self.collection_name):
                return 0
            result = self.client.count(collection_name=self.collection_name, exact=True)
            return int(result.count)
        except Exception:
            return None
