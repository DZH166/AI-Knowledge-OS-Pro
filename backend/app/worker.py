from __future__ import annotations

from redis import Redis
from rq import Queue, SimpleWorker

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ingestion_job import IngestionJob
from app.services.task_broker import mark_stale_jobs_interrupted, task_broker


def main() -> None:
    connection = Redis.from_url(settings.redis_url)
    queue_names = [name.strip() for name in settings.worker_queues.split(",") if name.strip()]
    db = SessionLocal()
    try:
        mark_stale_jobs_interrupted(db)
        queued = db.query(IngestionJob).filter(
            IngestionJob.status.in_(["queued", "retry_scheduled", "interrupted"])
        ).all()
        for job in queued:
            try:
                enqueue = getattr(task_broker, "enqueue_task", task_broker.enqueue_ingestion)
                enqueue(job.id, job.queue_name)
            except Exception:
                continue
    finally:
        db.close()
    worker = SimpleWorker([Queue(name, connection=connection) for name in queue_names], connection=connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
