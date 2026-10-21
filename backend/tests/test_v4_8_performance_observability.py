from fastapi.testclient import TestClient

from app.main import app
from app.schemas.system_schema import ComponentStatus
from app.services.performance_service import PerformanceService
from app.services.system_service import system_service


def test_v4_8_performance_routes_return_runtime_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        system_service,
        "_qdrant_status",
        lambda: ComponentStatus(ok=False, status="unavailable", message="Qdrant unavailable", details={"error": "test"}),
    )
    monkeypatch.setattr(
        system_service,
        "_redis_status",
        lambda: ComponentStatus(ok=False, status="unavailable", message="Redis unavailable", details={"error": "test"}),
    )

    client = TestClient(app)
    client.get("/api/system/status", headers={"x-request-id": "v4-8-runtime-status", "x-client-cache-status": "miss"})

    response = client.get("/api/system/performance", headers={"x-request-id": "v4-8-performance"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["summary"]["total_requests"] >= 1
    assert data["summary"]["buffer_limit"] == 200
    assert data["summary"]["cache_status_counts"]
    assert any(item["request_id"] == "v4-8-runtime-status" for item in data["recent_requests"])
    assert all("?" not in item["path"] for item in data["recent_requests"])
    assert any("API keys" in note for note in data["notes"])

    endpoints = [
        "/api/system/performance/recent",
        "/api/system/performance/slow",
        "/api/system/performance/summary",
    ]
    for endpoint in endpoints:
        item_response = client.get(endpoint)
        assert item_response.status_code == 200, endpoint
        assert item_response.json()["success"] is True


def test_v4_8_performance_service_uses_bounded_sanitized_records() -> None:
    service = PerformanceService(maxlen=3, slow_threshold_ms=50)
    for index, latency in enumerate([10, 20, 60, 70, 80]):
        service.record_request(
            request_id=f"req-{index}",
            path=f"/api/private?token=secret-{index}",
            method="get",
            status_code=200 if index < 4 else 503,
            latency_ms=latency,
            error_code="BAD TOKEN !!!" if index == 4 else None,
            provider_name="llm provider with spaces",
            cache_status="hit" if index % 2 == 0 else "miss",
        )

    recent = service.recent(10)
    assert len(recent) == 3
    assert [item.request_id for item in recent] == ["req-4", "req-3", "req-2"]
    assert all(item.path == "/api/private" for item in recent)
    assert all("secret" not in item.path for item in recent)
    assert recent[0].error_code == "BADTOKEN"
    assert recent[0].provider_name == "llmproviderwithspaces"

    summary = service.summary()
    assert summary.total_requests == 3
    assert summary.slow_request_count == 3
    assert summary.duplicate_request_count == 2
    assert summary.cache_status_counts["hit"] == 2
    assert summary.cache_status_counts["miss"] == 1
