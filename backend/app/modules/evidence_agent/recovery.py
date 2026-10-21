from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from typing import Callable
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models.agent_event import AgentCheckpoint, AgentEvent
from app.models.agent_run import AgentModelCall, AgentRun, AgentToolCall
from app.models.outbox import OutboxMessage
from app.modules.evidence_agent.contracts import RunStatus
from app.modules.evidence_agent.sql_store import SqlAgentJournal


SessionFactory = Callable[[], Session]


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    scanned: int = 0
    requeued: int = 0
    failed: int = 0
    skipped: int = 0


class AgentInvocationRecovery:
    """Recover external-call crash windows without replaying unknown write effects.

    A prepared invocation has already advanced the run fence and checkpointed a
    ``*.started`` event. Recovery claims that exact version/epoch atomically,
    validates the checkpoint, and then either requeues a known read-only search
    or terminates fail-closed. Model calls are never replayed because a process
    death leaves their provider outcome and cost unknown.
    """

    _ACTIVE_STATUSES = {
        RunStatus.QUEUED.value,
        RunStatus.ROUTING.value,
        RunStatus.PLANNED.value,
        RunStatus.RUNNING.value,
    }

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._utcnow = utcnow or (lambda: datetime.now(UTC))

    def recover_once(
        self,
        *,
        stale_after_seconds: int,
        limit: int = 100,
    ) -> RecoveryResult:
        now = self._utcnow()
        cutoff = now - timedelta(seconds=max(0, stale_after_seconds))
        candidates = self._candidate_run_ids(cutoff=cutoff, limit=max(1, min(limit, 500)))
        requeued = 0
        failed = 0
        skipped = 0
        for run_id in candidates:
            outcome = self._recover_run(run_id, cutoff=cutoff, now=now)
            if outcome == "requeued":
                requeued += 1
            elif outcome == "failed":
                failed += 1
            else:
                skipped += 1
        return RecoveryResult(
            scanned=len(candidates),
            requeued=requeued,
            failed=failed,
            skipped=skipped,
        )

    def _candidate_run_ids(self, *, cutoff: datetime, limit: int) -> list[str]:
        with self._sessions() as session:
            tool_rows = session.execute(
                select(AgentToolCall.run_id, AgentToolCall.started_at, AgentToolCall.created_at)
                .join(AgentRun, AgentRun.id == AgentToolCall.run_id)
                .where(
                    AgentRun.status.in_(self._ACTIVE_STATUSES),
                    AgentToolCall.status == "running",
                    AgentToolCall.execution_epoch == AgentRun.execution_epoch,
                )
                .order_by(AgentToolCall.created_at.asc(), AgentToolCall.id.asc())
                .limit(limit)
            ).all()
            model_rows = session.execute(
                select(AgentModelCall.run_id, AgentModelCall.created_at)
                .join(AgentRun, AgentRun.id == AgentModelCall.run_id)
                .where(
                    AgentRun.status.in_(self._ACTIVE_STATUSES),
                    AgentModelCall.status == "running",
                    AgentModelCall.execution_epoch == AgentRun.execution_epoch,
                )
                .order_by(AgentModelCall.created_at.asc(), AgentModelCall.id.asc())
                .limit(limit)
            ).all()
            expired_claim_rows = session.scalars(
                select(AgentRun.id)
                .where(
                    AgentRun.status.in_(self._ACTIVE_STATUSES),
                    AgentRun.lease_owner.is_not(None),
                    AgentRun.lease_expires_at.is_not(None),
                    AgentRun.lease_expires_at <= self._utcnow(),
                )
                .order_by(AgentRun.lease_expires_at.asc(), AgentRun.id.asc())
                .limit(limit)
            ).all()

        run_ids: list[str] = []
        for run_id, started_at, created_at in tool_rows:
            if self._is_stale(started_at or created_at, cutoff) and run_id not in run_ids:
                run_ids.append(run_id)
        for run_id, created_at in model_rows:
            if self._is_stale(created_at, cutoff) and run_id not in run_ids:
                run_ids.append(run_id)
        for run_id in expired_claim_rows:
            if run_id not in run_ids:
                run_ids.append(run_id)
        return run_ids[:limit]

    def _recover_run(self, run_id: str, *, cutoff: datetime, now: datetime) -> str:
        recovery_owner = f"agent-recovery:{uuid4().hex}"
        with self._sessions() as snapshot_session:
            snapshot = snapshot_session.get(AgentRun, run_id)
            if snapshot is None or snapshot.status not in self._ACTIVE_STATUSES:
                return "skipped"
            old_version = snapshot.version
            old_epoch = snapshot.execution_epoch

        with self._sessions() as session, session.begin():
            claimed = session.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    AgentRun.version == old_version,
                    AgentRun.execution_epoch == old_epoch,
                    AgentRun.status.in_(self._ACTIVE_STATUSES),
                    or_(
                        AgentRun.lease_owner.is_(None),
                        AgentRun.lease_expires_at.is_(None),
                        AgentRun.lease_expires_at <= now,
                    ),
                )
                .values(
                    lease_owner=recovery_owner,
                    lease_expires_at=now + timedelta(seconds=30),
                )
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                return "skipped"

            session.expire_all()
            run = session.get(AgentRun, run_id)
            if run is None:
                return "skipped"
            tool_calls = list(
                session.scalars(
                    select(AgentToolCall).where(
                        AgentToolCall.run_id == run_id,
                        AgentToolCall.status == "running",
                        AgentToolCall.execution_epoch == old_epoch,
                    )
                )
            )
            model_calls = list(
                session.scalars(
                    select(AgentModelCall).where(
                        AgentModelCall.run_id == run_id,
                        AgentModelCall.status == "running",
                        AgentModelCall.execution_epoch == old_epoch,
                    )
                )
            )
            if not tool_calls and not model_calls:
                current_wakeup = session.scalar(
                    select(OutboxMessage).where(
                        OutboxMessage.dedupe_key
                        == (
                            f"agent.advance:{run.id}:{run.version}:"
                            f"{run.execution_epoch}"
                        )
                    )
                )
                if current_wakeup is not None and current_wakeup.status in {
                    "pending",
                    "publishing",
                }:
                    run.lease_owner = None
                    run.lease_expires_at = None
                    return "skipped"

                checkpoint_event = self._validated_checkpoint_event(
                    session,
                    run,
                    expected_version=old_version,
                    expected_epoch=old_epoch,
                )
                run.execution_epoch += 1
                run.lease_owner = None
                run.lease_expires_at = None
                journal = SqlAgentJournal(session)
                if checkpoint_event is not None and checkpoint_event.event_type not in {
                    "model.completed",
                    "model.failed",
                }:
                    event = journal.append_event(
                        run,
                        event_type="run.recovered",
                        payload={
                            "reason": "worker_interrupted_before_external_call",
                            "execution_epoch": run.execution_epoch,
                        },
                    )
                    session.flush()
                    journal.checkpoint(run, event.id)
                    journal.enqueue_advance(run, reason="worker_recovered_safe_checkpoint")
                    return "requeued"

                reason = (
                    "worker_interrupted_after_model_call"
                    if checkpoint_event is not None
                    else "recovery_checkpoint_invalid"
                )
                run.status = RunStatus.FAILED.value
                run.termination_reason = reason
                run.finished_at = now
                run.version += 1
                event = journal.append_event(
                    run,
                    event_type="run.failed",
                    payload={
                        "reason": reason,
                        "error_code": "WORKER_INTERRUPTED_UNKNOWN_OUTCOME",
                    },
                )
                session.flush()
                journal.checkpoint(run, event.id)
                return "failed"
            if any(
                not self._is_stale(call.started_at or call.created_at, cutoff)
                for call in tool_calls
            ) or any(not self._is_stale(call.created_at, cutoff) for call in model_calls):
                run.lease_owner = None
                run.lease_expires_at = None
                return "skipped"

            checkpoint_valid = self._checkpoint_valid(
                session,
                run,
                expected_version=old_version,
                expected_epoch=old_epoch,
                tool_calls=tool_calls,
                model_calls=model_calls,
            )
            run.execution_epoch += 1
            journal = SqlAgentJournal(session)
            for call in tool_calls:
                call.status = "abandoned"
                call.error_code = "worker_interrupted"
                call.finished_at = now
                journal.append_event(
                    run,
                    event_type="tool.abandoned",
                    payload={
                        "tool_call_id": call.id,
                        "reason": "worker_interrupted",
                    },
                    visibility="internal",
                    tool_call_id=call.id,
                )
            for call in model_calls:
                call.status = "abandoned"
                call.error_code = "worker_interrupted_unknown_outcome"
                call.finished_at = now
                journal.append_event(
                    run,
                    event_type="model.abandoned",
                    payload={
                        "model_call_id": call.id,
                        "operation": call.operation,
                        "reason": "worker_interrupted_unknown_outcome",
                    },
                    visibility="internal",
                )

            safe_read_retry = (
                checkpoint_valid
                and not model_calls
                and bool(tool_calls)
                and all(
                    call.effect == "read_evidence"
                    and call.tool_name
                    in {"search_evidence", "open_evidence", "read_neighbors"}
                    for call in tool_calls
                )
            )
            run.lease_owner = None
            run.lease_expires_at = None
            if safe_read_retry:
                event = journal.append_event(
                    run,
                    event_type="run.recovered",
                    payload={
                        "reason": "worker_interrupted_read_only_call",
                        "abandoned_tool_call_ids": [call.id for call in tool_calls],
                        "execution_epoch": run.execution_epoch,
                    },
                )
                session.flush()
                journal.checkpoint(run, event.id)
                journal.enqueue_advance(run, reason="worker_recovered_read_only_call")
                return "requeued"

            reason = (
                "worker_interrupted_during_model_call"
                if model_calls
                else "recovery_checkpoint_invalid"
                if not checkpoint_valid
                else "worker_interrupted_during_non_replayable_tool"
            )
            run.status = RunStatus.FAILED.value
            run.termination_reason = reason
            run.finished_at = now
            run.version += 1
            event = journal.append_event(
                run,
                event_type="run.failed",
                payload={
                    "reason": reason,
                    "error_code": "WORKER_INTERRUPTED_UNKNOWN_OUTCOME",
                },
            )
            session.flush()
            journal.checkpoint(run, event.id)
            return "failed"

    @staticmethod
    def _checkpoint_valid(
        session: Session,
        run: AgentRun,
        *,
        expected_version: int,
        expected_epoch: int,
        tool_calls: list[AgentToolCall],
        model_calls: list[AgentModelCall],
    ) -> bool:
        event = AgentInvocationRecovery._validated_checkpoint_event(
            session,
            run,
            expected_version=expected_version,
            expected_epoch=expected_epoch,
        )
        if event is None:
            return False
        try:
            payload = json.loads(event.payload_json)
        except (TypeError, ValueError):
            return False
        if tool_calls:
            return event.event_type == "tool.started" and payload.get("tool_call_id") in {
                call.id for call in tool_calls
            }
        if model_calls:
            return event.event_type == "model.started" and payload.get("model_call_id") in {
                call.id for call in model_calls
            }
        return False

    @staticmethod
    def _validated_checkpoint_event(
        session: Session,
        run: AgentRun,
        *,
        expected_version: int,
        expected_epoch: int,
    ) -> AgentEvent | None:
        checkpoint = session.scalar(
            select(AgentCheckpoint).where(
                AgentCheckpoint.run_id == run.id,
                AgentCheckpoint.run_version == expected_version,
                AgentCheckpoint.execution_epoch == expected_epoch,
            )
        )
        if checkpoint is None:
            return None
        if sha256(checkpoint.state_json.encode("utf-8")).hexdigest() != checkpoint.checksum:
            return None
        try:
            state = json.loads(checkpoint.state_json)
        except (TypeError, ValueError):
            return None
        if (
            state.get("version") != expected_version
            or state.get("execution_epoch") != expected_epoch
            or state.get("scope_digest") != run.scope_digest
            or state.get("status") != run.status
            or state.get("phase") != run.phase
        ):
            return None
        event = session.get(AgentEvent, checkpoint.last_event_cursor)
        if event is None or event.run_id != run.id:
            return None
        return event

    @staticmethod
    def _is_stale(value: datetime | None, cutoff: datetime) -> bool:
        if value is None:
            return True
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        return value <= cutoff
