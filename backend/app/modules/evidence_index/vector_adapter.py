from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class VectorPointWrite:
    point_id: str
    vector: tuple[float, ...]
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class VectorPointState:
    point_id: str
    vector: tuple[float, ...]
    payload: Mapping[str, Any]


class VectorIndexPort(Protocol):
    """Internal seam implemented by Qdrant and recording adapters."""

    def upsert_points(self, collection: str, points: Sequence[VectorPointWrite]) -> None: ...

    def delete_points(self, collection: str, point_ids: Sequence[str]) -> None: ...

    def list_points(self, collection: str) -> tuple[VectorPointState, ...]: ...


class QdrantVectorAdapter:
    """Qdrant binding with an injected client and no eager network activity."""

    def __init__(self, client: Any, *, scroll_batch_size: int = 256) -> None:
        if scroll_batch_size <= 0:
            raise ValueError("scroll_batch_size must be positive.")
        self._client = client
        self._scroll_batch_size = scroll_batch_size

    def upsert_points(self, collection: str, points: Sequence[VectorPointWrite]) -> None:
        if not points:
            return
        from qdrant_client.http import models as qdrant_models

        self._client.upsert(
            collection_name=collection,
            points=[
                qdrant_models.PointStruct(
                    id=point.point_id,
                    vector=list(point.vector),
                    payload=dict(point.payload),
                )
                for point in points
            ],
            wait=True,
        )

    def delete_points(self, collection: str, point_ids: Sequence[str]) -> None:
        if not point_ids:
            return
        from qdrant_client.http import models as qdrant_models

        self._client.delete(
            collection_name=collection,
            points_selector=qdrant_models.PointIdsList(points=list(point_ids)),
            wait=True,
        )

    def list_points(self, collection: str) -> tuple[VectorPointState, ...]:
        states: list[VectorPointState] = []
        offset: Any = None
        while True:
            records, next_offset = self._client.scroll(
                collection_name=collection,
                limit=self._scroll_batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            states.extend(
                VectorPointState(
                    point_id=str(record.id),
                    vector=self._dense_vector(record.vector),
                    payload=dict(record.payload or {}),
                )
                for record in records
            )
            if next_offset is None:
                break
            offset = next_offset
        return tuple(sorted(states, key=lambda point: point.point_id))

    @staticmethod
    def _dense_vector(raw_vector: Any) -> tuple[float, ...]:
        if isinstance(raw_vector, Mapping):
            if len(raw_vector) != 1:
                raise ValueError("EvidenceIndex expects one dense vector per Qdrant point.")
            raw_vector = next(iter(raw_vector.values()))
        if not isinstance(raw_vector, (list, tuple)):
            raise ValueError("Qdrant point did not return a dense vector.")
        return tuple(float(value) for value in raw_vector)


class RecordingVectorAdapter:
    """Stateful local adapter for lifecycle and recovery contract tests."""

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, VectorPointState]] = {}
        self._next_upsert_error: Exception | None = None
        self._next_delete_error: Exception | None = None

    def upsert_points(self, collection: str, points: Sequence[VectorPointWrite]) -> None:
        target = self._collections.setdefault(collection, {})
        for point in points:
            target[point.point_id] = VectorPointState(
                point_id=point.point_id,
                vector=tuple(point.vector),
                payload=dict(point.payload),
            )
        if self._next_upsert_error is not None:
            error = self._next_upsert_error
            self._next_upsert_error = None
            raise error

    def delete_points(self, collection: str, point_ids: Sequence[str]) -> None:
        if self._next_delete_error is not None:
            error = self._next_delete_error
            self._next_delete_error = None
            raise error
        target = self._collections.setdefault(collection, {})
        for point_id in point_ids:
            target.pop(point_id, None)

    def list_points(self, collection: str) -> tuple[VectorPointState, ...]:
        target = self._collections.get(collection, {})
        return tuple(target[point_id] for point_id in sorted(target))

    def fail_next_upsert_after_write(self, error: Exception) -> None:
        self._next_upsert_error = error

    def fail_next_delete(self, error: Exception) -> None:
        self._next_delete_error = error
