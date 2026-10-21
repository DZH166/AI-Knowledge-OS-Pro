from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock

from app.core.config import settings
from app.schemas.performance_schema import PerformancePathStats, PerformanceRequestRecord, PerformanceSnapshot, PerformanceSummary


@dataclass
class PerformanceObservation:
    request_id: str
    path: str
    method: str
    status_code: int
    latency_ms: int
    error_code: str | None
    provider_name: str | None
    provider_status: str | None
    retrieval_trace_id: str | None
    task_id: int | None
    cache_status: str | None
    demo_mode: bool
    timestamp: str


class PerformanceService:
    def __init__(self, *, maxlen: int = 200, slow_threshold_ms: int = 1000) -> None:
        self.maxlen = maxlen
        self.slow_threshold_ms = slow_threshold_ms
        self._records: deque[PerformanceObservation] = deque(maxlen=maxlen)
        self._lock = Lock()

    def record_request(
        self,
        *,
        request_id: str,
        path: str,
        method: str,
        status_code: int,
        latency_ms: int,
        error_code: str | None = None,
        provider_name: str | None = None,
        provider_status: str | None = None,
        retrieval_trace_id: str | None = None,
        task_id: int | None = None,
        cache_status: str | None = None,
    ) -> None:
        safe_path = path.split("?", 1)[0]
        record = PerformanceObservation(
            request_id=request_id,
            path=safe_path,
            method=method.upper(),
            status_code=status_code,
            latency_ms=max(0, int(latency_ms)),
            error_code=self._safe_token(error_code),
            provider_name=self._safe_token(provider_name),
            provider_status=self._safe_token(provider_status),
            retrieval_trace_id=self._safe_token(retrieval_trace_id),
            task_id=task_id,
            cache_status=self._safe_token(cache_status) or "server",
            demo_mode=settings.demo_mode,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._records.appendleft(record)

    def recent(self, limit: int = 50) -> list[PerformanceRequestRecord]:
        return [PerformanceRequestRecord(**item) for item in self._recent_dicts(limit)]

    def slow(self, limit: int = 10) -> list[PerformanceRequestRecord]:
        with self._lock:
            records = sorted(self._records, key=lambda item: item.latency_ms, reverse=True)[:limit]
        return [PerformanceRequestRecord(**asdict(item)) for item in records]

    def summary(self) -> PerformanceSummary:
        with self._lock:
            records = list(self._records)
        total = len(records)
        latencies = sorted(item.latency_ms for item in records)
        average = int(sum(latencies) / total) if total else 0
        p95 = latencies[min(total - 1, int(total * 0.95))] if total else 0
        slow_count = sum(1 for item in records if item.latency_ms >= self.slow_threshold_ms)
        duplicate_count = self._duplicate_count(records)
        cache_counts = Counter(item.cache_status or "server" for item in records)
        error_counts = Counter(item.error_code for item in records if item.error_code)
        return PerformanceSummary(
            total_requests=total,
            slow_request_count=slow_count,
            average_latency_ms=average,
            p95_latency_ms=p95,
            duplicate_request_count=duplicate_count,
            cache_status_counts=dict(cache_counts),
            error_code_counts=dict(error_counts),
            path_stats=self._path_stats(records),
            slow_threshold_ms=self.slow_threshold_ms,
            buffer_limit=self.maxlen,
        )

    def snapshot(self) -> PerformanceSnapshot:
        return PerformanceSnapshot(
            summary=self.summary(),
            recent_requests=self.recent(30),
            slow_requests=self.slow(10),
            notes=[
                "Performance data is an in-process rolling buffer and resets when the API process restarts.",
                "Only request metadata is recorded; API keys, uploaded file contents and full user prompts are not stored.",
                "Frontend cache hits that do not reach the backend are shown in the browser performance panel.",
            ],
        )

    def _recent_dicts(self, limit: int) -> list[dict]:
        with self._lock:
            return [asdict(item) for item in list(self._records)[:limit]]

    def _path_stats(self, records: list[PerformanceObservation]) -> list[PerformancePathStats]:
        grouped: dict[str, list[int]] = defaultdict(list)
        for item in records:
            grouped[f"{item.method} {item.path}"].append(item.latency_ms)
        stats: list[PerformancePathStats] = []
        for path, values in grouped.items():
            stats.append(
                PerformancePathStats(
                    path=path,
                    count=len(values),
                    average_latency_ms=int(sum(values) / len(values)),
                    max_latency_ms=max(values),
                    slow_count=sum(1 for value in values if value >= self.slow_threshold_ms),
                )
            )
        return sorted(stats, key=lambda item: (item.slow_count, item.max_latency_ms, item.count), reverse=True)

    @staticmethod
    def _duplicate_count(records: list[PerformanceObservation]) -> int:
        counts = Counter(f"{item.method} {item.path}" for item in records)
        return sum(count - 1 for count in counts.values() if count > 1)

    @staticmethod
    def _safe_token(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = "".join(ch for ch in str(value) if ch.isalnum() or ch in {"_", "-", ".", ":"})[:80]
        return cleaned or None


performance_service = PerformanceService()
