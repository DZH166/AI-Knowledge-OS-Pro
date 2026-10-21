import json
from pathlib import Path

import pytest

from app.models.ingestion_job import IngestionJob
from app.models.task_event import JobEvent
from app.services.media_service import MediaService
from app.services.media_task_service import MediaTaskService
from app.services.transcription_service import (
    TranscriptionResult,
    TranscriptionSegmentResult,
    UnconfiguredTranscriptionProvider,
)
from tests.conftest import FakeEmbeddingService, FakeVectorStore
from tests.test_v3_audio_transcription import make_wav_upload


class FakeTaskTranscriptionProvider:
    name = "fake_task_transcription"
    model = "fake-whisper-task"

    def is_configured(self) -> bool:
        return True

    def transcribe(self, audio_path: Path, mime_type: str | None = None) -> TranscriptionResult:
        assert audio_path.exists()
        return TranscriptionResult(
            text="RAG task transcript from a real uploaded wav file.",
            language="en",
            duration_ms=1000,
            segments=[
                TranscriptionSegmentResult(index=0, start_ms=0, end_ms=1000, text="RAG task transcript from a real uploaded wav file."),
            ],
            provider=self.name,
            model=self.model,
        )


def test_media_task_success_records_source_target_events_and_result(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    processor = MediaService(
        transcription_provider=FakeTaskTranscriptionProvider(),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(),
    )
    task_service = MediaTaskService(processor)
    source = processor.upload_audio(db_session, knowledge_space.id, make_wav_upload(duration_ms=1000))

    job = task_service.create_job(db_session, source.id, "audio_transcription", process_immediately=True)

    assert job.target_type == "media"
    assert job.document_id is None
    assert job.source_id == source.id
    assert job.status == "completed"
    assert json.loads(job.result_json)["detail_url"] == f"/media/sources/{source.id}"
    assert db_session.query(IngestionJob).filter_by(target_type="media", source_id=source.id).count() == 1
    events = db_session.query(JobEvent).filter_by(job_id=job.id).order_by(JobEvent.id).all()
    assert events[0].event_type == "queued"
    assert events[-1].event_type == "completed"
    assert processor.get_source(db_session, source.id).metadata_data["last_job_status"] == "completed"


def test_media_task_unconfigured_transcription_fails_without_fake_segments(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    processor = MediaService(transcription_provider=UnconfiguredTranscriptionProvider())
    task_service = MediaTaskService(processor)
    source = processor.upload_audio(db_session, knowledge_space.id, make_wav_upload(duration_ms=1000))

    job = task_service.create_job(db_session, source.id, "audio_transcription")
    with pytest.raises(Exception):
        task_service.process_job(db_session, job.id)

    failed = db_session.get(IngestionJob, job.id)
    refreshed = processor.get_source(db_session, source.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error_code == "TRANSCRIPTION_NOT_CONFIGURED"
    assert refreshed.revisions[0].transcript_segments == []
    assert refreshed.revisions[0].chunks == []
