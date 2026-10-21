from __future__ import annotations

import json
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_event import AgentEvent
from app.models.agent_run import AgentToolCall
from app.modules.agent_policy.simulation import RecordedPolicyDecision


_REQUIREMENT_KINDS = {"factual", "comparative", "temporal"}


def load_recorded_policy_decisions(session: Session, run_id: str) -> tuple[RecordedPolicyDecision, ...]:
    rows = session.execute(
        select(AgentEvent.run_sequence, AgentEvent.payload_json)
        .join(AgentToolCall, AgentToolCall.id == AgentEvent.tool_call_id)
        .where(
            AgentEvent.run_id == run_id,
            AgentEvent.event_type == "tool.started",
            AgentEvent.visibility == "public",
            AgentToolCall.status == "completed",
        )
        .order_by(AgentEvent.run_sequence.asc())
    ).all()
    recorded: list[RecordedPolicyDecision] = []
    for _run_sequence, payload_json in rows:
        payload = _mapping(payload_json, "Persisted public policy event")
        policy = payload.get("retrieval_policy")
        tool = payload.get("tool")
        if not isinstance(policy, Mapping) or tool not in {"search_evidence", "read_neighbors"}:
            continue
        sequence = len(recorded) + 1
        if tool == "search_evidence":
            reason = policy.get("reason_code")
            kind = reason.removeprefix("requirement_kind:") if isinstance(reason, str) else ""
            top_k = policy.get("top_k")
            if kind not in _REQUIREMENT_KINDS or type(top_k) is not int or top_k <= 0:
                _unavailable("Persisted public search decision is invalid.")
            recorded.append(
                RecordedPolicyDecision(
                    sequence=sequence,
                    tool="search_evidence",
                    requirement_kind=kind,
                    top_k=top_k,
                )
            )
            continue
        before = policy.get("before")
        after = policy.get("after")
        if type(before) is not int or type(after) is not int or before < 0 or after < 0:
            _unavailable("Persisted public neighbor decision is invalid.")
        recorded.append(
            RecordedPolicyDecision(
                sequence=sequence,
                tool="read_neighbors",
                before=before,
                after=after,
            )
        )
    return tuple(recorded)


def _mapping(payload_json: str, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError as exc:
        raise ServiceError(
            code="POLICY_SIMULATION_UNAVAILABLE",
            message=f"{label} is not valid JSON.",
            status_code=409,
        ) from exc
    if not isinstance(payload, Mapping):
        _unavailable(f"{label} is not an object.")
    return payload


def _unavailable(message: str) -> None:
    raise ServiceError(
        code="POLICY_SIMULATION_UNAVAILABLE",
        message=message,
        status_code=409,
    )
