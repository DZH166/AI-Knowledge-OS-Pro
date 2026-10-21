from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import time
from typing import Callable
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_event import AgentCommand, AgentEvent
from app.models.agent_evidence import AgentArtifact, AgentClaim, AgentEvidence, ClaimEvidence
from app.models.agent_run import AgentGate, AgentModelCall, AgentRequirement, AgentRun, AgentToolCall
from app.models.source import IndexRevision, Source, SourceRevision
from app.modules.agent_policy.config import (
    canonical_policy_json,
    policy_fingerprint,
)
from app.modules.agent_policy.contracts import PolicyDetail, PolicyStatus
from app.modules.evidence_agent.contracts import (
    GetRun,
    GetArtifact,
    GetEvidence,
    ArtifactClaimView,
    ArtifactView,
    EvidenceView,
    ListRuns,
    ListArtifacts,
    RunCatalog,
    ArtifactCatalog,
    ArtifactSummary,
    BudgetLimits,
    ContinueRun,
    DeliverableSpec,
    DecisionPolicyView,
    OpenRun,
    PermissionPolicy,
    RunFrame,
    RunMode,
    RunOrigin,
    RunPhase,
    RunStatus,
    RunView,
    ScopeSnapshot,
    ScopeSelector,
    ScopedRevision,
    SignalKind,
    SignalRun,
    Submission,
)
from app.modules.evidence_agent.state_machine import InvalidRunTransition, RunSignal, transition_run
from app.modules.evidence_agent.policy_snapshot import PinnedDecisionPolicy
from app.modules.evidence_agent.sql_store import SqlAgentJournal
from app.modules.evidence_agent.tools import (
    ToolIntent,
    ToolRegistry,
    artifact_content_digest,
)


SessionFactory = Callable[[], Session]
ActivePolicyPort = Callable[[], PolicyDetail]


