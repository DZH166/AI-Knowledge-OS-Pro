from __future__ import annotations

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.evidence_agent.wiring import get_agent_runner
from app.services.outbox_dispatcher import OutboxDispatcher, new_dispatcher_worker_id
from app.services.task_broker import task_broker


def advance_agent_run(run_id: str, expected_version: int, execution_epoch: int) -> dict[str, object]:
    """RQ entrypoint: execute exactly one fenced slice, then wake the dispatcher."""

    result = get_agent_runner().advance_one(
        run_id,
        expected_version=expected_version,
        execution_epoch=execution_epoch,
    )
    dispatcher = OutboxDispatcher(
        SessionLocal,
        task_broker,
        worker_id=new_dispatcher_worker_id("agent-task"),
        lease_seconds=settings.outbox_lease_seconds,
    )
    dispatcher.dispatch_once(limit=settings.outbox_batch_size)
    return {
        "run_id": result.run_id,
        "applied": result.applied,
        "version": result.version,
        "status": result.status.value,
        "reason": result.reason,
    }
