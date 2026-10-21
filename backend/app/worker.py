from __future__ import annotations

from datetime import UTC, datetime
import logging
from threading import Event, Thread

from redis import Redis
from rq import Queue, SimpleWorker

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ingestion_job import IngestionJob
from app.modules.evidence_agent.recovery import AgentInvocationRecovery
from app.modules.agent_control.contracts import RecoverEvaluations
from app.modules.agent_control.service import SqlAgentControl
from app.services.task_broker import mark_stale_jobs_interrupted, task_broker
from app.services.outbox_dispatcher import OutboxDispatcher, new_dispatcher_worker_id


logger = logging.getLogger(__name__)


def build_worker(
    queues: list[Queue],
    *,
    connection: Redis,
    worker_name: str | None = None,
) -> SimpleWorker:
    options = {"name": worker_name} if worker_name else {}
    return SimpleWorker(queues, connection=connection, **options)


def _recover_agent_invocations() -> None:
    result = AgentInvocationRecovery(SessionLocal).recover_once(
        stale_after_seconds=settings.task_timeout_seconds,
        limit=settings.outbox_batch_size,
    )
    if result.requeued or result.failed:
        logger.warning(
            "Recovered interrupted Agent invocations: requeued=%s failed=%s.",
            result.requeued,
            result.failed,
        )


def _recover_agent_evaluations() -> None:
    recovered = SqlAgentControl(
        SessionLocal,
        lease_seconds=settings.evaluation_lease_seconds,
    ).recover(RecoverEvaluations(now=datetime.now(UTC)))
    if recovered:
        logger.warning("Recovered interrupted Agent evaluations: failed=%s.", recovered)


def _maintain_durable_work(stop: Event) -> None:
    dispatcher_owner = new_dispatcher_worker_id("worker")
    dispatcher = OutboxDispatcher(
        SessionLocal,
        task_broker,
        worker_id=dispatcher_owner,
        lease_seconds=settings.outbox_lease_seconds,
    )
    while not stop.is_set():
        try:
            _recover_agent_invocations()
        except Exception:
            logger.exception("Agent invocation recovery failed; the durable fence will be retried.")
        try:
            _recover_agent_evaluations()
        except Exception:
            logger.exception("Agent evaluation recovery failed; the durable lease will be retried.")
        try:
            result = dispatcher.dispatch_once(limit=settings.outbox_batch_size)
            if result.claimed:
                logger.info(
                    "Outbox dispatch: claimed=%s published=%s failed=%s dead_lettered=%s.",
                    result.claimed,
                    result.published,
                    result.failed,
                    result.dead_lettered,
                )
        except Exception:
            # Durable SQL leases keep messages recoverable; worker logging captures
            # unexpected broker/database faults without killing ingestion work.
            logger.exception("Outbox dispatch failed; the durable lease will be retried.")
        stop.wait(settings.outbox_poll_seconds)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    connection = Redis.from_url(settings.redis_url)
    queue_names = [name.strip() for name in settings.worker_queues.split(",") if name.strip()]
    db = SessionLocal()
    try:
        mark_stale_jobs_interrupted(db)
        try:
            _recover_agent_invocations()
        except Exception:
            logger.exception("Agent invocation startup recovery failed; maintenance will retry it.")
        try:
            _recover_agent_evaluations()
        except Exception:
            logger.exception("Agent evaluation startup recovery failed; maintenance will retry it.")
        queued = db.query(IngestionJob).filter(
            IngestionJob.status.in_(["queued", "retry_scheduled", "interrupted"])
        ).all()
        for job in queued:
            try:
                enqueue = getattr(task_broker, "enqueue_task", task_broker.enqueue_ingestion)
                enqueue(job.id, job.queue_name)
            except Exception:
                logger.exception("Failed to requeue interrupted ingestion job %s.", job.id)
                continue
    finally:
        db.close()
    stop = Event()
    dispatcher_thread = Thread(
        target=_maintain_durable_work,
        args=(stop,),
        name="durable-work-maintainer",
        daemon=True,
    )
    dispatcher_thread.start()
    worker = build_worker(
        [Queue(name, connection=connection) for name in queue_names],
        connection=connection,
        worker_name=settings.worker_name,
    )
    try:
        worker.work(with_scheduler=True)
    finally:
        stop.set()
        dispatcher_thread.join(timeout=5)


if __name__ == "__main__":
    main()