class SqlEvidenceAgent:
    """Transactional command/query/event implementation of the EvidenceAgent seam."""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        follow_poll_seconds: float = 0.1,
        heartbeat_interval_seconds: float = 15.0,
        follow_clock: Callable[[], float] = time.monotonic,
        active_policy: ActivePolicyPort | None = None,
    ) -> None:
        if follow_poll_seconds < 0:
            raise ValueError("follow_poll_seconds cannot be negative.")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive.")
        self._sessions = session_factory
        self._follow_poll_seconds = follow_poll_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._follow_clock = follow_clock
        self._active_policy = active_policy

    def submit(self, command: OpenRun | ContinueRun | SignalRun) -> Submission:
        if isinstance(command, (OpenRun, ContinueRun)):
            return self._open(command)
        return self._signal(command)

    def inspect(self, query):
        with self._sessions() as session:
            if isinstance(query, GetRun):
                run = session.get(AgentRun, query.run_id)
                if run is None:
                    raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
                cursor = self._public_cursor(session, run.id)
                return self._view(run, cursor)
            if isinstance(query, GetArtifact):
                return self._artifact_view(session, query.artifact_id)
            if isinstance(query, GetEvidence):
                return self._evidence_view(session, query.evidence_id)
            if isinstance(query, ListRuns):
                statement = select(AgentRun).order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                if query.space_id is not None:
                    statement = statement.where(AgentRun.space_id == query.space_id)
                if query.status is not None:
                    statement = statement.where(AgentRun.status == query.status.value)
                runs = session.scalars(statement.limit(max(1, min(query.limit, 100)))).all()
                items = []
                for run in runs:
                    cursor = self._public_cursor(session, run.id)
                    items.append(self._view(run, cursor))
                return RunCatalog(items=tuple(items))
            if isinstance(query, ListArtifacts):
                statement = select(AgentArtifact).join(
                    AgentRun, AgentRun.id == AgentArtifact.producing_run_id
                ).order_by(AgentArtifact.created_at.desc(), AgentArtifact.id.desc())
                if query.space_id is not None:
                    statement = statement.where(AgentRun.space_id == query.space_id)
                if query.source_id is not None:
                    statement = (
                        statement.join(
                            AgentClaim,
                            AgentClaim.artifact_id == AgentArtifact.id,
                        )
                        .join(
                            ClaimEvidence,
                            ClaimEvidence.claim_id == AgentClaim.id,
                        )
                        .join(
                            AgentEvidence,
                            AgentEvidence.id == ClaimEvidence.evidence_id,
                        )
                        .where(AgentEvidence.source_id == query.source_id)
                        .distinct()
                    )
                if query.run_id is not None:
                    statement = statement.where(AgentArtifact.producing_run_id == query.run_id)
                artifacts = session.scalars(statement.limit(max(1, min(query.limit, 100)))).all()
                return ArtifactCatalog(
                    items=tuple(
                        ArtifactSummary(
                            id=item.id,
                            producing_run_id=item.producing_run_id,
                            kind=item.kind,
                            title=item.title,
                            status=item.status,
                        )
                        for item in artifacts
                    )
                )
            raise TypeError(f"Unsupported Agent query: {type(query).__name__}")

    async def follow(self, run_id: str, cursor: int | None = None):
        next_cursor = int(cursor or 0)
        if not self._valid_public_cursor(run_id, cursor):
            snapshot = self.inspect(GetRun(run_id))
            next_cursor = 0
            yield RunFrame(
                cursor=0,
                event_type="sync",
                run_version=snapshot.version,
                payload={"run": self._run_view_payload(snapshot)},
            )
        last_emit_at = self._follow_clock()

        terminal = {
            RunStatus.COMPLETED.value,
            RunStatus.INSUFFICIENT_EVIDENCE.value,
            RunStatus.CANCELLED.value,
            RunStatus.FAILED.value,
        }
        while True:
            with self._sessions() as session:
                run = session.get(AgentRun, run_id)
                if run is None:
                    raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
                events = session.scalars(
                    select(AgentEvent)
                    .where(
                        AgentEvent.run_id == run_id,
                        AgentEvent.id > int(next_cursor or 0),
                        AgentEvent.visibility == "public",
                    )
                    .order_by(AgentEvent.id.asc())
                    .limit(200)
                ).all()
                current_status = run.status
                current_version = run.version
            if events:
                for event in events:
                    next_cursor = event.id
                    last_emit_at = self._follow_clock()
                    yield RunFrame(
                        cursor=event.id,
                        event_type=event.event_type,
                        run_version=event.run_version,
                        payload=json.loads(event.payload_json or "{}"),
                        schema_version=event.schema_version,
                    )
                continue
            if current_status in terminal:
                return
            now = self._follow_clock()
            if now - last_emit_at >= self._heartbeat_interval_seconds:
                last_emit_at = now
                yield RunFrame(
                    cursor=next_cursor,
                    event_type="heartbeat",
                    run_version=current_version,
                    payload={},
                )
                continue
            await asyncio.sleep(self._follow_poll_seconds)

    def _valid_public_cursor(self, run_id: str, cursor: int | None) -> bool:
        if cursor is None or cursor < 0:
            return False
        if cursor == 0:
            with self._sessions() as session:
                if session.get(AgentRun, run_id) is None:
                    raise ServiceError(
                        code="RUN_NOT_FOUND",
                        message="Agent run not found.",
                        status_code=404,
                    )
            return True
        with self._sessions() as session:
            if session.get(AgentRun, run_id) is None:
                raise ServiceError(
                    code="RUN_NOT_FOUND",
                    message="Agent run not found.",
                    status_code=404,
                )
            return session.scalar(
                select(AgentEvent.id).where(
                    AgentEvent.run_id == run_id,
                    AgentEvent.id == cursor,
                    AgentEvent.visibility == "public",
                )
            ) is not None

    def _open(self, command: OpenRun | ContinueRun) -> Submission:
        if isinstance(command, OpenRun) and not command.goal.strip():
            raise ServiceError(code="INVALID_GOAL", message="Run goal cannot be empty.", status_code=422)
        payload_hash = self._payload_hash(command)
        with self._sessions() as replay_session:
            replay = self._replay_or_conflict(replay_session, command.request_id, payload_hash)
            if replay is not None:
                return replay
        initial_policy = (
            self._load_active_policy()
            if isinstance(command, OpenRun) and self._active_policy is not None
            else None
        )
        try:
            with self._sessions() as session, session.begin():
                replay = self._replay_or_conflict(session, command.request_id, payload_hash)
                if replay is not None:
                    return replay

                open_command, snapshot, origin, decision_policy = self._materialize_open(
                    session,
                    command,
                    initial_policy=initial_policy,
                )
                run_id = str(uuid4())
                command_id = str(uuid4())
                trace_id = uuid4().hex
                scope_payload = self._scope_payload(snapshot)
                scope_json = self._canonical_json(scope_payload)
                scope_digest = hashlib.sha256(scope_json.encode("utf-8")).hexdigest()
                run = AgentRun(
                    id=run_id,
                    space_id=open_command.space_id,
                    goal=open_command.goal.strip(),
                    requested_mode=open_command.mode.value,
                    effective_mode=None,
                    status=RunStatus.QUEUED.value,
                    phase=RunPhase.ROUTE.value,
                    version=1,
                    execution_epoch=0,
                    scope_snapshot_json=scope_json,
                    scope_digest=scope_digest,
                    deliverable_json=self._canonical_json(
                        self._deliverable_payload(open_command.deliverable, origin)
                    ),
                    policy_snapshot_json=self._canonical_json(asdict(open_command.permissions)),
                    decision_policy_id=decision_policy.id if decision_policy else None,
                    decision_policy_version=decision_policy.version if decision_policy else None,
                    decision_policy_fingerprint=(decision_policy.config_sha256 if decision_policy else None),
                    decision_policy_snapshot_json=(decision_policy.config_json if decision_policy else None),
                    budget_limits_json=self._canonical_json(asdict(open_command.budget)),
                    budget_usage_json=self._canonical_json(self._empty_usage()),
                    provider_mode=open_command.provider_mode,
                    trace_id=trace_id,
                )
                session.add(run)
                # Agent runtime rows use scalar foreign keys without ORM relationships,
                # so persist the parent before journal rows are flushed in this transaction.
                session.flush([run])
                event = self._append_event(
                    session,
                    run,
                    event_type="run.opened",
                    payload={
                        "goal": run.goal,
                        "requested_mode": run.requested_mode,
                        "provider_mode": run.provider_mode,
                        "scope": scope_payload,
                        "origin": asdict(origin),
                        "decision_policy": self._policy_payload(decision_policy),
                    },
                )
                session.flush()
                self._write_checkpoint(session, run, event.id)
                self._enqueue_advance(session, run, reason="opened")
                receipt = Submission(
                    command_id=command_id,
                    run_id=run.id,
                    run_version=run.version,
                    status=RunStatus(run.status),
                    cursor=event.id,
                )
                session.add(
                    AgentCommand(
                        id=command_id,
                        request_id=command.request_id,
                        run_id=run.id,
                        command_type=(
                            "continue_run" if isinstance(command, ContinueRun) else "open_run"
                        ),
                        payload_hash=payload_hash,
                        receipt_json=self._receipt_json(receipt),
                    )
                )
                return receipt
        except IntegrityError as exc:
            if not self._is_request_id_integrity_conflict(exc):
                raise
            with self._sessions() as session:
                replay = self._replay_or_conflict(
                    session,
                    command.request_id,
                    payload_hash,
                )
                if replay is not None:
                    return replay
            raise ServiceError(
                code="IDEMPOTENCY_RESULT_PENDING",
                message="The concurrent idempotent request has not become visible yet.",
                status_code=503,
                retryable=True,
            ) from exc

    def _signal(self, command: SignalRun) -> Submission:
        payload_hash = self._payload_hash(command)
        # Keep SQLite's mutation transaction free of a preceding read snapshot so
        # the version compare-and-swap can serialize concurrent commands instead
        # of surfacing SQLITE_BUSY_SNAPSHOT during a read-to-write upgrade.
        with self._sessions() as replay_session:
            replay = self._replay_or_conflict(
                replay_session,
                command.request_id,
                payload_hash,
            )
            if replay is not None:
                return replay

        with self._sessions() as session, session.begin():
            claimed = session.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == command.run_id,
                    AgentRun.version == command.expected_version,
                )
                .values(version=AgentRun.version + 1)
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                replay = self._replay_or_conflict(session, command.request_id, payload_hash)
                if replay is not None:
                    return replay
                actual_version = session.scalar(
                    select(AgentRun.version).where(AgentRun.id == command.run_id)
                )
                if actual_version is None:
                    raise ServiceError(
                        code="RUN_NOT_FOUND",
                        message="Agent run not found.",
                        status_code=404,
                    )
                raise ServiceError(
                    code="STALE_RUN_VERSION",
                    message="The run changed before this command was applied.",
                    status_code=409,
                    details={
                        "expected": command.expected_version,
                        "actual": actual_version,
                    },
                )

            run = session.get(AgentRun, command.run_id)
            if run is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)

            pending_gate = session.get(AgentGate, run.pending_gate_id) if run.pending_gate_id else None
            gate = None
            proposed_tool_call: AgentToolCall | None = None
            clarification: tuple[AgentRequirement, str] | None = None
            modified_title: str | None = None
            replacement_gate: AgentGate | None = None
            if command.signal in {
                SignalKind.PROVIDE_INPUT,
                SignalKind.APPROVE,
                SignalKind.REJECT,
                SignalKind.MODIFY,
            }:
                gate = pending_gate
                if gate is None or gate.status != "open":
                    raise ServiceError(
                        code="NO_PENDING_GATE",
                        message="This run has no matching open human decision.",
                        status_code=409,
                    )
                if command.signal is SignalKind.PROVIDE_INPUT and gate.kind != "clarification":
                    raise ServiceError(
                        code="GATE_KIND_MISMATCH",
                        message="The pending decision requires approval rather than clarification.",
                        status_code=409,
                    )
                if command.signal in {
                    SignalKind.APPROVE,
                    SignalKind.REJECT,
                    SignalKind.MODIFY,
                } and gate.kind == "clarification":
                    raise ServiceError(
                        code="GATE_KIND_MISMATCH",
                        message="The pending decision requires clarification input.",
                        status_code=409,
                    )
                if command.signal is SignalKind.PROVIDE_INPUT:
                    clarification = self._clarification_target(
                        session,
                        run,
                        gate,
                        command.response,
                    )
                if (
                    command.signal in {SignalKind.APPROVE, SignalKind.MODIFY}
                    and gate.arguments_digest
                    and gate.arguments_digest != command.proposal_digest
                ):
                    raise ServiceError(
                        code="STALE_APPROVAL",
                        message="The approved proposal no longer matches the pending protected action.",
                        status_code=409,
                        details={"gate_id": gate.id},
                    )
                if gate.proposed_tool_call_id is not None:
                    proposed_tool_call = session.get(
                        AgentToolCall,
                        gate.proposed_tool_call_id,
                    )
                    if (
                        proposed_tool_call is None
                        or proposed_tool_call.run_id != run.id
                        or proposed_tool_call.status != "awaiting_approval"
                        or proposed_tool_call.arguments_digest != gate.arguments_digest
                    ):
                        raise ServiceError(
                            code="PROPOSAL_STATE_CONFLICT",
                            message="The protected proposal is missing or no longer pending.",
                            status_code=409,
                            details={"gate_id": gate.id},
                        )
                if command.signal is SignalKind.MODIFY:
                    modified_title = self._modified_artifact_title(command.response)
                    if proposed_tool_call is None:
                        raise ServiceError(
                            code="MODIFICATION_NOT_SUPPORTED",
                            message="Only a pending Artifact publication can be modified.",
                            status_code=409,
                        )

            signal = self._to_state_signal(command.signal)
            try:
                next_status = transition_run(RunStatus(run.status), signal)
            except InvalidRunTransition as exc:
                raise ServiceError(
                    code="INVALID_RUN_TRANSITION",
                    message=str(exc),
                    status_code=409,
                ) from exc

            run.status = next_status.value
            if clarification is not None:
                target, clarification_text = clarification
                target.text = self._clarified_query(target.text, clarification_text)
                target.status = "uncovered"
                run.phase = RunPhase.RETRIEVE.value
            if gate is not None:
                gate.status = {
                    SignalKind.PROVIDE_INPUT: "resolved",
                    SignalKind.APPROVE: "approved",
                    SignalKind.REJECT: "rejected",
                    SignalKind.MODIFY: "modified",
                }[command.signal]
                gate.response_json = self._canonical_json(
                    {"text": clarification[1]}
                    if clarification is not None
                    else dict(command.response)
                )
                gate.resolved_at = datetime.now(UTC)
                gate.resolved_by = "user"
                run.pending_gate_id = None
                if proposed_tool_call is not None:
                    if command.signal is SignalKind.APPROVE:
                        proposed_tool_call.status = "approved"
                    elif command.signal is SignalKind.MODIFY:
                        if modified_title is None:
                            raise AssertionError("Modify signal has no validated title.")
                        replacement_gate = self._replace_artifact_publication_proposal(
                            session,
                            run,
                            gate,
                            proposed_tool_call,
                            title=modified_title,
                        )
                        run.pending_gate_id = replacement_gate.id
                    elif command.signal is SignalKind.REJECT:
                        proposed_tool_call.status = "rejected"
                        proposed_tool_call.error_code = "approval_rejected"
                        proposed_tool_call.finished_at = datetime.now(UTC)
                        proposal_arguments = json.loads(proposed_tool_call.arguments_json)
                        artifact_id = proposal_arguments.get("artifact_id")
                        artifact = (
                            session.get(AgentArtifact, str(artifact_id))
                            if artifact_id is not None
                            else None
                        )
                        if (
                            artifact is not None
                            and artifact.producing_run_id == run.id
                            and artifact.status == "draft"
                        ):
                            artifact.status = "rejected"
            if command.signal in {SignalKind.CANCEL, SignalKind.PAUSE}:
                run.execution_epoch += 1
                now = datetime.now(UTC)
                for tool_call in session.scalars(
                    select(AgentToolCall).where(
                        AgentToolCall.run_id == run.id,
                        AgentToolCall.status == "running",
                    )
                ):
                    tool_call.status = "abandoned"
                    tool_call.finished_at = now
                    tool_call.error_code = command.signal.value
                for model_call in session.scalars(
                    select(AgentModelCall).where(
                        AgentModelCall.run_id == run.id,
                        AgentModelCall.status == "running",
                    )
                ):
                    model_call.status = "abandoned"
                    model_call.finished_at = now
                    model_call.error_code = command.signal.value
            if next_status in {
                RunStatus.COMPLETED,
                RunStatus.INSUFFICIENT_EVIDENCE,
                RunStatus.CANCELLED,
                RunStatus.FAILED,
            }:
                run.finished_at = datetime.now(UTC)
                run.lease_owner = None
                run.lease_expires_at = None
            if command.signal is SignalKind.REJECT:
                run.termination_reason = "approval_rejected"
            if command.signal is SignalKind.CANCEL and pending_gate is not None:
                if pending_gate.status == "open":
                    pending_gate.status = "cancelled"
                    pending_gate.resolved_at = datetime.now(UTC)
                    pending_gate.resolved_by = "user"
                run.pending_gate_id = None
                if pending_gate.proposed_tool_call_id is not None:
                    cancelled_proposal = session.get(
                        AgentToolCall,
                        pending_gate.proposed_tool_call_id,
                    )
                    if cancelled_proposal is not None and cancelled_proposal.status in {
                        "awaiting_approval",
                        "approved",
                    }:
                        cancelled_proposal.status = "cancelled"
                        cancelled_proposal.error_code = "cancelled"
                        cancelled_proposal.finished_at = datetime.now(UTC)
            if clarification is not None and gate is not None:
                self._append_event(
                    session,
                    run,
                    event_type="interaction.resolved",
                    payload={
                        "gate_id": gate.id,
                        "kind": "clarification",
                        "target_requirement_id": clarification[0].id,
                        "response": {"text": clarification[1]},
                    },
                )
            elif gate is not None:
                self._append_event(
                    session,
                    run,
                    event_type="interaction.resolved",
                    payload={
                        "gate_id": gate.id,
                        "kind": "approval",
                        "decision": command.signal.value,
                        "proposal_digest": gate.arguments_digest,
                    },
                )
                if replacement_gate is not None:
                    self._append_event(
                        session,
                        run,
                        event_type="interaction.required",
                        payload={
                            "gate_id": replacement_gate.id,
                            "kind": "approval",
                            "summary": "发布修改标题后的逐 claim 引用研究成果",
                            "target": self._proposal_target(
                                session,
                                replacement_gate,
                            ),
                            "risk_class": "write",
                            "proposal_digest": replacement_gate.arguments_digest,
                        },
                    )
            event = self._append_event(
                session,
                run,
                event_type=f"run.{next_status.value}",
                payload={"signal": command.signal.value, "response": dict(command.response)},
            )
            session.flush()
            self._write_checkpoint(session, run, event.id)
            if next_status is RunStatus.QUEUED:
                self._enqueue_advance(session, run, reason=command.signal.value)

            receipt = Submission(
                command_id=str(uuid4()),
                run_id=run.id,
                run_version=run.version,
                status=next_status,
                cursor=event.id,
            )
            session.add(
                AgentCommand(
                    id=receipt.command_id,
                    request_id=command.request_id,
                    run_id=run.id,
                    command_type=command.signal.value,
                    payload_hash=payload_hash,
                    receipt_json=self._receipt_json(receipt),
                )
            )
            return receipt

    def _clarification_target(
        self,
        session: Session,
        run: AgentRun,
        gate: AgentGate,
        response: object,
    ) -> tuple[AgentRequirement, str]:
        if not isinstance(response, Mapping):
            raise ServiceError(
                code="INVALID_CLARIFICATION_RESPONSE",
                message="Clarification input must be an object containing non-empty text.",
                status_code=422,
            )
        text = response.get("text")
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > 500:
            raise ServiceError(
                code="INVALID_CLARIFICATION_RESPONSE",
                message="Clarification text must contain between 1 and 500 characters.",
                status_code=422,
            )
        try:
            response_schema = json.loads(gate.response_schema_json or "{}")
        except json.JSONDecodeError as exc:
            raise ServiceError(
                code="CLARIFICATION_GATE_INVALID",
                message="The pending clarification target is invalid.",
                status_code=409,
            ) from exc
        metadata = response_schema.get("x-evidence-agent")
        requirement_id = metadata.get("target_requirement_id") if isinstance(metadata, dict) else None
        if not isinstance(requirement_id, str) or not requirement_id:
            raise ServiceError(
                code="CLARIFICATION_GATE_INVALID",
                message="The pending clarification target is invalid.",
                status_code=409,
            )
        requirement = session.scalar(
            select(AgentRequirement).where(
                AgentRequirement.id == requirement_id,
                AgentRequirement.run_id == run.id,
            )
        )
        if requirement is None:
            raise ServiceError(
                code="CLARIFICATION_TARGET_NOT_FOUND",
                message="The target requirement no longer exists in this run.",
                status_code=409,
            )
        return requirement, text.strip()

    @staticmethod
    def _clarified_query(previous_query: str, clarification: str) -> str:
        candidate = f"{previous_query.strip()} {clarification.strip()}".strip()
        if len(candidate) <= 500:
            return candidate
        previous_budget = max(0, 499 - len(clarification))
        previous = previous_query.strip()[:previous_budget].rstrip()
        return f"{previous} {clarification}".strip()[-500:]

    def _materialize_open(
        self,
        session: Session,
        command: OpenRun | ContinueRun,
        *,
        initial_policy: PinnedDecisionPolicy | None,
    ) -> tuple[OpenRun, ScopeSnapshot, RunOrigin, PinnedDecisionPolicy | None]:
        if isinstance(command, OpenRun):
            return command, self._resolve_scope(session, command), RunOrigin(), initial_policy

        parent = session.get(AgentRun, command.source_run_id)
        if parent is None:
            raise ServiceError(
                code="CONTINUATION_SOURCE_NOT_FOUND",
                message="The source Agent run was not found.",
                status_code=404,
            )
        if parent.status != RunStatus.INSUFFICIENT_EVIDENCE.value:
            raise ServiceError(
                code="CONTINUATION_SOURCE_NOT_GAP",
                message="Only an insufficient-evidence run can be continued.",
                status_code=409,
            )
        artifact = session.get(AgentArtifact, command.gap_artifact_id)
        if (
            artifact is None
            or artifact.id != parent.final_artifact_id
            or artifact.producing_run_id != parent.id
            or artifact.kind != "evidence_gap_report"
            or artifact.status != "final"
        ):
            raise ServiceError(
                code="CONTINUATION_GAP_MISMATCH",
                message="The continuation must reference the source run's final Evidence Gap Report.",
                status_code=409,
            )
        try:
            gap_payload = json.loads(artifact.structured_payload_json)
            gaps = gap_payload["gaps"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ServiceError(
                code="CONTINUATION_GAP_INVALID",
                message="The Evidence Gap Report payload is invalid.",
                status_code=409,
            ) from exc
        if (
            not isinstance(gaps, list)
            or not gaps
            or any(not isinstance(gap, str) or not gap.strip() for gap in gaps)
        ):
            raise ServiceError(
                code="CONTINUATION_GAP_INVALID",
                message="The Evidence Gap Report contains no continuable gaps.",
                status_code=409,
            )
        ordinals = command.gap_ordinals or tuple(range(1, len(gaps) + 1))
        if any(ordinal > len(gaps) for ordinal in ordinals):
            raise ServiceError(
                code="CONTINUATION_GAP_NOT_FOUND",
                message="A selected Evidence Gap ordinal does not exist.",
                status_code=422,
            )
        selected_gaps = [gaps[ordinal - 1].strip() for ordinal in ordinals]
        parent_scope = json.loads(parent.scope_snapshot_json)
        source_ids = tuple(
            int(item["source_id"])
            for item in parent_scope.get("revisions", [])
        )
        deliverable_payload = json.loads(parent.deliverable_json)
        open_command = OpenRun(
            request_id=command.request_id,
            space_id=parent.space_id,
            goal=self._continuation_goal(selected_gaps),
            scope=ScopeSelector(source_ids=source_ids),
            deliverable=DeliverableSpec(
                kind=str(deliverable_payload.get("kind") or "answer"),
                title=deliverable_payload.get("title"),
            ),
            mode=RunMode.FORCE_AGENT,
            budget=BudgetLimits(**json.loads(parent.budget_limits_json)),
            permissions=PermissionPolicy(**json.loads(parent.policy_snapshot_json)),
            provider_mode=parent.provider_mode,
        )
        origin = RunOrigin(
            kind="continuation",
            source_run_id=parent.id,
            gap_artifact_id=artifact.id,
            gap_ordinals=tuple(ordinals),
        )
        snapshot = self._resolve_scope(
            session,
            open_command,
            strict_source_scope=True,
        )
        return open_command, snapshot, origin, PinnedDecisionPolicy.from_run(parent)

    @staticmethod
    def _continuation_goal(gaps: list[str]) -> str:
        return "; ".join(gaps)[:4_000]

    def _resolve_scope(
        self,
        session: Session,
        command: OpenRun,
        *,
        strict_source_scope: bool = False,
    ) -> ScopeSnapshot:
        statement = select(Source).where(
            Source.space_id == command.space_id,
            Source.retired_at.is_(None),
        )
        if strict_source_scope and not command.scope.source_ids:
            sources = []
        elif command.scope.source_ids:
            statement = statement.where(Source.id.in_(command.scope.source_ids))
            sources = session.scalars(statement.order_by(Source.id.asc())).all()
        else:
            sources = session.scalars(statement.order_by(Source.id.asc())).all()
        explicit_source_ids = set(command.scope.source_ids)
        invalid_source_ids = explicit_source_ids - {source.id for source in sources}
        revisions: list[ScopedRevision] = []
        for source in sources:
            if not source.active_revision_id:
                if explicit_source_ids:
                    invalid_source_ids.add(source.id)
                continue
            revision = session.get(SourceRevision, source.active_revision_id)
            index_id = source.active_index_revision_id
            if index_id is None:
                index_id = session.scalar(
                    select(IndexRevision.id).where(
                        IndexRevision.source_id == source.id,
                        IndexRevision.revision_id == revision.id,
                        IndexRevision.status == "active",
                    )
                ) if revision is not None else None
            if revision is None or not index_id:
                if explicit_source_ids:
                    invalid_source_ids.add(source.id)
                continue
            if explicit_source_ids:
                index = session.get(IndexRevision, index_id)
                if (
                    revision.source_id != source.id
                    or revision.status != "active"
                    or revision.validation_status != "passed"
                    or index is None
                    or index.source_id != source.id
                    or index.revision_id != revision.id
                    or index.status != "active"
                    or index.validation_status != "passed"
                ):
                    invalid_source_ids.add(source.id)
                    continue
            revisions.append(
                ScopedRevision(
                    source_id=source.id,
                    revision_id=revision.id,
                    index_revision_id=index_id,
                    content_hash=revision.content_hash or source.content_hash or "0" * 64,
                )
            )
        if invalid_source_ids:
            raise ServiceError(
                code="RUN_SCOPE_INVALID",
                message="所选资料不存在、已退役、不属于当前空间或尚无可用版本/索引，请刷新资料后重新选择。",
                status_code=422,
                details={"invalid_source_ids": sorted(invalid_source_ids)},
            )
        return ScopeSnapshot(space_id=command.space_id, revisions=tuple(revisions))

    def _append_event(
        self,
        session: Session,
        run: AgentRun,
        *,
        event_type: str,
        payload: dict[str, object],
    ) -> AgentEvent:
        return SqlAgentJournal(session).append_event(run, event_type=event_type, payload=payload)

    def _write_checkpoint(self, session: Session, run: AgentRun, event_cursor: int) -> None:
        SqlAgentJournal(session).checkpoint(run, event_cursor)

    def _enqueue_advance(self, session: Session, run: AgentRun, *, reason: str) -> None:
        SqlAgentJournal(session).enqueue_advance(run, reason=reason)

    def _replay_or_conflict(self, session: Session, request_id: str, payload_hash: str) -> Submission | None:
        existing = session.scalar(select(AgentCommand).where(AgentCommand.request_id == request_id))
        if existing is None:
            return None
        if existing.payload_hash != payload_hash:
            raise ServiceError(
                code="IDEMPOTENCY_CONFLICT",
                message="The request id was already used with a different payload.",
                status_code=409,
            )
        value = json.loads(existing.receipt_json)
        return Submission(
            command_id=value["command_id"],
            run_id=value["run_id"],
            run_version=value["run_version"],
            status=RunStatus(value["status"]),
            cursor=value["cursor"],
            replayed=True,
        )

    @staticmethod
    def _is_request_id_integrity_conflict(error: IntegrityError) -> bool:
        original = error.orig
        diagnostic = getattr(original, "diag", None)
        constraint_name = str(getattr(diagnostic, "constraint_name", "") or "").lower()
        if constraint_name in {
            "ix_agent_commands_request_id",
            "agent_commands_request_id_key",
        }:
            return True
        message = str(original).lower()
        names_request_id = (
            "agent_commands.request_id" in message
            or "ix_agent_commands_request_id" in message
            or "agent_commands_request_id_key" in message
        )
        is_unique_conflict = any(
            marker in message
            for marker in ("unique", "duplicate key", "duplicate entry")
        )
        return names_request_id and is_unique_conflict

    @staticmethod
    def _modified_artifact_title(response: object) -> str:
        if not isinstance(response, Mapping) or set(response) != {"title"}:
            raise ServiceError(
                code="INVALID_MODIFICATION",
                message="Artifact modification accepts only a title field.",
                status_code=422,
            )
        title = response.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 255:
            raise ServiceError(
                code="INVALID_MODIFICATION",
                message="Artifact title must contain between 1 and 255 characters.",
                status_code=422,
            )
        return title.strip()

    def _replace_artifact_publication_proposal(
        self,
        session: Session,
        run: AgentRun,
        old_gate: AgentGate,
        old_tool_call: AgentToolCall,
        *,
        title: str,
    ) -> AgentGate:
        if old_gate.kind != "approval" or old_tool_call.tool_name != "publish_artifact":
            raise ServiceError(
                code="MODIFICATION_NOT_SUPPORTED",
                message="Only a pending Artifact publication title can be modified.",
                status_code=409,
            )
        try:
            old_arguments = json.loads(old_tool_call.arguments_json)
        except json.JSONDecodeError as exc:
            raise ServiceError(
                code="PROPOSAL_STATE_CONFLICT",
                message="The pending Artifact proposal is invalid.",
                status_code=409,
            ) from exc
        artifact = session.get(AgentArtifact, str(old_arguments.get("artifact_id") or ""))
        if (
            artifact is None
            or artifact.producing_run_id != run.id
            or artifact.status != "draft"
            or old_arguments.get("run_id") != run.id
            or old_arguments.get("expected_status") != "draft"
            or old_arguments.get("artifact_digest")
            != artifact_content_digest(
                title=artifact.title,
                body_markdown=artifact.body_markdown,
                structured_payload_json=artifact.structured_payload_json,
            )
        ):
            raise ServiceError(
                code="PROPOSAL_STATE_CONFLICT",
                message="The draft Artifact changed before modification.",
                status_code=409,
            )
        if artifact.title == title:
            raise ServiceError(
                code="MODIFICATION_NO_CHANGE",
                message="The modified title must differ from the pending title.",
                status_code=422,
            )

        artifact.title = title
        old_tool_call.status = "superseded"
        old_tool_call.error_code = "proposal_modified"
        old_tool_call.finished_at = datetime.now(UTC)
        intent = ToolIntent(
            name="publish_artifact",
            arguments={
                "artifact_id": artifact.id,
                "artifact_digest": artifact_content_digest(
                    title=artifact.title,
                    body_markdown=artifact.body_markdown,
                    structured_payload_json=artifact.structured_payload_json,
                ),
                "expected_status": "draft",
                "run_id": run.id,
            },
        )
        proposal = ToolRegistry.production().validate_proposal(
            intent,
            pinned_revision_ids=tuple(
                int(item["revision_id"])
                for item in json.loads(run.scope_snapshot_json).get("revisions", [])
            ),
        )
        tool_call = AgentToolCall(
            id=str(uuid4()),
            run_id=run.id,
            invocation_key=f"publish_artifact:{artifact.id}:modified:{run.version}",
            tool_name=proposal.name,
            tool_version=proposal.version,
            effect=proposal.effect.value,
            arguments_json=self._canonical_json(dict(proposal.arguments)),
            arguments_digest=proposal.arguments_digest,
            status="awaiting_approval",
            execution_epoch=run.execution_epoch,
        )
        gate = AgentGate(
            id=str(uuid4()),
            run_id=run.id,
            kind="approval",
            status="open",
            prompt="发布修改标题后的逐 claim 引用研究成果吗？",
            response_schema_json=self._canonical_json(
                {
                    "type": "object",
                    "properties": {"approved": {"type": "boolean"}},
                    "required": ["approved"],
                    "additionalProperties": False,
                }
            ),
            proposed_tool_call_id=tool_call.id,
            arguments_digest=proposal.arguments_digest,
            policy_reason="protected_artifact_publication_modified",
        )
        session.add_all((tool_call, gate))
        return gate

    @staticmethod
    def _proposal_target(session: Session, gate: AgentGate) -> str:
        tool_call = (
            session.get(AgentToolCall, gate.proposed_tool_call_id)
            if gate.proposed_tool_call_id is not None
            else None
        )
        if tool_call is None:
            return "artifact:unknown"
        try:
            artifact_id = json.loads(tool_call.arguments_json).get("artifact_id")
        except json.JSONDecodeError:
            artifact_id = None
        return f"artifact:{artifact_id or 'unknown'}"

    @staticmethod
    def _to_state_signal(signal: SignalKind) -> RunSignal:
        return {
            SignalKind.PROVIDE_INPUT: RunSignal.PROVIDE_INPUT,
            SignalKind.APPROVE: RunSignal.APPROVE,
            SignalKind.REJECT: RunSignal.REJECT,
            SignalKind.MODIFY: RunSignal.MODIFY,
            SignalKind.PAUSE: RunSignal.PAUSE,
            SignalKind.RESUME: RunSignal.RESUME,
            SignalKind.CANCEL: RunSignal.CANCEL,
        }[signal]

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _payload_hash(self, command: OpenRun | ContinueRun | SignalRun) -> str:
        return hashlib.sha256(self._canonical_json(asdict(command)).encode("utf-8")).hexdigest()

    def _receipt_json(self, receipt: Submission) -> str:
        return self._canonical_json(
            {
                "command_id": receipt.command_id,
                "run_id": receipt.run_id,
                "run_version": receipt.run_version,
                "status": receipt.status.value,
                "cursor": receipt.cursor,
            }
        )

    @staticmethod
    def _empty_usage() -> dict[str, int]:
        return {
            "steps": 0,
            "tool_calls": 0,
            "model_calls": 0,
            "model_input_tokens": 0,
            "model_output_tokens": 0,
            "cost_micros": 0,
            "cost_reported_calls": 0,
            "cost_estimated_calls": 0,
            "cost_unknown_calls": 0,
            "active_ms": 0,
            "no_new_evidence_rounds": 0,
            "query_rewrites": 0,
            "evidence_records": 0,
            "context_tokens": 0,
        }

    @staticmethod
    def _scope_payload(snapshot: ScopeSnapshot) -> dict[str, object]:
        return {
            "space_id": snapshot.space_id,
            "revisions": [asdict(item) for item in snapshot.revisions],
        }

    @staticmethod
    def _run_view_payload(view: RunView) -> dict[str, object]:
        return {
            "id": view.id,
            "space_id": view.space_id,
            "goal": view.goal,
            "requested_mode": view.requested_mode.value,
            "effective_mode": view.effective_mode.value if view.effective_mode else None,
            "status": view.status.value,
            "phase": view.phase.value,
            "version": view.version,
            "execution_epoch": view.execution_epoch,
            "scope_snapshot": SqlEvidenceAgent._scope_payload(view.scope_snapshot),
            "origin": asdict(view.origin),
            "budget_limits": dict(view.budget_limits),
            "budget_usage": dict(view.budget_usage),
            "provider_mode": view.provider_mode,
            "last_event_cursor": view.last_event_cursor,
            "decision_policy": asdict(view.decision_policy) if view.decision_policy else None,
            "final_artifact_id": view.final_artifact_id,
            "termination_reason": view.termination_reason,
            "cost_measurement": view.cost_measurement,
        }

    @staticmethod
    def _deliverable_payload(deliverable: DeliverableSpec, origin: RunOrigin) -> dict[str, object]:
        return {**asdict(deliverable), "origin": asdict(origin)}

    @staticmethod
    def _origin_from_deliverable(payload: Mapping[str, object]) -> RunOrigin:
        raw_origin = payload.get("origin")
        origin = raw_origin if isinstance(raw_origin, Mapping) else {}
        raw_ordinals = origin.get("gap_ordinals", ())
        ordinals = raw_ordinals if isinstance(raw_ordinals, (list, tuple)) else ()
        return RunOrigin(
            kind=str(origin.get("kind") or "initial"),
            source_run_id=str(origin["source_run_id"]) if origin.get("source_run_id") else None,
            gap_artifact_id=str(origin["gap_artifact_id"]) if origin.get("gap_artifact_id") else None,
            gap_ordinals=tuple(int(value) for value in ordinals),
        )

    @staticmethod
    def _view(run: AgentRun, cursor: int) -> RunView:
        scope_value = json.loads(run.scope_snapshot_json)
        deliverable_value = json.loads(run.deliverable_json)
        snapshot = ScopeSnapshot(
            space_id=int(scope_value["space_id"]),
            revisions=tuple(ScopedRevision(**item) for item in scope_value.get("revisions", [])),
        )
        budget_usage = json.loads(run.budget_usage_json)
        return RunView(
            id=run.id,
            space_id=run.space_id,
            goal=run.goal,
            requested_mode=RunMode(run.requested_mode),
            effective_mode=RunMode(run.effective_mode) if run.effective_mode else None,
            status=RunStatus(run.status),
            phase=RunPhase(run.phase),
            version=run.version,
            execution_epoch=run.execution_epoch,
            scope_snapshot=snapshot,
            origin=SqlEvidenceAgent._origin_from_deliverable(deliverable_value),
            budget_limits=json.loads(run.budget_limits_json),
            budget_usage=budget_usage,
            provider_mode=run.provider_mode,
            last_event_cursor=cursor,
            decision_policy=SqlEvidenceAgent._policy_view(
                PinnedDecisionPolicy.from_run(run)
            ),
            final_artifact_id=run.final_artifact_id,
            termination_reason=run.termination_reason,
            cost_measurement=SqlEvidenceAgent._cost_measurement(budget_usage),
        )

    def _load_active_policy(self) -> PinnedDecisionPolicy:
        if self._active_policy is None:
            raise ServiceError(
                code="POLICY_NOT_CONFIGURED",
                message="The active Agent policy port is not configured.",
                status_code=503,
            )
        detail = self._active_policy()
        if not isinstance(detail, PolicyDetail) or detail.status is not PolicyStatus.ACTIVE:
            raise ServiceError(
                code="POLICY_ACTIVE_STATE_INVALID",
                message="The active Agent policy is unavailable or invalid.",
                status_code=503,
            )
        config_json = canonical_policy_json(detail.config)
        if policy_fingerprint(detail.config) != detail.config_sha256:
            raise ServiceError(
                code="POLICY_ACTIVE_STATE_INVALID",
                message="The active Agent policy fingerprint is invalid.",
                status_code=503,
            )
        return PinnedDecisionPolicy(
            id=detail.id,
            version=detail.version,
            config_sha256=detail.config_sha256,
            config_json=config_json,
            config=detail.config,
        )

    @staticmethod
    def _policy_view(policy: PinnedDecisionPolicy | None) -> DecisionPolicyView | None:
        if policy is None:
            return None
        return DecisionPolicyView(
            id=policy.id,
            version=policy.version,
            config_sha256=policy.config_sha256,
        )

    @staticmethod
    def _policy_payload(policy: PinnedDecisionPolicy | None) -> dict[str, object] | None:
        view = SqlEvidenceAgent._policy_view(policy)
        return asdict(view) if view else None

    @staticmethod
    def _cost_measurement(usage: dict[str, int]) -> str:
        unknown = int(usage.get("cost_unknown_calls", 0))
        estimated = int(usage.get("cost_estimated_calls", 0))
        reported = int(usage.get("cost_reported_calls", 0))
        if unknown:
            return "partial_unknown" if estimated or reported else "unknown"
        if estimated:
            return "estimated"
        if reported:
            return "reported"
        return "unknown"

    @staticmethod
    def _public_cursor(session: Session, run_id: str) -> int:
        return session.scalar(
            select(func.max(AgentEvent.id)).where(
                AgentEvent.run_id == run_id,
                AgentEvent.visibility == "public",
            )
        ) or 0

    @staticmethod
    def _artifact_view(session: Session, artifact_id: str) -> ArtifactView:
        artifact = session.get(AgentArtifact, artifact_id)
        if artifact is None:
            raise ServiceError(code="ARTIFACT_NOT_FOUND", message="Agent artifact not found.", status_code=404)
        try:
            structured_claims = {
                item["id"]: item
                for item in json.loads(artifact.structured_payload_json).get("claims", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
        except (json.JSONDecodeError, AttributeError):
            structured_claims = {}
        claims: list[ArtifactClaimView] = []
        for claim in session.scalars(
            select(AgentClaim).where(AgentClaim.artifact_id == artifact.id).order_by(AgentClaim.ordinal)
        ):
            evidence_ids = tuple(
                session.scalars(
                    select(ClaimEvidence.evidence_id)
                    .where(ClaimEvidence.claim_id == claim.id)
                    .order_by(ClaimEvidence.id)
                )
            )
            has_support = session.scalar(
                select(ClaimEvidence.id).where(
                    ClaimEvidence.claim_id == claim.id,
                    ClaimEvidence.relation == "supports",
                )
            )
            if claim.kind == "factual" and has_support is None:
                raise ServiceError(
                    code="ARTIFACT_PROVENANCE_INVALID",
                    message="A factual claim has no verified supporting evidence.",
                    status_code=409,
                )
            decision = structured_claims.get(claim.id, {}).get("decision", {})
            if not isinstance(decision, dict):
                decision = {}
            contested = claim.verification_status == "contested"
            claims.append(
                ArtifactClaimView(
                    id=claim.id,
                    ordinal=claim.ordinal,
                    text=claim.text,
                    kind=claim.kind,
                    verification_status=claim.verification_status,
                    evidence_ids=evidence_ids,
                    resolution_status=decision.get(
                        "resolution_status",
                        "unresolved" if contested else "not_applicable",
                    ),
                    confidence_millis=int(decision.get("confidence_millis", 0)),
                    confidence_band=decision.get("confidence_band", "low"),
                    calibration_method=str(
                        decision.get("calibration_method", "legacy_uncalibrated")
                    ),
                    calibration_reason=str(
                        decision.get("calibration_reason", "legacy_claim")
                    ),
                )
            )
        return ArtifactView(
            id=artifact.id,
            producing_run_id=artifact.producing_run_id,
            kind=artifact.kind,
            title=artifact.title,
            body_markdown=artifact.body_markdown,
            status=artifact.status,
            schema_version=artifact.schema_version,
            claims=tuple(claims),
        )

    @staticmethod
    def _evidence_view(session: Session, evidence_id: str) -> EvidenceView:
        evidence = session.get(AgentEvidence, evidence_id)
        if evidence is None:
            raise ServiceError(code="EVIDENCE_NOT_FOUND", message="Agent evidence not found.", status_code=404)
        claim_ids = tuple(
            session.scalars(
                select(ClaimEvidence.claim_id)
                .where(ClaimEvidence.evidence_id == evidence.id)
                .order_by(ClaimEvidence.id)
            )
        )
        return EvidenceView(
            id=evidence.id,
            run_id=evidence.run_id,
            source_id=evidence.source_id,
            revision_id=evidence.revision_id,
            index_revision_id=evidence.index_revision_id,
            chunk_id=evidence.chunk_id,
            source_type=evidence.source_type,
            locator=json.loads(evidence.locator_json),
            revision_content_hash=evidence.revision_content_hash,
            content_hash=evidence.evidence_content_hash,
            excerpt_preview=evidence.excerpt_preview,
            claim_ids=claim_ids,
        )
