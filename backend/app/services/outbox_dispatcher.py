from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
import socket
from threading import Event, Thread
from typing import Callable
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models.outbox import OutboxMessage
from app.models.agent_run import AgentRun
from app.modules.evidence_agent.contracts import RunStatus
from app.modules.evidence_agent.sql_store import SqlAgentJournal
from app.services.task_broker import TaskBroker, TaskEnvelope


SessionFactory = Callable[[], Session]


def new_dispatcher_worker_id(prefix: str) -> str:
    """Return a process- and instance-unique lease owner identity."""

    return f"{prefix}:{socket.gethostname()}:{os.getpid()}:{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class DispatchResult:
    claimed: int = 0
    published: int = 0
    failed: int = 0
    dead_lettered: int = 0


class OutboxDispatcher:
    """Lease-based SQL outbox dispatcher with recoverable at-least-once delivery."""

    def __init__(
        self,
        session_factory: SessionFactory,
        broker: TaskBroker,
        *,
        worker_id: str,
        lease_seconds: int = 30,
        retry_delay_seconds: int = 2,
        max_retry_delay_seconds: int = 300,
        max_attempts: int = 5,
    ) -> None:
        self._sessions = session_factory
        self._broker = broker
        self._worker_id = worker_id
        self._lease_seconds = max(0.1, float(lease_seconds))
        self._retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self._max_retry_delay_seconds = max(0.0, float(max_retry_delay_seconds))
        self._max_attempts = max(1, max_attempts)

    def dispatch_once(self, *, limit: int = 25) -> DispatchResult:
        claimed_ids = self._claim(limit=max(1, min(limit, 200)))
        published = 0
        failed = 0
        dead_lettered = 0
        for message_id in claimed_ids:
            heartbeat_stop = Event()
            heartbeat = Thread(
                target=self._keep_lease_alive,
                args=(message_id, heartbeat_stop),
                name=f"outbox-lease-{message_id}",
                daemon=True,
            )
            heartbeat.start()
            try:
                with self._sessions() as session:
                    message = session.get(OutboxMessage, message_id)
                    if message is None or message.status != "publishing" or message.lease_owner != self._worker_id:
                        continue
                    envelope = self._envelope(message)
                self._broker.publish(envelope)
            except Exception as exc:
                failed += 1
                if self._mark_failed(message_id, exc) == "dead_letter":
                    dead_lettered += 1
            else:
                if self._mark_published(message_id):
                    published += 1
            finally:
                heartbeat_stop.set()
                heartbeat.join(timeout=max(1.0, self._lease_seconds))
        return DispatchResult(
            claimed=len(claimed_ids),
            published=published,
            failed=failed,
            dead_lettered=dead_lettered,
        )

    def retry_dead_letter(self, message_id: str) -> bool:
        """Return one terminal message to the pending queue after operator repair."""

        with self._sessions() as session, session.begin():
            result = session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.id == message_id,
                    OutboxMessage.status == "dead_letter",
                )
                .values(
                    status="pending",
                    attempt=0,
                    available_at=datetime.now(UTC),
                    lease_owner=None,
                    lease_expires_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1

    def _claim(self, *, limit: int) -> list[str]:
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=self._lease_seconds)
        eligible = or_(
            (OutboxMessage.status == "pending") & (OutboxMessage.available_at <= now),
            (OutboxMessage.status == "publishing")
            & (OutboxMessage.lease_expires_at.is_not(None))
            & (OutboxMessage.lease_expires_at <= now),
        )
        candidate_ids = (
            select(OutboxMessage.id)
            .where(eligible)
            .order_by(OutboxMessage.available_at.asc(), OutboxMessage.created_at.asc(), OutboxMessage.id.asc())
            .limit(limit)
        )
        with self._sessions() as session, session.begin():
            statement = (
                update(OutboxMessage)
                .where(OutboxMessage.id.in_(candidate_ids), eligible)
                .values(
                    status="publishing",
                    lease_owner=self._worker_id,
                    lease_expires_at=lease_expires_at,
                    attempt=OutboxMessage.attempt + 1,
                )
                .returning(OutboxMessage.id)
                .execution_options(synchronize_session=False)
            )
            return list(session.scalars(statement))

    def _keep_lease_alive(self, message_id: str, stop: Event) -> None:
        interval = max(0.05, min(self._lease_seconds / 3, 5.0))
        while not stop.wait(interval):
            if not self._renew_lease(message_id):
                return

    def _renew_lease(self, message_id: str) -> bool:
        with self._sessions() as session, session.begin():
            result = session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.id == message_id,
                    OutboxMessage.status == "publishing",
                    OutboxMessage.lease_owner == self._worker_id,
                )
                .values(lease_expires_at=datetime.now(UTC) + timedelta(seconds=self._lease_seconds))
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1

    def _mark_published(self, message_id: str) -> bool:
        with self._sessions() as session, session.begin():
            result = session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.id == message_id,
                    OutboxMessage.status == "publishing",
                    OutboxMessage.lease_owner == self._worker_id,
                )
                .values(
                    status="published",
                    published_at=datetime.now(UTC),
                    lease_owner=None,
                    lease_expires_at=None,
                    last_error=None,
                )
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1

    def _mark_failed(self, message_id: str, error: Exception) -> str | None:
        with self._sessions() as session, session.begin():
            attempt = session.scalar(
                select(OutboxMessage.attempt).where(
                    OutboxMessage.id == message_id,
                    OutboxMessage.status == "publishing",
                    OutboxMessage.lease_owner == self._worker_id,
                )
            )
            if attempt is None:
                return None
            exhausted = attempt >= self._max_attempts
            values: dict[str, object] = {
                "status": "dead_letter" if exhausted else "pending",
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error": f"{type(error).__name__}: {error}"[:2_000],
            }
            if not exhausted:
                delay = min(
                    self._max_retry_delay_seconds,
                    self._retry_delay_seconds * (2 ** max(0, attempt - 1)),
                )
                values["available_at"] = datetime.now(UTC) + timedelta(seconds=delay)
            result = session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.id == message_id,
                    OutboxMessage.status == "publishing",
                    OutboxMessage.lease_owner == self._worker_id,
                    OutboxMessage.attempt == attempt,
                )
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                return None
            message = session.get(OutboxMessage, message_id)
            if exhausted and message is not None and message.topic == "agent.advance":
                    run = session.get(AgentRun, message.aggregate_id)
                    if run is not None and run.status not in {
                        RunStatus.COMPLETED.value,
                        RunStatus.INSUFFICIENT_EVIDENCE.value,
                        RunStatus.CANCELLED.value,
                        RunStatus.FAILED.value,
                    }:
                        run.status = RunStatus.FAILED.value
                        run.termination_reason = "agent_dispatch_dead_letter"
                        run.version += 1
                        run.finished_at = datetime.now(UTC)
                        SqlAgentJournal(session).append_event(
                            run,
                            event_type="run.failed",
                            payload={
                                "reason": "agent_dispatch_dead_letter",
                                "retryable": True,
                                "outbox_id": message.id,
                                "last_error": str(values["last_error"]),
                            },
                        )
            return str(values["status"])

    @staticmethod
    def _envelope(message: OutboxMessage) -> TaskEnvelope:
        payload = json.loads(message.payload_json or "{}")
        if message.topic == "agent.advance":
            task_id = (
                f"agent:{payload['run_id']}:{int(payload['version'])}:"
                f"{int(payload['execution_epoch'])}"
            )
        else:
            task_id = f"outbox:{message.id}"
        return TaskEnvelope(
            task_id=task_id,
            topic=message.topic,
            payload=payload,
            queue_name=str(payload.get("queue_name") or "default"),
        )
