import json

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.ingestion_job import IngestionJob
from app.models.source import Source


def test_media_job_routes_return_nullable_document_and_media_target_fields(
    db_session, knowledge_space, monkeypatch
) -> None:
    source = Source(
        space_id=knowledge_space.id,
        source_type="video",
        title="Route contract video",
        original_filename="route-contract.mp4",
        mime_type="video/mp4",
        file_size=1024,
        status="ready",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    job = IngestionJob(
        document_id=None,
        source_id=source.id,
        space_id=knowledge_space.id,
        target_type="media",
        job_type="video_transcription",
        status="failed",
        progress=42,
        message="Provider unavailable.",
        error_code="TRANSCRIPTION_NOT_CONFIGURED",
        result_json=json.dumps({"detail_url": f"/media/sources/{source.id}"}),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("app.services.media_task_service.task_broker.cancel", lambda _job_id: True)
    try:
        client = TestClient(app)
        response = client.get("/api/ingestion-jobs", params={"target_type": "media"})
        assert response.status_code == 200
        payload = response.json()["data"]
        assert len(payload) == 1
        assert payload[0]["document_id"] is None
        assert payload[0]["source_id"] == source.id
        assert payload[0]["target_type"] == "media"
        assert json.loads(payload[0]["result_json"])["detail_url"] == f"/media/sources/{source.id}"

        cancel_response = client.post(f"/api/ingestion-jobs/{job.id}/cancel")
        assert cancel_response.status_code == 200
        cancelled = cancel_response.json()["data"]
        assert cancelled["status"] == "cancelled"
        assert cancelled["document_id"] is None
        assert cancelled["source_id"] == source.id
        assert cancelled["target_type"] == "media"
    finally:
        app.dependency_overrides.pop(get_db, None)
