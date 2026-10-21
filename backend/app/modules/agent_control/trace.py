from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Mapping

from app.modules.agent_control.contracts import (
    PolicyFact,
    ReplayIntegrity,
    RunTrace,
    TraceEvent,
    TraceModelCall,
    TraceToolCall,
)
from app.modules.agent_control.sanitization import sanitize_fact
from app.modules.agent_control.triage import triage_run_failure


_SAFE_SCALAR_KEYS = {
    "artifact_id",
    "effective",
    "evidence_id",
    "gap_state",
    "method",
    "mode",
    "phase",
    "plan_version",
    "policy_id",
    "policy_version",
    "previous_relation",
    "reason",
    "reason_code",
    "relation",
    "requested",
    "requirement_id",
    "retryable",
    "status",
    "strategy",
    "tool",
}
_TERMINAL_EVENT_STATUS = {
    "run.completed": "completed",
    "run.insufficient_evidence": "insufficient_evidence",
    "run.cancelled": "cancelled",
    "run.failed": "failed",
}


@dataclass(frozen=True, slots=True)
class TraceRunInput:
    id: str
    trace_id: str
    goal: str
    requested_mode: str
    effective_mode: str | None
    status: str
    phase: str
    provider_mode: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    active_elapsed_ms: int
    budget_limits: Mapping[str, int]
    budget_usage: Mapping[str, int]
    decision_policy_id: str | None = None
    decision_policy_version: int | None = None
    decision_policy_fingerprint: str | None = None
    termination_reason: str | None = None
    dispatch_dead_letter: bool = False


@dataclass(frozen=True, slots=True)
class TraceEventInput:
    sequence: int
    run_version: int
    event_type: str
    visibility: str
    payload: Mapping[str, object]
    trace_id: str
    created_at: datetime
    step_id: str | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceToolCallInput:
    id: str
    tool_name: str
    tool_version: str
    effect: str
    status: str
    arguments_digest: str
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class TraceModelCallInput:
    id: str
    operation: str
    provider: str
    model: str
    status: str
    input_tokens: int
    output_tokens: int
    cost_micros: int
    latency_ms: int
    retries: int
    usage_estimated: bool
    error_code: str | None


@dataclass(frozen=True, slots=True)
class TraceCheckpointInput:
    checksum: str
    run_version: int


def project_run_trace(
    run: TraceRunInput,
    *,
    events: tuple[TraceEventInput, ...],
    tool_calls: tuple[TraceToolCallInput, ...] = (),
    model_calls: tuple[TraceModelCallInput, ...] = (),
    checkpoints: tuple[TraceCheckpointInput, ...] = (),
) -> RunTrace:
    ordered_events = tuple(sorted(events, key=lambda item: item.sequence))
    projected_events: list[TraceEvent] = []
    previous_at = _utc(run.created_at)
    policies: dict[tuple[str, str, str, str], PolicyFact] = {}
    if run.decision_policy_id and run.decision_policy_version is not None:
        policy = PolicyFact(
            policy_id=sanitize_fact(run.decision_policy_id),
            version=sanitize_fact(run.decision_policy_version),
            source="run_snapshot",
            config_sha256=sanitize_fact(run.decision_policy_fingerprint) if run.decision_policy_fingerprint else None,
        )
        policies[(policy.policy_id, policy.version, policy.source, policy.config_sha256 or "")] = policy
    replayed_terminal: str | None = None
    digest_rows: list[dict[str, object]] = []

    for event in ordered_events:
        created_at = _utc(event.created_at)
        facts = () if event.visibility != "public" else _safe_facts(event.payload)
        redacted = event.visibility != "public"
        projected_events.append(
            TraceEvent(
                sequence=event.sequence,
                run_version=event.run_version,
                event_type=event.event_type,
                visibility=event.visibility,
                redacted=redacted,
                facts=facts,
                elapsed_ms=max(0, int((created_at - _utc(run.created_at)).total_seconds() * 1_000)),
                delta_ms=max(0, int((created_at - previous_at).total_seconds() * 1_000)),
                step_id=event.step_id,
                tool_call_id=event.tool_call_id,
            )
        )
        previous_at = created_at
        payload_hash = sha256(_canonical_json(event.payload).encode("utf-8")).hexdigest()
        digest_rows.append(
            {
                "sequence": event.sequence,
                "run_version": event.run_version,
                "event_type": event.event_type,
                "visibility": event.visibility,
                "payload_sha256": payload_hash,
                "trace_id": event.trace_id,
            }
        )
        terminal = _terminal_status(event)
        if terminal is not None:
            replayed_terminal = terminal
        if event.visibility == "public":
            for fact in _policy_facts(event):
                policies[(fact.policy_id, fact.version, fact.source, fact.config_sha256 or "")] = fact

    projected_tools = tuple(
        TraceToolCall(
            id=item.id,
            tool_name=item.tool_name,
            tool_version=item.tool_version,
            effect=item.effect,
            status=item.status,
            arguments_digest=item.arguments_digest,
            error_code=item.error_code,
            duration_ms=_duration_ms(item.started_at, item.finished_at),
        )
        for item in tool_calls
    )
    for item in projected_tools:
        fact = PolicyFact(policy_id=f"tool:{item.tool_name}", version=item.tool_version, source="tool_call")
        policies[(fact.policy_id, fact.version, fact.source, fact.config_sha256 or "")] = fact

    projected_models = tuple(
        TraceModelCall(
            id=item.id,
            operation=item.operation,
            provider=item.provider,
            model=item.model,
            status=item.status,
            input_tokens=max(0, item.input_tokens),
            output_tokens=max(0, item.output_tokens),
            cost_micros=max(0, item.cost_micros),
            latency_ms=max(0, item.latency_ms),
            retries=max(0, item.retries),
            usage_estimated=bool(item.usage_estimated),
            error_code=item.error_code,
        )
        for item in model_calls
    )
    terminal_statuses = set(_TERMINAL_EVENT_STATUS.values())
    stored_matches = replayed_terminal == run.status if run.status in terminal_statuses else replayed_terminal is None
    sequences = [item.sequence for item in ordered_events]
    sequence_contiguous = sequences == list(range(1, len(sequences) + 1))
    trace_consistent = all(item.trace_id == run.trace_id for item in ordered_events)
    replay = ReplayIntegrity(
        digest=sha256(_canonical_json(digest_rows).encode("utf-8")).hexdigest(),
        sequence_contiguous=sequence_contiguous,
        trace_id_consistent=trace_consistent,
        stored_terminal_state=run.status,
        replayed_terminal_state=replayed_terminal,
        stored_state_matches=stored_matches,
        event_count=len(ordered_events),
        redacted_event_count=sum(item.visibility != "public" for item in ordered_events),
        checkpoint_count=len(checkpoints),
        latest_checkpoint_checksum=(
            max(checkpoints, key=lambda item: item.run_version).checksum if checkpoints else None
        ),
    )
    tool_errors = tuple(item.error_code for item in projected_tools if item.error_code)
    warnings = tuple(
        warning
        for condition, warning in (
            (not sequence_contiguous, "event_sequence_not_contiguous"),
            (not trace_consistent, "trace_id_mismatch"),
            (not stored_matches, "replayed_terminal_state_mismatch"),
        )
        if condition
    )
    return RunTrace(
        run_id=run.id,
        trace_id=run.trace_id,
        goal=sanitize_fact(run.goal, maximum_length=500),
        requested_mode=run.requested_mode,
        effective_mode=run.effective_mode,
        status=run.status,
        phase=run.phase,
        provider_mode=run.provider_mode,
        created_at=_utc(run.created_at),
        started_at=_utc(run.started_at) if run.started_at else None,
        finished_at=_utc(run.finished_at) if run.finished_at else None,
        active_elapsed_ms=max(0, run.active_elapsed_ms),
        budget_limits={key: max(0, int(value)) for key, value in run.budget_limits.items()},
        budget_usage={key: max(0, int(value)) for key, value in run.budget_usage.items()},
        events=tuple(projected_events),
        tool_calls=projected_tools,
        model_calls=projected_models,
        policies=tuple(sorted(policies.values(), key=lambda item: (item.policy_id, item.version, item.source))),
        replay=replay,
        triage=triage_run_failure(
            status=run.status,
            termination_reason=run.termination_reason,
            tool_error_codes=tool_errors,
            dispatch_dead_letter=run.dispatch_dead_letter,
        ),
        warnings=warnings,
    )


