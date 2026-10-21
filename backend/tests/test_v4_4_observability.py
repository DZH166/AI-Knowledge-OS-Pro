import json

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.ingestion_job import IngestionJob
from app.models.qa_log import QALog
from app.models.task_event import JobEvent
from app.schemas.system_schema import ComponentStatus
from app.services.system_service import system_service


def test_v4_4_observability_routes_return_recent_runtime_signals(db_session, knowledge_space, monkeypatch) -> None:
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

    job = IngestionJob(
        space_id=knowledge_space.id,
        target_type="media",
        source_id=None,
        job_type="video_transcription",
        status="failed",
        current_step="transcription",
        progress=60,
        error_code="TRANSCRIPTION_NOT_CONFIGURED",
        error_message="No speech provider configured.",
        duration_ms=1200,
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        JobEvent(
            job_id=job.id,
            event_type="failed",
            step="transcription",
            progress=60,
            message="Provider missing; no fake transcript generated.",
            technical_message="TRANSCRIPTION_NOT_CONFIGURED",
        )
    )
    db_session.add(
        QALog(
            space_id=knowledge_space.id,
            question="How does V4.4 observe retrieval?",
            answer="It derives retrieval observations from persisted QA logs.",
            answer_mode="normal",
            citations_json=json.dumps(
                [
                    {
                        "citation_id": "C1",
                        "source_type": "video",
                        "source_id": 1,
                        "chunk_id": 11,
                        "start_ms": 1000,
                        "end_ms": 3000,
                    }
                ]
            ),
            related_chunks_json="[]",
            used_citation_ids_json=json.dumps(["C1"]),
            answer_confidence="high",
            retrieval_score=0.91,
            retrieval_status="grounded",
            runtime_mode="demo",
        )
    )
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        client.get("/api/system/status", headers={"x-request-id": "v4-4-request"})
        response = client.get("/api/system/observability")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        data = payload["data"]
        assert data["runtime_mode"] in {"demo", "real"}
        assert any(item["request_id"] == "v4-4-request" for item in data["recent_requests"])
        assert data["recent_tasks"][0]["task_id"] == job.id
        assert data["recent_tasks"][0]["error_code"] == "TRANSCRIPTION_NOT_CONFIGURED"
        assert data["recent_retrievals"][0]["retrieval_trace_id"].startswith("qa-")
        assert data["recent_retrievals"][0]["citation_validation_status"] == "passed"
        assert data["recent_retrievals"][0]["retrieval_source_mix"]["video"] == 1
        assert any(item["provider_name"] == "llm" for item in data["provider_status"])
        assert data["error_categories"]["TRANSCRIPTION_NOT_CONFIGURED"] == 1

        endpoints = [
            "/api/system/observability/recent-requests",
            "/api/system/observability/recent-tasks",
            "/api/system/observability/recent-retrievals",
            "/api/system/observability/provider-status",
        ]
        for endpoint in endpoints:
            item_response = client.get(endpoint)
            assert item_response.status_code == 200, endpoint
            assert item_response.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)

