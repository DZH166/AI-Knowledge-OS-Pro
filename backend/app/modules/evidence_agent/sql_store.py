from __future__ import annotations

from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_event import AgentCheckpoint, AgentEvent
from app.models.agent_run import AgentRun
from app.models.outbox import OutboxMessage


class SqlAgentJournal:
    """Transaction-local event, checkpoint and wake-up writer."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def append_event(
        self,
        run: AgentRun,
        *,
        event_type: str,
        payload: dict[str, object],
        visibility: str = "public",
        step_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> AgentEvent:
        persisted_sequence = self.session.scalar(
            select(func.max(AgentEvent.run_sequence)).where(AgentEvent.run_id == run.id)
        ) or 0
        pending_sequence = max(
            (
                item.run_sequence
                for item in self.session.new
                if isinstance(item, AgentEvent) and item.run_id == run.id
            ),
            default=0,
        )
        sequence = max(persisted_sequence, pending_sequence)
        event = AgentEvent(
            event_id=str(uuid4()),
            run_id=run.id,
            run_sequence=sequence + 1,
            run_version=run.version,
            event_type=event_type,
            payload_json=canonical_json(payload),
            schema_version=1,
            visibility=visibility,
            step_id=step_id,
            tool_call_id=tool_call_id,
            trace_id=run.trace_id,
        )
        self.session.add(event)
        return event

    def checkpoint(self, run: AgentRun, event_cursor: int) -> AgentCheckpoint:
        state = {
            "status": run.status,
            "phase": run.phase,
            "version": run.version,
            "execution_epoch": run.execution_epoch,
            "scope_digest": run.scope_digest,
            "current_plan_version": run.current_plan_version,
            "pending_gate_id": run.pending_gate_id,
        }
        state_json = canonical_json(state)
        checkpoint = self.session.scalar(
            select(AgentCheckpoint).where(
                AgentCheckpoint.run_id == run.id,
                AgentCheckpoint.run_version == run.version,
            )
        )
        if checkpoint is not None:
            checkpoint.last_event_cursor = max(checkpoint.last_event_cursor, event_cursor)
            checkpoint.state_schema_version = 1
            checkpoint.checksum = sha256(state_json.encode("utf-8")).hexdigest()
            checkpoint.state_json = state_json
            checkpoint.execution_epoch = run.execution_epoch
            checkpoint.scope_digest = run.scope_digest
            return checkpoint

        checkpoint = AgentCheckpoint(
            id=str(uuid4()),
            run_id=run.id,
            run_version=run.version,
            last_event_cursor=event_cursor,
            state_schema_version=1,
            checksum=sha256(state_json.encode("utf-8")).hexdigest(),
            state_json=state_json,
            execution_epoch=run.execution_epoch,
            scope_digest=run.scope_digest,
        )
        self.session.add(checkpoint)
        return checkpoint

    def enqueue_advance(self, run: AgentRun, *, reason: str) -> OutboxMessage:
        # Hand the run lease to the next durable slice in the same transaction
        # that makes its wake-up visible.  A dispatcher can otherwise publish
        # version N+1 while the version N call is still unwinding, causing the
        # next worker to consume its only wake-up against the old lease.
        run.lease_owner = None
        run.lease_expires_at = None
        message = OutboxMessage(
            id=str(uuid4()),
            topic="agent.advance",
            aggregate_type="agent_run",
            aggregate_id=run.id,
            dedupe_key=f"agent.advance:{run.id}:{run.version}:{run.execution_epoch}",
            payload_json=canonical_json(
                {
                    "run_id": run.id,
                    "version": run.version,
                    "execution_epoch": run.execution_epoch,
                    "reason": reason,
                }
            ),
            status="pending",
        )
        self.session.add(message)
        return message


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