def _safe_facts(payload: Mapping[str, object]) -> tuple[str, ...]:
    facts: list[str] = []
    for key in sorted(_SAFE_SCALAR_KEYS):
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)):
            facts.append(f"{key}={_bounded(value)}")
    selection = payload.get("selection")
    if isinstance(selection, Mapping):
        for key in ("policy_id", "policy_version", "gap_state", "reason_code", "tool"):
            value = selection.get(key)
            if isinstance(value, (str, int, float, bool)):
                facts.append(f"selection.{key}={_bounded(value)}")
    retrieval_policy = payload.get("retrieval_policy")
    if isinstance(retrieval_policy, Mapping):
        for key in (
            "policy_id",
            "policy_version",
            "reason_code",
            "top_k",
            "minimum_score_millis",
            "max_hits_per_source",
            "before",
            "after",
        ):
            value = retrieval_policy.get(key)
            if isinstance(value, (str, int, float, bool)):
                facts.append(f"retrieval_policy.{key}={_bounded(value)}")
    return tuple(facts)


def _policy_facts(event: TraceEventInput) -> tuple[PolicyFact, ...]:
    facts: list[PolicyFact] = []
    selection = event.payload.get("selection")
    if isinstance(selection, Mapping) and selection.get("policy_id") and selection.get("policy_version") is not None:
        facts.append(
            PolicyFact(
                policy_id=sanitize_fact(selection["policy_id"]),
                version=sanitize_fact(selection["policy_version"]),
                source=event.event_type,
            )
        )
    if event.event_type == "plan.created" and event.payload.get("plan_version") is not None:
        facts.append(
            PolicyFact(
                policy_id="plan",
                version=sanitize_fact(event.payload["plan_version"]),
                source=event.event_type,
            )
        )
    retrieval_policy = event.payload.get("retrieval_policy")
    if (
        isinstance(retrieval_policy, Mapping)
        and retrieval_policy.get("policy_id")
        and retrieval_policy.get("policy_version") is not None
    ):
        facts.append(
            PolicyFact(
                policy_id=sanitize_fact(retrieval_policy["policy_id"]),
                version=sanitize_fact(retrieval_policy["policy_version"]),
                source=event.event_type,
            )
        )
    return tuple(facts)


def _terminal_status(event: TraceEventInput) -> str | None:
    direct = _TERMINAL_EVENT_STATUS.get(event.event_type)
    if direct is not None:
        return direct
    if event.event_type == "run.status_changed":
        status = event.payload.get("status")
        return str(status) if status in set(_TERMINAL_EVENT_STATUS.values()) else None
    return None


def _duration_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
    if started_at is None or finished_at is None:
        return None
    return max(0, int((_utc(finished_at) - _utc(started_at)).total_seconds() * 1_000))


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _bounded(value: object) -> str:
    return sanitize_fact(value)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
