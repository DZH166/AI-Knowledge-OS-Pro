from __future__ import annotations

import json

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent_event import AgentCheckpoint, AgentCommand, AgentEvent
from app.models.agent_run import AgentRun


def _run(space_id: int, run_id: str = "run-1") -> AgentRun:
    return AgentRun(
        id=run_id,
        space_id=space_id,
        goal="比较两份证据并给出可核验结论",
        requested_mode="auto",
        effective_mode="force_agent",
        status="queued",
        phase="route",
        version=1,
        execution_epoch=0,
        scope_snapshot_json=json.dumps({"revision_ids": [1, 2]}),
        scope_digest="a" * 64,
        deliverable_json='{"kind":"research_report"}',
        policy_snapshot_json='{"read_only":true}',
        budget_limits_json='{"max_steps":8}',
        budget_usage_json='{"steps":0}',
        provider_mode="recording",
    )


def test_agent_command_idempotency_and_event_order_are_database_invariants(
    db_session: Session,
    knowledge_space,
) -> None:
    db_session.add(_run(knowledge_space.id))
    db_session.add(
        AgentCommand(
            id="command-1",
            request_id="request-1",
            run_id="run-1",
            command_type="open_run",
            payload_hash="b" * 64,
            receipt_json='{"run_id":"run-1"}',
        )
    )
    db_session.add_all(
        [
            AgentEvent(
                event_id="event-1",
                run_id="run-1",
                run_sequence=1,
                run_version=1,
                event_type="run.opened",
                payload_json="{}",
                schema_version=1,
                visibility="public",
                trace_id="trace-1",
            ),
            AgentCheckpoint(
                id="checkpoint-1",
                run_id="run-1",
                run_version=1,
                last_event_cursor=0,
                state_schema_version=1,
                checksum="c" * 64,
                state_json='{"phase":"route"}',
                execution_epoch=0,
                scope_digest="a" * 64,
            ),
        ]
    )
    db_session.commit()

    duplicate_request = AgentCommand(
        id="command-2",
        request_id="request-1",
        run_id="run-1",
        command_type="cancel",
        payload_hash="d" * 64,
        receipt_json="{}",
    )
    db_session.add(duplicate_request)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    duplicate_sequence = AgentEvent(
        event_id="event-2",
        run_id="run-1",
        run_sequence=1,
        run_version=1,
        event_type="run.status_changed",
        payload_json="{}",
        schema_version=1,
        visibility="public",
        trace_id="trace-1",
    )
    db_session.add(duplicate_sequence)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_run_version_and_execution_epoch_start_at_safe_values(db_session: Session, knowledge_space) -> None:
    run = _run(knowledge_space.id, "run-safe-defaults")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    assert run.version == 1
    assert run.execution_epoch == 0
    assert run.status == "queued"
    assert run.provider_mode == "recording"
