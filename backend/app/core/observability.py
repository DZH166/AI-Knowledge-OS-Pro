from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class RequestObservation:
    request_id: str
    method: str
    path: str
    status_code: int
    latency_ms: int
    error_code: str | None
    created_at: str


class ObservabilityStore:
    def __init__(self, maxlen: int = 100) -> None:
        self._requests: deque[RequestObservation] = deque(maxlen=maxlen)
        self._lock = Lock()

    def record_request(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        latency_ms: int,
        error_code: str | None = None,
    ) -> None:
        observation = RequestObservation(
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
            error_code=error_code,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._requests.appendleft(observation)

    def recent_requests(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return [asdict(item) for item in list(self._requests)[:limit]]


observability_store = ObservabilityStore()

