from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ingestion_job import IngestionJob


class TaskBroker(Protocol):
    def publish(self, envelope: "TaskEnvelope") -> str: ...

    def enqueue_task(self, job_id: int, queue_name: str = "default") -> str: ...

    def enqueue_ingestion(self, job_id: int, queue_name: str = "default") -> str: ...

    def cancel(self, job_id: int) -> bool: ...


@dataclass(slots=True)
class EnqueuedTask:
    broker_job_id: str
    queue_name: str


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    task_id: str
    topic: str
    payload: dict[str, Any]
    queue_name: str = ""


class RedisRQTaskBroker:
    """Redis/RQ adapter. Imports are lazy so unit tests do not need Redis."""

    def publish(self, envelope: TaskEnvelope) -> str:
        from redis import Redis
        from rq import Queue, Retry

        connection = Redis.from_url(settings.redis_url)
        queue = Queue(envelope.queue_name or settings.task_queue_name, connection=connection)
        if envelope.topic == "agent.advance":
            function = "app.tasks.agent_tasks.advance_agent_run"
            arguments = (
                str(envelope.payload["run_id"]),
                int(envelope.payload["version"]),
                int(envelope.payload["execution_epoch"]),
            )
        elif envelope.topic == "evidence_index.reconcile":
            function = "app.tasks.evidence_index_tasks.reconcile_evidence_index"
            arguments = (bool(envelope.payload.get("apply", False)),)
        else:
            raise ValueError(f"Unsupported task topic: {envelope.topic}")
        enqueue_options: dict[str, Any] = {
            "job_id": envelope.task_id,
            "job_timeout": settings.task_timeout_seconds,
            "result_ttl": 86_400,
            "failure_ttl": 604_800,
        }
        if envelope.topic == "agent.advance":
            enqueue_options["retry"] = Retry(
                max=max(1, settings.task_max_attempts),
                interval=[5, 30, 120],
            )
        rq_job = queue.enqueue(
            function,
            *arguments,
            **enqueue_options,
        )
        return rq_job.id

    def enqueue_task(self, job_id: int, queue_name: str = "default") -> str:
        from redis import Redis
        from rq import Queue

        connection = Redis.from_url(settings.redis_url)
        queue = Queue(queue_name or settings.task_queue_name, connection=connection)
        rq_job = queue.enqueue(
            "app.tasks.ingestion_tasks.run_task_job",
            job_id,
            job_id=f"task-{job_id}",
            job_timeout=settings.task_timeout_seconds,
            result_ttl=86400,
            failure_ttl=604800,
        )
        return rq_job.id

    def enqueue_ingestion(self, job_id: int, queue_name: str = "default") -> str:
        return self.enqueue_task(job_id, queue_name)

    def cancel(self, job_id: int) -> bool:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(settings.redis_url)
        for broker_job_id in (f"task-{job_id}", f"ingestion-{job_id}"):
            try:
                rq_job = Job.fetch(broker_job_id, connection=connection)
            except Exception:
                continue
            rq_job.cancel()
            return True
        return False


def mark_stale_jobs_interrupted(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.task_heartbeat_timeout_seconds)
    jobs = list(
        db.scalars(
            select(IngestionJob).where(
                IngestionJob.status.in_(["claimed", "running", "cancelling"]),
            )
        )
    )
    changed = 0
    for job in jobs:
        heartbeat = job.heartbeat_at or job.started_at or job.updated_at
        if heartbeat is not None and heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        if heartbeat is None or heartbeat <= cutoff:
            job.status = "interrupted"
            job.finished_at = datetime.now(timezone.utc)
            job.error_code = "WORKER_INTERRUPTED"
            job.error_message = "Worker 心跳超时，任务已标记为中断，可重新入队。"
            changed += 1
    if changed:
        db.commit()
    return changed


task_broker: TaskBroker = RedisRQTaskBroker()
