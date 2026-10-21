from app.core.config import settings
from app.schemas.system_schema import ComponentStatus
from app.services.system_service import system_service


def test_system_status_includes_task_runtime_without_secret_leak(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "redis_url", "redis://:super-secret@localhost:6379/0")
    monkeypatch.setattr(
        system_service,
        "_redis_status",
        lambda: ComponentStatus(ok=False, status="unavailable", message="Redis unavailable", details={"error": "test"}),
    )

    status = system_service.status(db_session)

    assert status.runtime.app_version == "V5.0"
    assert status.runtime.semantic_version == "5.0.0"
    assert status.runtime.redis_url == "redis://***:***@localhost:6379/0"
    assert status.runtime.task_queue_name == settings.task_queue_name
    assert status.runtime.ocr_provider == settings.ocr_provider
    assert status.ocr.status in {"not_configured", "configured"}
    assert status.runtime.transcription_provider == settings.transcription_provider
    assert status.transcription.status in {"not_configured", "configured"}
    assert status.redis.status == "unavailable"
    assert "super-secret" not in status.model_dump_json()
    assert "active_workers" in status.worker.details
