from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.ingestion_job import IngestionJob
from app.models.task_event import JobEvent
from app.services.ingestion_service import DocumentIngestionService
from app.services.task_broker import mark_stale_jobs_interrupted


def test_background_enqueue_writes_persistent_event(
    db_session,
    knowledge_space,
    fake_embedding,
    fake_vector_store,
    fake_task_broker,
    upload_factory,
) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, job = service.ingest_upload(db_session, knowledge_space.id, upload_factory(), process_immediately=False)

    service.start_background_processing(document.id, job.id, mode="reparse", db=db_session)

    db_session.refresh(job)
    events = list(db_session.scalars(select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.id.asc())))
    assert job.status == "queued"
    assert fake_task_broker.enqueued == [(job.id, "default")]
    assert [event.event_type for event in events] == ["queued", "queued"]
    assert events[-1].message == "任务已写入 Redis 队列。"


def test_cancel_job_persists_cancel_request_and_event(
    db_session,
    knowledge_space,
    fake_embedding,
    fake_vector_store,
    fake_task_broker,
    upload_factory,
) -> None:
    service = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    _document, job = service.ingest_upload(db_session, knowledge_space.id, upload_factory(), process_immediately=False)
    job.status = "running"
    job.current_step = "embedding"
    db_session.commit()

    cancelled = service.cancel_job(db_session, job.id)

    assert cancelled.status == "cancelling"
    assert cancelled.cancel_requested_at is not None
    assert fake_task_broker.cancelled == [job.id]
    event = db_session.scalar(select(JobEvent).where(JobEvent.job_id == job.id, JobEvent.event_type == "cancelling"))
    assert event is not None
    assert event.step == "embedding"


def test_stale_running_jobs_are_marked_interrupted(db_session, knowledge_space, upload_factory) -> None:
    document_service = DocumentIngestionService()
    document, job = document_service.ingest_upload(db_session, knowledge_space.id, upload_factory(), process_immediately=False)
    job.status = "running"
    job.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=3)
    job.error_message = None
    db_session.commit()

    changed = mark_stale_jobs_interrupted(db_session)

    refreshed = db_session.get(IngestionJob, job.id)
    assert changed == 1
    assert refreshed is not None
    assert refreshed.status == "interrupted"
    assert refreshed.error_code == "WORKER_INTERRUPTED"
    assert document.id == refreshed.document_id
