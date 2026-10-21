from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import re
import time
from typing import Callable, Mapping
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evidence import (
    AgentArtifact,
    AgentClaim,
    AgentEvidence,
    ClaimEvidence,
    RequirementEvidence,
)
from app.models.agent_run import (
    AgentGate,
    AgentModelCall,
    AgentPlan,
    AgentRequirement,
    AgentRun,
    AgentToolCall,
)
from app.models.source import Source
from app.modules.agent_policy.contracts import SearchPolicyDecision
from app.modules.agent_policy.decision import (
    PolicyHit,
    RetrievalDecisionPolicy,
    filter_policy_hits,
)
from app.modules.evidence_agent.budget import BudgetController, BudgetExceeded, BudgetUsage
from app.modules.evidence_agent.claim_verifier import (
    ClaimVerificationRequest,
    ClaimVerificationResult,
    DeterministicClaimVerifier,
)
from app.modules.evidence_agent.contracts import BudgetLimits, RunMode, RunPhase, RunStatus
from app.modules.evidence_agent.decision_policy import (
    ClaimDecision,
    ConservativeEvidenceDecisionPolicy,
)
from app.modules.evidence_agent.policy_snapshot import PinnedDecisionPolicy
from app.modules.evidence_agent.sql_store import SqlAgentJournal, canonical_json
from app.modules.evidence_agent.tools import (
    EvidenceGapState,
    EvidenceToolSelection,
    EvidenceToolSelectionPolicy,
    ToolIntent,
    ToolPolicyDenied,
    ToolRegistry,
    artifact_content_digest,
)
from app.modules.evidence_index import (
    EvidenceHit,
    EvidenceQuery,
    EvidenceQueryResult,
    EvidenceSearchResult,
    EvidenceWindow,
    GetEvidenceChunk,
    GetEvidenceNeighbors,
    PinnedEvidenceRef,
    PinnedScope,
    SearchEvidence,
)
from app.services.agent_model import (
    AgentModel,
    AgentModelInvocationError,
    AgentModelResult,
    AssessModelInput,
    EvidenceModelContext,
    PlanDecision,
    PlanModelInput,
    RequirementModelContext,
    RouteDecision,
    RouteModelInput,
    SufficiencyDecision,
    SynthesisDecision,
    SynthesisModelInput,
    StructuredAgentModel,
)
from app.services.llm_service import ModelCallLimits


SearchPort = Callable[[SearchEvidence], EvidenceSearchResult]
EvidenceQueryPort = Callable[[EvidenceQuery], EvidenceQueryResult]
SessionFactory = Callable[[], Session]


@dataclass(frozen=True, slots=True)
class AdvanceResult:
    run_id: str
    applied: bool
    version: int
    status: RunStatus
    reason: str


@dataclass(frozen=True, slots=True)
class _ModelOutcome:
    result: AgentModelResult | None
    version: int
    stale: AdvanceResult | None = None


@dataclass(frozen=True, slots=True)
class _EvidenceRelationChange:
    evidence_id: str
    requirement_id: str
    requirement_ordinal: int
    previous_relation: str
    relation: str
    reason: str
    method: str

    def public_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "requirement_id": self.requirement_id,
            "requirement_ordinal": self.requirement_ordinal,
            "previous_relation": self.previous_relation,
            "relation": self.relation,
            "reason": self.reason,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class _PreparedEvidenceRead:
    tool_call_id: str
    tool_name: str
    evidence_id: str
    revision_id: int
    chunk_id: int
    requirement_ids: tuple[str, ...]
    before: int
    after: int
    reserved_version: int


@dataclass(frozen=True, slots=True)
class _PreparedSearch:
    tool_call_id: str
    requirement_id: str
    query: str
    revision_ids: tuple[int, ...]
    reserved_version: int
    limit: int
    policy_decision: SearchPolicyDecision | None


class AgentRunner:
    """Advances one durable, bounded run slice per invocation.

    Model and retrieval calls must happen outside the SQL transaction. The
    execution epoch is rechecked before returned work can become evidence.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        search: SearchPort,
        *,
        evidence_query: EvidenceQueryPort | None = None,
        agent_model: AgentModel | None = None,
        agent_models: Mapping[str, AgentModel] | None = None,
        clock: Callable[[], float] = time.perf_counter,
        claim_lease_seconds: int = 1_800,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._search = search
        self._evidence_query = evidence_query
        self._agent_model = agent_model
        self._agent_models = dict(agent_models or {})
        if agent_model is not None:
            self._agent_models.setdefault("real", agent_model)
        self._claim_verifier = DeterministicClaimVerifier()
        self._decision_policy = ConservativeEvidenceDecisionPolicy()
        self._tool_selection = EvidenceToolSelectionPolicy()
        self._clock = clock
        self._claim_lease_seconds = max(1, claim_lease_seconds)
        self._utcnow = utcnow or (lambda: datetime.now(UTC))

    def advance_one(self, run_id: str, *, expected_version: int, execution_epoch: int) -> AdvanceResult:
        claim_owner = f"agent-runner:{uuid4().hex}"
        if not self._claim_run(
            run_id,
            expected_version=expected_version,
            execution_epoch=execution_epoch,
            claim_owner=claim_owner,
        ):
            with self._sessions() as session:
                run = session.get(AgentRun, run_id)
                if run is None:
                    raise ServiceError(
                        code="RUN_NOT_FOUND",
                        message="Agent run not found.",
                        status_code=404,
                    )
                reason = (
                    "lease_busy"
                    if run.version == expected_version
                    and run.execution_epoch == execution_epoch
                    else "stale_wakeup"
                )
                return self._result(run, applied=False, reason=reason)

        release_claim = True
        try:
            with self._sessions() as session:
                run = session.get(AgentRun, run_id)
                if run is None:
                    raise ServiceError(
                        code="RUN_NOT_FOUND",
                        message="Agent run not found.",
                        status_code=404,
                    )
                if run.version != expected_version or run.execution_epoch != execution_epoch:
                    return self._result(run, applied=False, reason="stale_wakeup")
                status = RunStatus(run.status)
                phase = RunPhase(run.phase)

            if status is RunStatus.QUEUED:
                return self._dispatch(run_id, expected_version, execution_epoch)
            if status is RunStatus.ROUTING:
                return self._route(run_id, expected_version, execution_epoch)
            if status is RunStatus.PLANNED:
                return self._start_plan(run_id, expected_version, execution_epoch)
            if status is RunStatus.RUNNING and phase is RunPhase.RETRIEVE:
                return self._retrieve(run_id, expected_version, execution_epoch)
            if status is RunStatus.RUNNING and phase is RunPhase.ASSESS:
                return self._assess(run_id, expected_version, execution_epoch)
            if status is RunStatus.RUNNING and phase is RunPhase.SYNTHESIZE:
                return self._synthesize(run_id, expected_version, execution_epoch)
            if status is RunStatus.RUNNING and phase is RunPhase.PERSIST_ARTIFACT:
                return self._publish_approved_artifact(
                    run_id,
                    expected_version,
                    execution_epoch,
                )
            return AdvanceResult(
                run_id=run_id,
                applied=False,
                version=expected_version,
                status=status,
                reason="not_runnable",
            )
        except Exception:
            # The queue wake-up was already acknowledged by the SQL outbox.  If
            # this slice rolls back, retaining an immediately-expired run lease
            # gives AgentInvocationRecovery a durable, CAS-fenced retry signal.
            # Should this best-effort expiry fail, the original lease remains
            # recoverable after its normal timeout instead of being cleared.
            release_claim = False
            try:
                self._expire_claim(run_id, claim_owner=claim_owner)
            except Exception:
                pass
            raise
        finally:
            if release_claim:
                self._release_claim(run_id, claim_owner=claim_owner)

    def _claim_run(
        self,
        run_id: str,
        *,
        expected_version: int,
        execution_epoch: int,
        claim_owner: str,
    ) -> bool:
        now = self._utcnow()
        with self._sessions() as session, session.begin():
            claimed = session.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    AgentRun.version == expected_version,
                    AgentRun.execution_epoch == execution_epoch,
                    or_(
                        AgentRun.lease_owner.is_(None),
                        AgentRun.lease_expires_at.is_(None),
                        AgentRun.lease_expires_at <= now,
                    ),
                )
                .values(
                    lease_owner=claim_owner,
                    lease_expires_at=now + timedelta(seconds=self._claim_lease_seconds),
                )
                .execution_options(synchronize_session=False)
            )
            return claimed.rowcount == 1

    def _release_claim(self, run_id: str, *, claim_owner: str) -> None:
        with self._sessions() as session, session.begin():
            session.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    AgentRun.lease_owner == claim_owner,
                )
                .values(lease_owner=None, lease_expires_at=None)
                .execution_options(synchronize_session=False)
            )

    def _expire_claim(self, run_id: str, *, claim_owner: str) -> None:
        with self._sessions() as session, session.begin():
            session.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    AgentRun.lease_owner == claim_owner,
                )
                .values(lease_expires_at=self._utcnow())
                .execution_options(synchronize_session=False)
            )

    def _dispatch(self, run_id: str, version: int, epoch: int) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            if run.phase == RunPhase.ROUTE.value and run.effective_mode is None:
                run.status = RunStatus.ROUTING.value
                reason = "routing"
            else:
                run.status = RunStatus.RUNNING.value
                reason = "resumed"
            run.version += 1
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="run.status_changed",
                payload={"status": run.status, "reason": reason},
            )
            session.flush()
            journal.checkpoint(run, event.id)
            journal.enqueue_advance(run, reason=reason)
            return self._result(run, applied=True, reason=reason)

    def _model_for(self, provider_mode: str) -> AgentModel | None:
        # An explicitly injected model is the test/in-process seam. Production
        # wiring supplies a complete mode map, so this fallback cannot collapse
        # the real/demo/recording isolation there; it only keeps direct Runner
        # construction compatible with the historical ``agent_model=...`` API.
        return self._agent_models.get(provider_mode) or self._agent_model

    def _route(self, run_id: str, version: int, epoch: int) -> AdvanceResult:
        with self._sessions() as session:
            snapshot = session.get(AgentRun, run_id)
            if snapshot is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            if snapshot.version != version or snapshot.execution_epoch != epoch:
                return self._result(snapshot, applied=False, reason="stale_wakeup")
            model = self._model_for(snapshot.provider_mode)
            # Recording/demo runs intentionally retain the deterministic policy
            # when no model is injected. Only a real run must fail closed rather
            # than silently substituting that offline policy.
            provider_missing = snapshot.provider_mode == "real" and model is None
            requested = RunMode(snapshot.requested_mode)
            effective = self._select_mode(requested, snapshot.goal)
            goal = snapshot.goal
            source_count = len(json.loads(snapshot.scope_snapshot_json).get("revisions", []))

        if provider_missing:
            return self._fail_configuration(
                run_id,
                version,
                epoch,
                reason="llm_not_configured",
            )

        if requested is RunMode.AUTO and model is not None:
            outcome = self._invoke_model(
                run_id,
                version,
                epoch,
                operation="route",
                invoke=lambda allow_repair, call_limits: self._bounded_model(model, call_limits).route(
                    RouteModelInput(goal=goal, source_count=source_count),
                    allow_repair=allow_repair,
                ),
            )
            if outcome.stale is not None:
                return outcome.stale
            version = outcome.version
            if outcome.result is not None and isinstance(outcome.result.value, RouteDecision):
                effective = RunMode(outcome.result.value.mode)

        model_plan: PlanDecision | None = None
        if effective is RunMode.FORCE_AGENT and model is not None:
            outcome = self._invoke_model(
                run_id,
                version,
                epoch,
                operation="plan",
                invoke=lambda allow_repair, call_limits: self._bounded_model(model, call_limits).plan(
                    PlanModelInput(goal=goal, max_requirements=8),
                    allow_repair=allow_repair,
                ),
            )
            if outcome.stale is not None:
                return outcome.stale
            version = outcome.version
            if outcome.result is not None and isinstance(outcome.result.value, PlanDecision):
                model_plan = outcome.result.value

        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            run.effective_mode = effective.value
            run.version += 1
            journal = SqlAgentJournal(session)
            journal.append_event(
                run,
                event_type="run.mode_selected",
                payload={"requested": requested.value, "effective": effective.value},
            )

            if effective is RunMode.FORCE_QUICK:
                run.status = RunStatus.RUNNING.value
                run.phase = RunPhase.RETRIEVE.value
                session.add(
                    AgentRequirement(
                        id=str(uuid4()),
                        run_id=run.id,
                        plan_version=0,
                        ordinal=1,
                        text=run.goal,
                        kind="factual",
                        priority="must",
                        status="uncovered",
                    )
                )
                final_event = journal.append_event(
                    run,
                    event_type="step.started",
                    payload={"phase": RunPhase.RETRIEVE.value, "mode": "quick"},
                )
                reason = "quick_selected"
            else:
                run.status = RunStatus.PLANNED.value
                run.phase = RunPhase.PLAN.value
                run.current_plan_version = 1
                plan = AgentPlan(
                    id=str(uuid4()),
                    run_id=run.id,
                    version=1,
                    strategy=(
                        "structured_model_plan"
                        if model_plan is not None
                        else "deterministic_requirement_decomposition"
                    ),
                    created_by="model" if model_plan is not None else "policy",
                    summary_json=canonical_json(
                        {
                            "goal": run.goal,
                            "rationale": model_plan.rationale if model_plan is not None else "",
                        }
                    ),
                )
                session.add(plan)
                proposals = model_plan.requirements if model_plan is not None else None
                requirements = (
                    [proposal.text for proposal in proposals]
                    if proposals is not None
                    else self._requirements(run.goal)
                )
                for ordinal, requirement in enumerate(requirements, start=1):
                    proposal = proposals[ordinal - 1] if proposals is not None else None
                    session.add(
                        AgentRequirement(
                            id=str(uuid4()),
                            run_id=run.id,
                            plan_version=1,
                            ordinal=ordinal,
                            text=requirement,
                            kind=proposal.kind if proposal is not None else "factual",
                            priority=proposal.priority if proposal is not None else "must",
                            status="uncovered",
                        )
                    )
                final_event = journal.append_event(
                    run,
                    event_type="plan.created",
                    payload={
                        "plan_version": 1,
                        "strategy": plan.strategy,
                        "requirements": requirements,
                    },
                )
                reason = "agent_selected"
            session.flush()
            journal.checkpoint(run, final_event.id)
            journal.enqueue_advance(run, reason=reason)
            return self._result(run, applied=True, reason=reason)

    def _invoke_model(
        self,
        run_id: str,
        version: int,
        epoch: int,
        *,
        operation: str,
        invoke: Callable[[bool, ModelCallLimits], AgentModelResult],
    ) -> _ModelOutcome:
        prepared = self._prepare_model_call(run_id, version, epoch, operation=operation)
        if isinstance(prepared, _ModelOutcome):
            return prepared
        model_call_id, reserved_version, allow_repair, call_limits = prepared
        started_at = self._clock()
        try:
            result = invoke(allow_repair, call_limits)
        except Exception as exc:
            observed_active_ms = max(
                0,
                int((self._clock() - started_at) * 1_000),
            )
            return self._finish_model_call(
                run_id,
                model_call_id,
                reserved_version,
                epoch,
                result=None,
                error=exc,
                observed_active_ms=observed_active_ms,
            )
        observed_active_ms = max(
            0,
            int((self._clock() - started_at) * 1_000),
        )
        return self._finish_model_call(
            run_id,
            model_call_id,
            reserved_version,
            epoch,
            result=result,
            error=None,
            observed_active_ms=observed_active_ms,
        )

    def _prepare_model_call(
        self,
        run_id: str,
        version: int,
        epoch: int,
        *,
        operation: str,
    ) -> tuple[str, int, bool, ModelCallLimits] | _ModelOutcome:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return _ModelOutcome(
                    result=None,
                    version=version,
                    stale=self._stale_result(session, run_id),
                )
            limits = BudgetLimits(**json.loads(run.budget_limits_json))
            usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
            exhausted_reason = next(
                (
                    reason
                    for reason, consumed, maximum in (
                        ("max_context_tokens", usage.context_tokens, limits.max_context_tokens),
                        ("max_model_input_tokens", usage.model_input_tokens, limits.max_model_input_tokens),
                        ("max_model_output_tokens", usage.model_output_tokens, limits.max_model_output_tokens),
                        ("max_cost_micros", usage.cost_micros, limits.max_cost_micros),
                        ("max_active_ms", usage.active_ms, limits.max_active_ms),
                    )
                    if consumed >= maximum
                ),
                None,
            )
            if exhausted_reason is not None:
                journal = SqlAgentJournal(session)
                event = journal.append_event(
                    run,
                    event_type="budget.exhausted",
                    payload={
                        "reason": exhausted_reason,
                        "before_external": "model",
                        "usage": usage.as_dict(),
                    },
                )
                session.flush()
                journal.checkpoint(run, event.id)
                return _ModelOutcome(result=None, version=run.version)
            try:
                usage = BudgetController(limits).reserve_model_call(usage)
            except BudgetExceeded as exc:
                journal = SqlAgentJournal(session)
                event = journal.append_event(
                    run,
                    event_type="budget.exhausted",
                    payload={
                        "reason": exc.reason,
                        "before_external": "model",
                        "usage": usage.as_dict(),
                    },
                )
                session.flush()
                journal.checkpoint(run, event.id)
                return _ModelOutcome(result=None, version=run.version)

            run.budget_usage_json = canonical_json(usage.as_dict())
            run.version += 1
            model_call_id = str(uuid4())
            session.add(
                AgentModelCall(
                    id=model_call_id,
                    run_id=run.id,
                    invocation_key=f"{operation}:{run.phase}:{usage.model_calls}",
                    operation=operation,
                    provider=(self._model_for(run.provider_mode).provider_name if self._model_for(run.provider_mode) else "unknown"),
                    model=(self._model_for(run.provider_mode).model_name if self._model_for(run.provider_mode) else "unknown"),
                    status="running",
                    execution_epoch=run.execution_epoch,
                )
            )
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="model.started",
                payload={"model_call_id": model_call_id, "operation": operation},
                visibility="internal",
            )
            session.flush()
            journal.checkpoint(run, event.id)
            allow_repair = (
                usage.model_calls < limits.max_model_calls
                and usage.steps < limits.max_steps
            )
            call_limits = ModelCallLimits(
                remaining_model_calls=limits.max_model_calls - usage.model_calls + 1,
                remaining_input_tokens=limits.max_model_input_tokens - usage.model_input_tokens,
                remaining_output_tokens=limits.max_model_output_tokens - usage.model_output_tokens,
                remaining_context_tokens=limits.max_context_tokens - usage.context_tokens,
                remaining_cost_micros=limits.max_cost_micros - usage.cost_micros,
                remaining_active_ms=limits.max_active_ms - usage.active_ms,
            )
            return model_call_id, run.version, allow_repair, call_limits

    @staticmethod
    def _bounded_model(model: AgentModel, limits: ModelCallLimits) -> AgentModel:
        # Recording/deterministic adapters retain their existing contract.
        # The real adapter is copied per invocation so parallel runs never share mutable limits.
        if isinstance(model, StructuredAgentModel):
            return model.with_call_limits(limits)
        return model

    def _finish_model_call(
        self,
        run_id: str,
        model_call_id: str,
        version: int,
        epoch: int,
        *,
        result: AgentModelResult | None,
        error: Exception | None,
        observed_active_ms: int,
    ) -> _ModelOutcome:
        with self._sessions() as session, session.begin():
            run = session.get(AgentRun, run_id)
            model_call = session.get(AgentModelCall, model_call_id)
            if run is None or model_call is None:
                raise ServiceError(
                    code="RUN_STATE_MISSING",
                    message="Model invocation state is missing.",
                    status_code=409,
                )
            if run.version != version or run.execution_epoch != epoch:
                if model_call.status == "running":
                    model_call.status = "abandoned"
                    model_call.error_code = "execution_fence_changed"
                    model_call.finished_at = datetime.now(UTC)
                return _ModelOutcome(
                    result=None,
                    version=run.version,
                    stale=self._result(run, applied=False, reason="execution_fence_changed"),
                )

            journal = SqlAgentJournal(session)
            if error is not None or result is None:
                typed_error = error if isinstance(error, AgentModelInvocationError) else None
                error_active_ms = max(
                    observed_active_ms,
                    typed_error.usage.latency_ms if typed_error is not None else 0,
                )
                error_cost = typed_error.usage.cost_micros if typed_error is not None else None
                error_cost_status = (
                    typed_error.usage.cost_status if typed_error is not None else "unknown"
                )
                limits = BudgetLimits(**json.loads(run.budget_limits_json))
                usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
                budget_error: BudgetExceeded | None = None
                try:
                    usage = BudgetController(limits).record_model_usage(
                        usage,
                        input_tokens=(
                            typed_error.usage.input_tokens if typed_error is not None else 0
                        ),
                        output_tokens=(
                            typed_error.usage.output_tokens if typed_error is not None else 0
                        ),
                        cost_micros=error_cost,
                        cost_status=error_cost_status,
                        active_ms=error_active_ms,
                        additional_model_calls=(
                            typed_error.usage.provider_retries
                            + typed_error.usage.repair_attempts
                            if typed_error is not None
                            else 0
                        ),
                    )
                except BudgetExceeded as exc:
                    budget_error = exc
                    usage = exc.usage or usage
                run.budget_usage_json = canonical_json(usage.as_dict())
                model_call.latency_ms = error_active_ms
                if typed_error is not None:
                    model_call.provider = typed_error.provider
                    model_call.model = typed_error.model
                    model_call.input_tokens = typed_error.usage.input_tokens
                    model_call.output_tokens = typed_error.usage.output_tokens
                    model_call.cost_micros = typed_error.usage.cost_micros or 0
                    model_call.retries = (
                        typed_error.usage.provider_retries
                        + typed_error.usage.repair_attempts
                    )
                    model_call.usage_estimated = (
                        1
                        if typed_error.usage.estimated
                        or typed_error.usage.cost_status != "reported"
                        else 0
                    )
                else:
                    model_call.usage_estimated = 1
                model_call.status = "failed"
                model_call.error_code = (
                    typed_error.code
                    if typed_error is not None
                    else type(error).__name__
                    if error is not None
                    else "MODEL_RESULT_MISSING"
                )
                model_call.finished_at = datetime.now(UTC)
                if budget_error is not None:
                    journal.append_event(
                        run,
                        event_type="budget.exhausted",
                        payload={
                            "reason": budget_error.reason,
                            "after_external": "model",
                            "usage": usage.as_dict(),
                        },
                    )
                final_event = journal.append_event(
                    run,
                    event_type="model.failed",
                    payload={
                        "model_call_id": model_call.id,
                        "operation": model_call.operation,
                        "fallback": "deterministic_policy",
                        "cost": {"micros": error_cost, "status": error_cost_status},
                    },
                    visibility="internal",
                )
                session.flush()
                journal.checkpoint(run, final_event.id)
                return _ModelOutcome(result=None, version=run.version)

            limits = BudgetLimits(**json.loads(run.budget_limits_json))
            usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
            budget_error: BudgetExceeded | None = None
            try:
                usage = BudgetController(limits).record_model_usage(
                    usage,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    cost_micros=result.usage.cost_micros,
                    cost_status=result.usage.cost_status,
                    active_ms=max(result.usage.latency_ms, observed_active_ms),
                    additional_model_calls=(
                        result.usage.provider_retries + result.usage.repair_attempts
                    ),
                )
            except BudgetExceeded as exc:
                budget_error = exc
                usage = exc.usage or usage
            run.budget_usage_json = canonical_json(usage.as_dict())
            model_call.provider = result.provider
            model_call.model = result.model
            model_call.status = "completed"
            model_call.input_tokens = result.usage.input_tokens
            model_call.output_tokens = result.usage.output_tokens
            model_call.cost_micros = result.usage.cost_micros or 0
            model_call.latency_ms = max(result.usage.latency_ms, observed_active_ms)
            model_call.retries = result.usage.provider_retries + result.usage.repair_attempts
            model_call.usage_estimated = (
                1
                if result.usage.estimated or result.usage.cost_status != "reported"
                else 0
            )
            model_call.finished_at = datetime.now(UTC)
            if budget_error is not None:
                model_call.error_code = f"BUDGET_{budget_error.reason.upper()}"
                journal.append_event(
                    run,
                    event_type="budget.exhausted",
                    payload={
                        "reason": budget_error.reason,
                        "after_external": "model",
                        "usage": usage.as_dict(),
                    },
                )
            final_event = journal.append_event(
                run,
                event_type="model.completed",
                payload={
                    "model_call_id": model_call.id,
                    "operation": model_call.operation,
                    "repair_attempts": result.usage.repair_attempts,
                    "cost": {
                        "micros": result.usage.cost_micros,
                        "status": result.usage.cost_status,
                    },
                    "used": budget_error is None,
                },
                visibility="internal",
            )
            session.flush()
            journal.checkpoint(run, final_event.id)
            return _ModelOutcome(
                result=result if budget_error is None else None,
                version=run.version,
            )

    def _start_plan(self, run_id: str, version: int, epoch: int) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            run.status = RunStatus.RUNNING.value
            run.phase = RunPhase.RETRIEVE.value
            run.version += 1
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="step.started",
                payload={"phase": RunPhase.RETRIEVE.value, "mode": "agent"},
            )
            session.flush()
            journal.checkpoint(run, event.id)
            journal.enqueue_advance(run, reason="plan_started")
            return self._result(run, applied=True, reason="plan_started")

    def _retrieve(self, run_id: str, version: int, epoch: int) -> AdvanceResult:
        prepared_read = self._prepare_evidence_read(run_id, version, epoch)
        if isinstance(prepared_read, AdvanceResult):
            return prepared_read
        if prepared_read is not None:
            return self._execute_evidence_read(run_id, prepared_read, epoch)

        prepared = self._prepare_search(run_id, version, epoch)
        if isinstance(prepared, AdvanceResult):
            return prepared
        tool_call_id = prepared.tool_call_id

        started_at = self._clock()
        try:
            result = self._search(
                SearchEvidence(
                    text=prepared.query,
                    scope=PinnedScope(
                        space_id=self._space_id(run_id),
                        revision_ids=prepared.revision_ids,
                    ),
                    limit=prepared.limit,
                )
            )
        except Exception as exc:
            return self._fail_search(
                run_id,
                tool_call_id,
                expected_version=prepared.reserved_version,
                execution_epoch=epoch,
                error=exc,
            )
        active_ms = max(0, int((self._clock() - started_at) * 1_000))
        if prepared.policy_decision is not None:
            result = self._filter_policy_result(result, prepared.policy_decision)
        return self._commit_search(
            run_id,
            tool_call_id,
            prepared.requirement_id,
            prepared.query,
            result,
            active_ms=active_ms,
            expected_version=prepared.reserved_version,
            execution_epoch=epoch,
        )

    def _prepare_search(
        self,
        run_id: str,
        version: int,
        epoch: int,
    ) -> _PreparedSearch | AdvanceResult:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            requirement = session.scalar(
                select(AgentRequirement)
                .where(
                    AgentRequirement.run_id == run.id,
                    AgentRequirement.status == "uncovered",
                )
                .order_by(AgentRequirement.ordinal.asc())
            )
            if requirement is None:
                return self._decide_after_retrieval(session, run)

            limits = BudgetLimits(**json.loads(run.budget_limits_json))
            usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
            try:
                usage = BudgetController(limits).reserve_tool(usage)
            except BudgetExceeded as exc:
                return self._insufficient(session, run, reason=exc.reason)
            run.budget_usage_json = canonical_json(usage.as_dict())
            run.version += 1
            tool_call_id = str(uuid4())
            selection = self._tool_selection.select(
                EvidenceGapState.UNSEARCHED_REQUIREMENT
            )
            retrieval_policy = self._retrieval_policy(run)
            policy_decision = (
                retrieval_policy.search_decision(requirement.kind)
                if retrieval_policy is not None
                else None
            )
            arguments = {"query": requirement.text, "revision_ids": self._revision_ids(run)}
            if policy_decision is not None:
                arguments.update(
                    {
                        "limit": policy_decision.top_k,
                        "minimum_score_millis": policy_decision.minimum_score_millis,
                        "max_hits_per_source": policy_decision.max_hits_per_source,
                    }
                )
            authorized = ToolRegistry.production_read_only().authorize(
                ToolIntent(name=selection.tool, arguments=arguments),
                pinned_revision_ids=self._revision_ids(run),
            )
            arguments_json = canonical_json(arguments)
            session.add(
                AgentToolCall(
                    id=tool_call_id,
                    run_id=run.id,
                    invocation_key=f"search:{requirement.id}:{usage.tool_calls}",
                    tool_name=authorized.name,
                    tool_version=authorized.version,
                    effect=authorized.effect.value,
                    arguments_json=arguments_json,
                    arguments_digest=authorized.arguments_digest,
                    status="running",
                    execution_epoch=run.execution_epoch,
                    started_at=datetime.now(UTC),
                )
            )
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="tool.started",
                payload={
                    "tool_call_id": tool_call_id,
                    "tool": authorized.name,
                    "requirement_id": requirement.id,
                    "selection": selection.audit_payload(),
                    "retrieval_policy": (
                        policy_decision.audit_payload() if policy_decision is not None else None
                    ),
                },
                tool_call_id=tool_call_id,
            )
            session.flush()
            journal.checkpoint(run, event.id)
            return _PreparedSearch(
                tool_call_id=tool_call_id,
                requirement_id=requirement.id,
                query=requirement.text,
                revision_ids=self._revision_ids(run),
                reserved_version=run.version,
                limit=policy_decision.top_k if policy_decision is not None else 10,
                policy_decision=policy_decision,
            )

    def _prepare_evidence_read(
        self,
        run_id: str,
        version: int,
        epoch: int,
    ) -> _PreparedEvidenceRead | AdvanceResult | None:
        if self._evidence_query is None:
            return None
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            rows = session.execute(
                select(AgentEvidence, RequirementEvidence.requirement_id)
                .join(
                    RequirementEvidence,
                    RequirementEvidence.evidence_id == AgentEvidence.id,
                )
                .join(
                    AgentToolCall,
                    AgentToolCall.id == AgentEvidence.retrieved_by_tool_call_id,
                )
                .join(
                    AgentRequirement,
                    AgentRequirement.id == RequirementEvidence.requirement_id,
                )
                .where(
                    AgentEvidence.run_id == run.id,
                    AgentToolCall.tool_name == "search_evidence",
                    RequirementEvidence.relation.in_(
                        ["candidate", "supports", "contradicts"]
                    ),
                )
                .order_by(AgentRequirement.ordinal, RequirementEvidence.id)
            ).all()
            centers: dict[str, tuple[AgentEvidence, list[str]]] = {}
            selected_requirements: set[str] = set()
            for evidence, requirement_id in rows:
                if requirement_id in selected_requirements:
                    continue
                selected_requirements.add(requirement_id)
                if evidence.id not in centers:
                    centers[evidence.id] = (evidence, [])
                centers[evidence.id][1].append(requirement_id)

            for evidence, requirement_ids in centers.values():
                open_completed = session.scalar(
                    select(AgentToolCall.id).where(
                        AgentToolCall.run_id == run.id,
                        AgentToolCall.tool_name == "open_evidence",
                        AgentToolCall.status == "completed",
                        AgentToolCall.invocation_key.like(f"open:{evidence.id}:%"),
                    )
                )
                if open_completed is None:
                    return self._reserve_evidence_read(
                        session,
                        run,
                        evidence,
                        tuple(requirement_ids),
                        selection=self._tool_selection.select(
                            EvidenceGapState.CANDIDATE_NOT_OPENED
                        ),
                    )
                neighbors_completed = session.scalar(
                    select(AgentToolCall.id).where(
                        AgentToolCall.run_id == run.id,
                        AgentToolCall.tool_name == "read_neighbors",
                        AgentToolCall.status == "completed",
                        AgentToolCall.invocation_key.like(
                            f"neighbors:{evidence.id}:%"
                        ),
                    )
                )
                if neighbors_completed is None:
                    return self._reserve_evidence_read(
                        session,
                        run,
                        evidence,
                        tuple(requirement_ids),
                        selection=self._tool_selection.select(
                            EvidenceGapState.OPENED_WITHOUT_CONTEXT
                        ),
                    )
        return None

    def _reserve_evidence_read(
        self,
        session: Session,
        run: AgentRun,
        evidence: AgentEvidence,
        requirement_ids: tuple[str, ...],
        *,
        selection: EvidenceToolSelection,
    ) -> _PreparedEvidenceRead | AdvanceResult:
        tool_name = selection.tool
        if evidence.revision_id not in self._revision_ids(run):
            return self._insufficient(session, run, reason="pinned_scope_violation")
        limits = BudgetLimits(**json.loads(run.budget_limits_json))
        usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
        try:
            usage = BudgetController(limits).reserve_tool(usage)
        except BudgetExceeded as exc:
            return self._insufficient(session, run, reason=exc.reason)
        retrieval_policy = self._retrieval_policy(run)
        neighbor_decision = (
            retrieval_policy.neighbor_decision()
            if tool_name == "read_neighbors" and retrieval_policy is not None
            else None
        )
        if neighbor_decision is not None:
            before, after = neighbor_decision.before, neighbor_decision.after
        elif tool_name == "read_neighbors":
            before, after = 1, 1
        else:
            before, after = 0, 0
        arguments = (
            {"evidence_id": evidence.id, "before": before, "after": after}
            if tool_name == "read_neighbors"
            else {"evidence_id": evidence.id}
        )
        authorized = ToolRegistry.production_read_only().authorize(
            ToolIntent(name=tool_name, arguments=arguments),
            pinned_revision_ids=self._revision_ids(run),
        )
        run.budget_usage_json = canonical_json(usage.as_dict())
        run.version += 1
        tool_call_id = str(uuid4())
        prefix = "neighbors" if tool_name == "read_neighbors" else "open"
        session.add(
            AgentToolCall(
                id=tool_call_id,
                run_id=run.id,
                invocation_key=f"{prefix}:{evidence.id}:{usage.tool_calls}",
                tool_name=authorized.name,
                tool_version=authorized.version,
                effect=authorized.effect.value,
                arguments_json=canonical_json(dict(authorized.arguments)),
                arguments_digest=authorized.arguments_digest,
                status="running",
                execution_epoch=run.execution_epoch,
                started_at=datetime.now(UTC),
            )
        )
        journal = SqlAgentJournal(session)
        event = journal.append_event(
            run,
            event_type="tool.started",
            payload={
                "tool_call_id": tool_call_id,
                "tool": tool_name,
                "evidence_id": evidence.id,
                "requirement_ids": list(requirement_ids),
                "selection": selection.audit_payload(),
                "retrieval_policy": (
                    neighbor_decision.audit_payload() if neighbor_decision is not None else None
                ),
            },
            tool_call_id=tool_call_id,
        )
        session.flush()
        journal.checkpoint(run, event.id)
        return _PreparedEvidenceRead(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            evidence_id=evidence.id,
            revision_id=evidence.revision_id,
            chunk_id=evidence.chunk_id,
            requirement_ids=requirement_ids,
            before=before,
            after=after,
            reserved_version=run.version,
        )

    @staticmethod
    def _filter_policy_result(
        result: EvidenceSearchResult,
        decision: SearchPolicyDecision,
    ) -> EvidenceSearchResult:
        originals: dict[str, EvidenceHit] = {}
        policy_hits: list[PolicyHit] = []
        for hit in result.hits:
            evidence = hit.evidence
            identity = (
                f"{evidence.source_id}:{evidence.revision_id}:{evidence.chunk_id}:"
                f"{evidence.content_hash}"
            )
            originals.setdefault(identity, hit)
            policy_hits.append(
                PolicyHit(
                    identity=identity,
                    source_id=evidence.source_id,
                    score=hit.score,
                )
            )
        accepted = filter_policy_hits(
            tuple(policy_hits),
            minimum_score_millis=decision.minimum_score_millis,
            max_hits_per_source=decision.max_hits_per_source,
        )
        return EvidenceSearchResult(hits=tuple(originals[item.identity] for item in accepted))

    @staticmethod
    def _retrieval_policy(run: AgentRun) -> RetrievalDecisionPolicy | None:
        pinned = PinnedDecisionPolicy.from_run(run)
        return pinned.retrieval_policy() if pinned is not None else None

    def _execute_evidence_read(
        self,
        run_id: str,
        prepared: _PreparedEvidenceRead,
        epoch: int,
    ) -> AdvanceResult:
        if self._evidence_query is None:
            raise RuntimeError("Evidence read was prepared without a query port.")
        query: EvidenceQuery = (
            GetEvidenceNeighbors(
                revision_id=prepared.revision_id,
                chunk_id=prepared.chunk_id,
                before=prepared.before,
                after=prepared.after,
            )
            if prepared.tool_name == "read_neighbors"
            else GetEvidenceChunk(
                revision_id=prepared.revision_id,
                chunk_id=prepared.chunk_id,
            )
        )
        started_at = self._clock()
        try:
            result = self._evidence_query(query)
        except Exception as exc:
            return self._fail_evidence_read(
                run_id,
                prepared.tool_call_id,
                expected_version=prepared.reserved_version,
                execution_epoch=epoch,
                error=exc,
            )
        result_error: Exception | None = None
        if prepared.tool_name == "open_evidence":
            if (
                not isinstance(result, PinnedEvidenceRef)
                or result.revision_id != prepared.revision_id
                or result.chunk_id != prepared.chunk_id
            ):
                result_error = ValueError(
                    "Opened evidence does not match the prepared pinned identity."
                )
        elif (
            not isinstance(result, EvidenceWindow)
            or result.center_chunk_id != prepared.chunk_id
            or not any(item.chunk_id == prepared.chunk_id for item in result.items)
            or len(result.items) > prepared.before + prepared.after + 1
            or any(item.revision_id != prepared.revision_id for item in result.items)
        ):
            result_error = ValueError(
                "Neighbor evidence does not match the bounded pinned window."
            )
        if result_error is not None:
            return self._fail_evidence_read(
                run_id,
                prepared.tool_call_id,
                expected_version=prepared.reserved_version,
                execution_epoch=epoch,
                error=result_error,
            )
        active_ms = max(0, int((self._clock() - started_at) * 1_000))
        return self._commit_evidence_read(
            run_id,
            prepared,
            result,
            active_ms=active_ms,
            execution_epoch=epoch,
        )

    def _commit_evidence_read(
        self,
        run_id: str,
        prepared: _PreparedEvidenceRead,
        result: EvidenceQueryResult,
        *,
        active_ms: int,
        execution_epoch: int,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = session.get(AgentRun, run_id)
            tool_call = session.get(AgentToolCall, prepared.tool_call_id)
            center = session.get(AgentEvidence, prepared.evidence_id)
            if run is None or tool_call is None or center is None:
                raise ServiceError(
                    code="RUN_STATE_MISSING",
                    message="Evidence read invocation state is missing.",
                    status_code=409,
                )
            if (
                run.version != prepared.reserved_version
                or run.execution_epoch != execution_epoch
                or run.status != RunStatus.RUNNING.value
                or run.phase != RunPhase.RETRIEVE.value
            ):
                tool_call.status = "abandoned"
                tool_call.error_code = "execution_fence_changed"
                tool_call.finished_at = datetime.now(UTC)
                return self._result(
                    run,
                    applied=False,
                    reason="execution_fence_changed",
                )

            new_records = 0
            journal = SqlAgentJournal(session)
            if prepared.tool_name == "open_evidence":
                if (
                    not isinstance(result, PinnedEvidenceRef)
                    or result.revision_id != center.revision_id
                    or result.chunk_id != center.chunk_id
                ):
                    raise ServiceError(
                        code="EVIDENCE_READ_MISMATCH",
                        message="Opened evidence does not match the pinned Agent evidence.",
                        status_code=409,
                    )
                tool_call.result_json = canonical_json(
                    {"reference": self._reference_payload(result)}
                )
                journal.append_event(
                    run,
                    event_type="evidence.opened",
                    payload={
                        "evidence_id": center.id,
                        "reference": self._reference_payload(result),
                    },
                    tool_call_id=tool_call.id,
                )
            else:
                if not isinstance(result, EvidenceWindow):
                    raise ServiceError(
                        code="EVIDENCE_WINDOW_INVALID",
                        message="Neighbor read did not return an evidence window.",
                        status_code=409,
                    )
                revision_hashes = {
                    int(item["revision_id"]): str(item["content_hash"])
                    for item in json.loads(run.scope_snapshot_json).get("revisions", [])
                }
                source = session.get(Source, center.source_id)
                source_title = (
                    source.title or source.original_filename or f"Source {center.source_id}"
                    if source is not None
                    else f"Source {center.source_id}"
                )
                neighbor_ids: list[str] = []
                for item in result.items:
                    if item.chunk_id == center.chunk_id:
                        continue
                    if (
                        item.revision_id != center.revision_id
                        or item.revision_id not in self._revision_ids(run)
                    ):
                        raise ServiceError(
                            code="EVIDENCE_WINDOW_SCOPE_ESCAPE",
                            message="Neighbor evidence escaped the pinned revision.",
                            status_code=409,
                        )
                    locator_json = canonical_json(dict(item.locator))
                    locator_digest = sha256(locator_json.encode("utf-8")).hexdigest()
                    neighbor = session.scalar(
                        select(AgentEvidence).where(
                            AgentEvidence.run_id == run.id,
                            AgentEvidence.revision_id == item.revision_id,
                            AgentEvidence.chunk_id == item.chunk_id,
                            AgentEvidence.locator_digest == locator_digest,
                        )
                    )
                    if neighbor is None:
                        neighbor = AgentEvidence(
                            id=str(uuid4()),
                            run_id=run.id,
                            source_id=item.source_id,
                            revision_id=item.revision_id,
                            index_revision_id=item.index_revision_id,
                            chunk_id=item.chunk_id,
                            source_type=item.source_type,
                            locator_json=locator_json,
                            locator_digest=locator_digest,
                            revision_content_hash=revision_hashes.get(
                                item.revision_id,
                                "0" * 64,
                            ),
                            evidence_content_hash=item.content_hash,
                            excerpt_preview=item.excerpt[:1_200],
                            retrieved_by_tool_call_id=tool_call.id,
                            query=center.query,
                            retrieval_scores_json=canonical_json(
                                {"bounded_neighbor": True}
                            ),
                            trust_level="untrusted",
                            active_at_snapshot=1,
                        )
                        session.add(neighbor)
                        session.flush()
                        new_records += 1
                    neighbor_ids.append(neighbor.id)
                    relation_added = False
                    for requirement_id in prepared.requirement_ids:
                        existing_relation = session.scalar(
                            select(RequirementEvidence.id).where(
                                RequirementEvidence.requirement_id == requirement_id,
                                RequirementEvidence.evidence_id == neighbor.id,
                            )
                        )
                        if existing_relation is None:
                            session.add(
                                RequirementEvidence(
                                    requirement_id=requirement_id,
                                    evidence_id=neighbor.id,
                                    relation="contextual",
                                    method="bounded_neighbors",
                                    confidence_millis=600,
                                    reason_code="same_revision_neighbor",
                                )
                            )
                            relation_added = True
                    if relation_added:
                        journal.append_event(
                            run,
                            event_type="evidence.added",
                            payload={
                                "evidence_id": neighbor.id,
                                "source_title": source_title,
                                "excerpt": neighbor.excerpt_preview,
                                "relation": "contextual",
                                "reference": self._reference_payload(item),
                            },
                            tool_call_id=tool_call.id,
                        )
                tool_call.result_json = canonical_json(
                    {
                        "center_evidence_id": center.id,
                        "neighbor_evidence_ids": neighbor_ids,
                    }
                )

            limits = BudgetLimits(**json.loads(run.budget_limits_json))
            usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
            try:
                if prepared.tool_name == "read_neighbors":
                    usage = BudgetController(limits).record_evidence(
                        usage,
                        new_records=new_records,
                    )
                usage = BudgetController(limits).add_active_time(usage, active_ms)
            except BudgetExceeded as exc:
                run.budget_usage_json = canonical_json(
                    (exc.usage or usage).as_dict()
                )
                tool_call.status = "completed"
                tool_call.finished_at = datetime.now(UTC)
                return self._insufficient(session, run, reason=exc.reason)
            run.budget_usage_json = canonical_json(usage.as_dict())
            tool_call.status = "completed"
            tool_call.finished_at = datetime.now(UTC)
            run.version += 1
            completed = journal.append_event(
                run,
                event_type="tool.completed",
                payload={
                    "tool_call_id": tool_call.id,
                    "tool": prepared.tool_name,
                    "new_evidence": new_records,
                },
                tool_call_id=tool_call.id,
            )
            session.flush()
            journal.checkpoint(run, completed.id)
            journal.enqueue_advance(run, reason=f"{prepared.tool_name}_completed")
            return self._result(
                run,
                applied=True,
                reason=f"{prepared.tool_name}_completed",
            )

    def _commit_search(
        self,
        run_id: str,
        tool_call_id: str,
        requirement_id: str,
        query: str,
        result: EvidenceSearchResult,
        *,
        active_ms: int,
        expected_version: int,
        execution_epoch: int,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = session.get(AgentRun, run_id)
            tool_call = session.get(AgentToolCall, tool_call_id)
            if run is None or tool_call is None:
                raise ServiceError(code="RUN_STATE_MISSING", message="Run invocation state is missing.", status_code=409)
            if (
                run.version != expected_version
                or run.execution_epoch != execution_epoch
                or run.status != RunStatus.RUNNING.value
                or run.phase != RunPhase.RETRIEVE.value
            ):
                if tool_call.status == "running":
                    tool_call.status = "abandoned"
                    tool_call.error_code = "execution_fence_changed"
                    tool_call.finished_at = datetime.now(UTC)
                return self._result(run, applied=False, reason="execution_fence_changed")

            requirement = session.get(AgentRequirement, requirement_id)
            if requirement is None:
                raise ServiceError(code="REQUIREMENT_NOT_FOUND", message="Requirement state is missing.", status_code=409)
            revision_hashes = {
                int(item["revision_id"]): str(item["content_hash"])
                for item in json.loads(run.scope_snapshot_json).get("revisions", [])
            }
            new_records = 0
            evidence_ids: list[str] = []
            evidence_rows: list[tuple[AgentEvidence, float]] = []
            for hit in self._context_hits(result.hits):
                evidence = hit.evidence
                locator_json = canonical_json(dict(evidence.locator))
                locator_digest = sha256(locator_json.encode("utf-8")).hexdigest()
                existing = session.scalar(
                    select(AgentEvidence).where(
                        AgentEvidence.run_id == run.id,
                        AgentEvidence.revision_id == evidence.revision_id,
                        AgentEvidence.chunk_id == evidence.chunk_id,
                        AgentEvidence.locator_digest == locator_digest,
                    )
                )
                if existing is None:
                    existing = AgentEvidence(
                        id=str(uuid4()),
                        run_id=run.id,
                        source_id=evidence.source_id,
                        revision_id=evidence.revision_id,
                        index_revision_id=evidence.index_revision_id,
                        chunk_id=evidence.chunk_id,
                        source_type=evidence.source_type,
                        locator_json=locator_json,
                        locator_digest=locator_digest,
                        revision_content_hash=revision_hashes.get(evidence.revision_id, "0" * 64),
                        evidence_content_hash=evidence.content_hash,
                        excerpt_preview=evidence.excerpt[:1_200],
                        retrieved_by_tool_call_id=tool_call.id,
                        query=query,
                        retrieval_scores_json=canonical_json({"hybrid": hit.score}),
                        trust_level="untrusted",
                        active_at_snapshot=1,
                    )
                    session.add(existing)
                    session.flush()
                    new_records += 1
                evidence_ids.append(existing.id)
                evidence_rows.append((existing, hit.score))

            directly_supporting_rows = [
                item
                for item in evidence_rows
                if self._direct_fact_support(query, item[0].excerpt_preview)
            ]
            if directly_supporting_rows:
                requirement_rows = directly_supporting_rows
                relations = self._classify_relations(
                    [item.excerpt_preview for item, _score in requirement_rows]
                )
            elif run.effective_mode == RunMode.FORCE_AGENT.value:
                # Semantic candidates remain available to the structured
                # sufficiency model, but retrieval alone does not mark coverage.
                requirement_rows = evidence_rows
                relations = ["candidate"] * len(requirement_rows)
            else:
                requirement_rows = []
                relations = []
            relation_by_evidence_id = {
                evidence_row.id: relation_name
                for (evidence_row, _score), relation_name in zip(
                    requirement_rows,
                    relations,
                    strict=True,
                )
            }
            for (evidence_row, score), relation_name in zip(
                requirement_rows,
                relations,
                strict=True,
            ):
                relation = session.scalar(
                    select(RequirementEvidence).where(
                        RequirementEvidence.requirement_id == requirement.id,
                        RequirementEvidence.evidence_id == evidence_row.id,
                        RequirementEvidence.relation == relation_name,
                    )
                )
                if relation is None:
                    session.add(
                        RequirementEvidence(
                            requirement_id=requirement.id,
                            evidence_id=evidence_row.id,
                            relation=relation_name,
                            method=(
                                "retrieval_candidate"
                                if relation_name == "candidate"
                                else "deterministic"
                            ),
                            confidence_millis=min(1000, max(0, int(score * 500))),
                            reason_code=(
                                "semantic_retrieval_candidate"
                                if relation_name == "candidate"
                                else "quantitative_conflict"
                                if relation_name == "contradicts"
                                else "retrieval_match"
                            ),
                        )
                    )

            limits = BudgetLimits(**json.loads(run.budget_limits_json))
            usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
            try:
                usage = BudgetController(limits).record_evidence(usage, new_records=new_records)
                usage = BudgetController(limits).add_active_time(usage, active_ms)
            except BudgetExceeded as exc:
                if exc.usage is not None:
                    run.budget_usage_json = canonical_json(exc.usage.as_dict())
                tool_call.status = "completed"
                tool_call.result_json = canonical_json({"evidence_ids": evidence_ids, "count": len(evidence_ids)})
                tool_call.finished_at = datetime.now(UTC)
                return self._insufficient(session, run, reason=exc.reason)
            run.budget_usage_json = canonical_json(usage.as_dict())
            requirement.status = (
                "contradicted"
                if directly_supporting_rows and "contradicts" in relations
                else "covered"
                if directly_supporting_rows
                else "partial"
            )
            tool_call.status = "completed"
            tool_call.result_json = canonical_json({"evidence_ids": evidence_ids, "count": len(evidence_ids)})
            tool_call.finished_at = datetime.now(UTC)
            run.version += 1
            journal = SqlAgentJournal(session)
            if evidence_ids:
                source_ids = {item.source_id for item, _score in evidence_rows}
                source_titles = {
                    source.id: source.title or source.original_filename or f"Source {source.id}"
                    for source in session.scalars(select(Source).where(Source.id.in_(source_ids)))
                }
                for evidence_row, _score in evidence_rows:
                    relation_name = relation_by_evidence_id.get(
                        evidence_row.id,
                        "candidate",
                    )
                    journal.append_event(
                        run,
                        event_type="evidence.added",
                        payload={
                            "evidence_id": evidence_row.id,
                            "source_title": source_titles.get(
                                evidence_row.source_id,
                                f"Source {evidence_row.source_id}",
                            ),
                            "excerpt": evidence_row.excerpt_preview,
                            "relation": relation_name,
                            "reference": {
                                "source_id": evidence_row.source_id,
                                "revision_id": evidence_row.revision_id,
                                "index_revision_id": evidence_row.index_revision_id,
                                "chunk_id": evidence_row.chunk_id,
                                "content_hash": evidence_row.evidence_content_hash,
                                "locator": json.loads(evidence_row.locator_json),
                            },
                        },
                        tool_call_id=tool_call.id,
                    )
            completed_event = journal.append_event(
                run,
                event_type="tool.completed",
                payload={"tool_call_id": tool_call.id, "new_evidence": new_records},
                tool_call_id=tool_call.id,
            )
            session.flush()

            if (
                run.effective_mode == RunMode.FORCE_QUICK.value
                and requirement.status in {"uncovered", "partial"}
            ):
                return self._insufficient(
                    session,
                    run,
                    reason="required_evidence_missing",
                    event_cursor=completed_event.id,
                    increment_version=False,
                )
            pending = session.scalar(
                select(AgentRequirement.id).where(
                    AgentRequirement.run_id == run.id,
                    AgentRequirement.status == "uncovered",
                )
            )
            if pending is not None:
                journal.checkpoint(run, completed_event.id)
                journal.enqueue_advance(run, reason="search_more")
                return self._result(run, applied=True, reason="search_more")
            if run.effective_mode == RunMode.FORCE_AGENT.value:
                if self._evidence_query is not None:
                    journal.checkpoint(run, completed_event.id)
                    journal.enqueue_advance(run, reason="inspect_evidence")
                    return self._result(
                        run,
                        applied=True,
                        reason="inspect_evidence",
                    )
                run.phase = RunPhase.ASSESS.value
                assessment = journal.append_event(
                    run,
                    event_type="step.started",
                    payload={"phase": RunPhase.ASSESS.value},
                )
                session.flush()
                journal.checkpoint(run, assessment.id)
                journal.enqueue_advance(run, reason="assess_evidence")
                return self._result(run, applied=True, reason="assess_evidence")
            uncovered = session.scalar(
                select(AgentRequirement.id).where(
                    AgentRequirement.run_id == run.id,
                    AgentRequirement.priority == "must",
                    AgentRequirement.status.in_(["uncovered", "partial"]),
                )
            )
            if uncovered is not None:
                return self._insufficient(
                    session,
                    run,
                    reason="required_evidence_missing",
                    event_cursor=completed_event.id,
                    increment_version=False,
                )
            run.phase = RunPhase.SYNTHESIZE.value
            decision = journal.append_event(
                run,
                event_type="sufficiency.decided",
                payload={"decision": "answer", "evidence_count": len(evidence_ids)},
            )
            session.flush()
            journal.checkpoint(run, decision.id)
            journal.enqueue_advance(run, reason="sufficient")
            return self._result(run, applied=True, reason="sufficient")

    def _decide_after_retrieval(self, session: Session, run: AgentRun) -> AdvanceResult:
        if run.effective_mode == RunMode.FORCE_AGENT.value:
            run.phase = RunPhase.ASSESS.value
            run.version += 1
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="step.started",
                payload={"phase": RunPhase.ASSESS.value},
            )
            session.flush()
            journal.checkpoint(run, event.id)
            journal.enqueue_advance(run, reason="assess_evidence")
            return self._result(run, applied=True, reason="assess_evidence")
        missing = session.scalar(
            select(AgentRequirement.id).where(
                AgentRequirement.run_id == run.id,
                AgentRequirement.priority == "must",
                AgentRequirement.status.in_(["uncovered", "partial"]),
            )
        )
        if missing is not None:
            return self._insufficient(session, run, reason="required_evidence_missing")
        run.phase = RunPhase.SYNTHESIZE.value
        run.version += 1
        journal = SqlAgentJournal(session)
        event = journal.append_event(
            run,
            event_type="sufficiency.decided",
            payload={"decision": "answer"},
        )
        session.flush()
        journal.checkpoint(run, event.id)
        journal.enqueue_advance(run, reason="sufficient")
        return self._result(run, applied=True, reason="sufficient")

    def _assess(self, run_id: str, version: int, epoch: int) -> AdvanceResult:
        with self._sessions() as session:
            snapshot = session.get(AgentRun, run_id)
            if snapshot is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            if snapshot.version != version or snapshot.execution_epoch != epoch:
                return self._result(snapshot, applied=False, reason="stale_wakeup")
            limits = BudgetLimits(**json.loads(snapshot.budget_limits_json))
            usage = BudgetUsage.from_mapping(json.loads(snapshot.budget_usage_json))
            context = AssessModelInput(
                goal=snapshot.goal,
                requirements=self._requirement_contexts(
                    session,
                    snapshot.id,
                    include_candidates=True,
                ),
                query_rewrites_remaining=max(0, limits.max_query_rewrites - usage.query_rewrites),
            )
            model = self._model_for(snapshot.provider_mode)

        model_decision: SufficiencyDecision | None = None
        if model is not None:
            outcome = self._invoke_model(
                run_id,
                version,
                epoch,
                operation="assess",
                invoke=lambda allow_repair, call_limits: self._bounded_model(model, call_limits).assess(
                    context,
                    allow_repair=allow_repair,
                ),
            )
            if outcome.stale is not None:
                return outcome.stale
            version = outcome.version
            if outcome.result is not None and isinstance(
                outcome.result.value, SufficiencyDecision
            ):
                model_decision = outcome.result.value

        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            requirements = session.scalars(
                select(AgentRequirement)
                .where(AgentRequirement.run_id == run.id)
                .order_by(AgentRequirement.ordinal)
            ).all()
            missing = [
                item
                for item in requirements
                if item.priority == "must" and item.status in {"uncovered", "partial"}
            ]

            if model_decision is not None and model_decision.decision == "search_more":
                target = next(
                    (
                        item
                        for item in missing
                        if item.ordinal == model_decision.target_requirement_ordinal
                    ),
                    None,
                )
                if target is not None and model_decision.next_query is not None:
                    limits = BudgetLimits(**json.loads(run.budget_limits_json))
                    usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
                    try:
                        usage = BudgetController(limits).record_query_rewrite(usage)
                    except BudgetExceeded as exc:
                        return self._insufficient(session, run, reason=exc.reason)
                    old_query = target.text
                    target.text = model_decision.next_query.strip()
                    target.status = "uncovered"
                    run.budget_usage_json = canonical_json(usage.as_dict())
                    run.phase = RunPhase.RETRIEVE.value
                    run.version += 1
                    journal = SqlAgentJournal(session)
                    event = journal.append_event(
                        run,
                        event_type="sufficiency.decided",
                        payload={
                            "decision": "search_more",
                            "requirement_ordinal": target.ordinal,
                            "previous_query": old_query,
                            "next_query": target.text,
                        },
                    )
                    session.flush()
                    journal.checkpoint(run, event.id)
                    journal.enqueue_advance(run, reason="model_next_query")
                    return self._result(run, applied=True, reason="model_next_query")

            if model_decision is not None and model_decision.decision == "request_clarification":
                target = next(
                    (
                        item
                        for item in requirements
                        if item.ordinal == model_decision.target_requirement_ordinal
                    ),
                    None,
                )
                question = (model_decision.clarification_question or "").strip()
                if target is None or not question:
                    return self._insufficient(
                        session,
                        run,
                        reason="model_clarification_target_invalid",
                    )
                limits = BudgetLimits(**json.loads(run.budget_limits_json))
                usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
                try:
                    usage = BudgetController(limits).record_query_rewrite(usage)
                except BudgetExceeded as exc:
                    return self._insufficient(session, run, reason=exc.reason)

                response_schema = {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 500,
                        }
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                }
                gate_id = str(uuid4())
                persisted_schema = {
                    **response_schema,
                    "x-evidence-agent": {
                        "target_requirement_id": target.id,
                        "target_requirement_ordinal": target.ordinal,
                        "previous_query": target.text,
                    },
                }
                session.add(
                    AgentGate(
                        id=gate_id,
                        run_id=run.id,
                        kind="clarification",
                        status="open",
                        prompt=question,
                        response_schema_json=canonical_json(persisted_schema),
                        policy_reason=model_decision.reason,
                    )
                )
                run.pending_gate_id = gate_id
                run.status = RunStatus.AWAITING_INPUT.value
                run.budget_usage_json = canonical_json(usage.as_dict())
                run.version += 1
                journal = SqlAgentJournal(session)
                journal.append_event(
                    run,
                    event_type="run.awaiting_input",
                    payload={"gate_id": gate_id, "reason": "clarification_required"},
                )
                event = journal.append_event(
                    run,
                    event_type="interaction.required",
                    payload={
                        "gate_id": gate_id,
                        "kind": "clarification",
                        "question": question,
                        "target": {
                            "requirement_id": target.id,
                            "requirement_ordinal": target.ordinal,
                        },
                        "response_schema": response_schema,
                    },
                )
                session.flush()
                journal.checkpoint(run, event.id)
                return self._result(run, applied=True, reason="clarification_required")

            if model_decision is not None and model_decision.decision == "insufficient_evidence":
                return self._insufficient(session, run, reason="model_insufficient_evidence")
            relation_changes: list[_EvidenceRelationChange] = []
            if model_decision is not None and model_decision.decision == "answer":
                promoted = self._promote_selected_support(
                    session,
                    run,
                    missing,
                    model_decision,
                )
                if promoted is None:
                    return self._insufficient(
                        session,
                        run,
                        reason="model_evidence_selection_invalid",
                    )
                relation_changes = promoted
                missing = [
                    item
                    for item in requirements
                    if item.priority == "must" and item.status in {"uncovered", "partial"}
                ]
            if missing:
                return self._insufficient(session, run, reason="required_evidence_missing")

            run.phase = RunPhase.SYNTHESIZE.value
            run.version += 1
            journal = SqlAgentJournal(session)
            for change in relation_changes:
                journal.append_event(
                    run,
                    event_type="evidence.relation_changed",
                    payload=change.public_payload(),
                )
            event = journal.append_event(
                run,
                event_type="sufficiency.decided",
                payload={
                    "decision": "answer",
                    "method": "model" if model_decision is not None else "deterministic_fallback",
                },
            )
            session.flush()
            journal.checkpoint(run, event.id)
            journal.enqueue_advance(run, reason="sufficient")
            return self._result(run, applied=True, reason="sufficient")

    def _synthesize(self, run_id: str, version: int, epoch: int) -> AdvanceResult:
        with self._sessions() as session:
            snapshot = session.get(AgentRun, run_id)
            if snapshot is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            if snapshot.version != version or snapshot.execution_epoch != epoch:
                return self._result(snapshot, applied=False, reason="stale_wakeup")
            deliverable = json.loads(snapshot.deliverable_json)
            context = SynthesisModelInput(
                goal=snapshot.goal,
                title=deliverable.get("title") or "可核验的证据结论",
                requirements=self._requirement_contexts(session, snapshot.id),
            )
            effective_mode = RunMode(snapshot.effective_mode or snapshot.requested_mode)
            model = self._model_for(snapshot.provider_mode)

        model_synthesis: SynthesisDecision | None = None
        if effective_mode is RunMode.FORCE_AGENT and model is not None:
            outcome = self._invoke_model(
                run_id,
                version,
                epoch,
                operation="synthesize",
                invoke=lambda allow_repair, call_limits: self._bounded_model(model, call_limits).synthesize(
                    context,
                    allow_repair=allow_repair,
                ),
            )
            if outcome.stale is not None:
                return outcome.stale
            version = outcome.version
            if outcome.result is not None and isinstance(
                outcome.result.value, SynthesisDecision
            ):
                model_synthesis = outcome.result.value

        return self._persist_synthesis(
            run_id,
            version,
            epoch,
            model_synthesis=model_synthesis,
        )

    def _persist_synthesis(
        self,
        run_id: str,
        version: int,
        epoch: int,
        *,
        model_synthesis: SynthesisDecision | None,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            requirements = session.scalars(
                select(AgentRequirement)
                .where(AgentRequirement.run_id == run.id)
                .order_by(AgentRequirement.ordinal)
            ).all()
            if not requirements:
                return self._insufficient(session, run, reason="required_evidence_missing")

            deliverable = json.loads(run.deliverable_json)
            requires_publication_approval = not bool(
                json.loads(run.policy_snapshot_json).get("read_only", True)
            )
            if requires_publication_approval:
                limits = BudgetLimits(**json.loads(run.budget_limits_json))
                usage = BudgetUsage.from_mapping(json.loads(run.budget_usage_json))
                try:
                    usage = BudgetController(limits).reserve_tool(usage)
                except BudgetExceeded as exc:
                    return self._insufficient(session, run, reason=exc.reason)
                run.budget_usage_json = canonical_json(usage.as_dict())
            artifact_id = str(uuid4())
            title = deliverable.get("title") or "可核验的证据结论"
            claim_rows: list[tuple[AgentClaim, list[tuple[AgentEvidence, str]]]] = []
            claim_verifications: dict[str, ClaimVerificationResult | None] = {}
            claim_decisions: dict[str, ClaimDecision] = {}
            body_lines = [f"# {title}", "", "## 结论", ""]
            structured_claims: list[dict[str, object]] = []
            evidence_count = 0
            model_claims = (
                {claim.requirement_ordinal: claim for claim in model_synthesis.claims}
                if model_synthesis is not None
                else {}
            )
            rejected_model_claims = 0
            if set(model_claims) != set(range(1, len(requirements) + 1)) or len(
                model_claims
            ) != len(model_synthesis.claims if model_synthesis is not None else ()):
                model_claims = {}
            for ordinal, requirement in enumerate(requirements, start=1):
                linked_rows = session.execute(
                    select(AgentEvidence, RequirementEvidence.relation)
                    .join(RequirementEvidence, RequirementEvidence.evidence_id == AgentEvidence.id)
                    .where(
                        RequirementEvidence.requirement_id == requirement.id,
                        RequirementEvidence.relation.in_(["supports", "contradicts"]),
                    )
                    .order_by(RequirementEvidence.id)
                ).all()
                linked = [(item, relation) for item, relation in linked_rows]
                if not linked:
                    return self._insufficient(session, run, reason="required_evidence_missing")
                claim_id = str(uuid4())
                is_contested = any(relation == "contradicts" for _item, relation in linked)
                model_claim_text: str | None = None
                claim_verification: ClaimVerificationResult | None = None
                if ordinal in model_claims:
                    candidate = model_claims[ordinal].text
                    claim_verification = self._claim_verifier.verify(
                        ClaimVerificationRequest(
                            claim=candidate,
                            evidence=tuple(item.excerpt_preview for item, _relation in linked),
                        )
                    )
                    if claim_verification.entailed:
                        model_claim_text = candidate
                    else:
                        rejected_model_claims += 1
                if is_contested:
                    excerpts = "；".join(" ".join(item.excerpt_preview.split())[:220] for item, _relation in linked)
                    claim_text = f"关于“{requirement.text}”，现有证据存在冲突：{excerpts}"[:700]
                elif model_claim_text is not None:
                    claim_text = model_claim_text
                else:
                    claim_text = " ".join(linked[0][0].excerpt_preview.split())[:500]
                    claim_verification = self._claim_verifier.verify(
                        ClaimVerificationRequest(
                            claim=claim_text,
                            evidence=tuple(
                                item.excerpt_preview for item, _relation in linked
                            ),
                        )
                    )
                claim = AgentClaim(
                    id=claim_id,
                    artifact_id=artifact_id,
                    ordinal=ordinal,
                    text=claim_text,
                    kind="factual",
                    verification_status="contested" if is_contested else "supported",
                )
                claim_rows.append((claim, linked))
                claim_verifications[claim_id] = claim_verification
                raw_support_confidence = (
                    claim_verification.confidence_millis
                    if claim_verification is not None
                    else 700
                )
                claim_decision = self._decision_policy.decide_claim(
                    relations=tuple(relation for _item, relation in linked),
                    supporting_confidences=tuple(
                        raw_support_confidence
                        for _item, relation in linked
                        if relation == "supports"
                    ),
                    supporting_source_ids=tuple(
                        item.source_id
                        for item, relation in linked
                        if relation == "supports"
                    ),
                )
                claim_decisions[claim_id] = claim_decision
                body_lines.append(f"{ordinal}. {claim_text} [{ordinal}]")
                evidence_ids_for_claim = [item.id for item, _relation in linked]
                evidence_count += len(evidence_ids_for_claim)
                structured_claims.append(
                    {
                        "id": claim_id,
                        "kind": "factual",
                        "verification_status": claim.verification_status,
                        "text": claim_text,
                        "evidence_ids": evidence_ids_for_claim,
                        "decision": claim_decision.public_payload(),
                    }
                )
            artifact = AgentArtifact(
                id=artifact_id,
                producing_run_id=run.id,
                kind=deliverable.get("kind") or "answer",
                title=title,
                body_markdown="\n".join(body_lines),
                structured_payload_json=canonical_json(
                    {"schema_version": 1, "claims": structured_claims, "evidence_count": evidence_count}
                ),
                status="draft" if requires_publication_approval else "final",
                schema_version=1,
                finalized_at=None if requires_publication_approval else datetime.now(UTC),
            )
            session.add(artifact)
            session.flush()
            for claim, linked in claim_rows:
                session.add(claim)
                session.flush()
                for item, relation in linked:
                    verification = claim_verifications.get(claim.id)
                    decision = claim_decisions[claim.id]
                    if decision.resolution_status == "unresolved":
                        verifier_method = decision.calibration_method
                        confidence_millis = decision.confidence_millis
                        reason_code = decision.calibration_reason
                    elif verification is not None:
                        verifier_method = decision.calibration_method
                        confidence_millis = min(
                            verification.confidence_millis,
                            decision.confidence_millis,
                        )
                        reason_code = decision.calibration_reason
                    else:
                        verifier_method = decision.calibration_method
                        confidence_millis = decision.confidence_millis
                        reason_code = decision.calibration_reason
                    session.add(
                        ClaimEvidence(
                            claim_id=claim.id,
                            evidence_id=item.id,
                            relation=relation,
                            verifier_method=verifier_method,
                            confidence_millis=confidence_millis,
                            reason_code=reason_code,
                        )
                    )

            if requires_publication_approval:
                return self._request_artifact_publication(
                    session,
                    run,
                    artifact,
                )

            run.final_artifact_id = artifact.id
            run.status = RunStatus.COMPLETED.value
            run.phase = RunPhase.PERSIST_ARTIFACT.value
            run.termination_reason = "sufficient_evidence"
            run.finished_at = datetime.now(UTC)
            run.version += 1
            journal = SqlAgentJournal(session)
            journal.append_event(
                run,
                event_type="artifact.finalized",
                payload={
                    "artifact_id": artifact.id,
                    "claim_count": len(claim_rows),
                    "rejected_model_claims": rejected_model_claims,
                },
            )
            journal.append_event(
                run,
                event_type="artifact.published",
                payload={
                    "artifact_id": artifact.id,
                    "final_artifact_id": artifact.id,
                    "title": artifact.title,
                    "kind": artifact.kind,
                    "status": artifact.status,
                },
            )
            final_event = journal.append_event(
                run,
                event_type="run.completed",
                payload={"artifact_id": artifact.id},
            )
            session.flush()
            journal.checkpoint(run, final_event.id)
            return self._result(run, applied=True, reason="completed")

    def _request_artifact_publication(
        self,
        session: Session,
        run: AgentRun,
        artifact: AgentArtifact,
    ) -> AdvanceResult:
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
        proposed = ToolRegistry.production().validate_proposal(
            intent,
            pinned_revision_ids=self._revision_ids(run),
        )
        tool_call_id = str(uuid4())
        gate_id = str(uuid4())
        session.add(
            AgentToolCall(
                id=tool_call_id,
                run_id=run.id,
                invocation_key=f"publish_artifact:{artifact.id}",
                tool_name=proposed.name,
                tool_version=proposed.version,
                effect=proposed.effect.value,
                arguments_json=canonical_json(dict(proposed.arguments)),
                arguments_digest=proposed.arguments_digest,
                status="awaiting_approval",
                execution_epoch=run.execution_epoch,
            )
        )
        session.add(
            AgentGate(
                id=gate_id,
                run_id=run.id,
                kind="approval",
                status="open",
                prompt="发布这份带逐 claim 引用的研究成果吗？",
                response_schema_json=canonical_json(
                    {
                        "type": "object",
                        "properties": {"approved": {"type": "boolean"}},
                        "required": ["approved"],
                        "additionalProperties": False,
                    }
                ),
                proposed_tool_call_id=tool_call_id,
                arguments_digest=proposed.arguments_digest,
                policy_reason="protected_artifact_publication",
            )
        )
        run.pending_gate_id = gate_id
        run.status = RunStatus.AWAITING_APPROVAL.value
        run.phase = RunPhase.PERSIST_ARTIFACT.value
        run.version += 1
        journal = SqlAgentJournal(session)
        journal.append_event(
            run,
            event_type="artifact.drafted",
            payload={"artifact_id": artifact.id, "status": artifact.status},
        )
        journal.append_event(
            run,
            event_type="run.awaiting_approval",
            payload={"gate_id": gate_id, "reason": "protected_artifact_publication"},
        )
        interaction = journal.append_event(
            run,
            event_type="interaction.required",
            payload={
                "gate_id": gate_id,
                "kind": "approval",
                "summary": "发布带逐 claim 引用的研究成果",
                "target": f"artifact:{artifact.id}",
                "risk_class": "write",
                "proposal_digest": proposed.arguments_digest,
            },
        )
        session.flush()
        journal.checkpoint(run, interaction.id)
        return self._result(run, applied=True, reason="approval_required")

    def _publish_approved_artifact(
        self,
        run_id: str,
        version: int,
        epoch: int,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, version, epoch)
            if run is None:
                return self._stale_result(session, run_id)
            gate = session.scalar(
                select(AgentGate)
                .where(
                    AgentGate.run_id == run.id,
                    AgentGate.kind == "approval",
                    AgentGate.status == "approved",
                    AgentGate.proposed_tool_call_id.is_not(None),
                )
                .order_by(AgentGate.opened_at.desc(), AgentGate.id.desc())
            )
            tool_call = (
                session.get(AgentToolCall, gate.proposed_tool_call_id)
                if gate is not None and gate.proposed_tool_call_id is not None
                else None
            )
            if (
                gate is None
                or tool_call is None
                or tool_call.run_id != run.id
                or tool_call.status != "approved"
                or gate.arguments_digest != tool_call.arguments_digest
            ):
                raise ServiceError(
                    code="APPROVED_PROPOSAL_MISSING",
                    message="The approved artifact proposal is missing or no longer valid.",
                    status_code=409,
                )

            arguments = json.loads(tool_call.arguments_json)
            intent = ToolIntent(name=tool_call.tool_name, arguments=arguments)
            try:
                authorized = ToolRegistry.production().authorize(
                    intent,
                    pinned_revision_ids=self._revision_ids(run),
                    approved_digest=gate.arguments_digest,
                )
            except ToolPolicyDenied as exc:
                raise ServiceError(
                    code="APPROVED_PROPOSAL_INVALID",
                    message="The approved artifact proposal failed policy validation.",
                    status_code=409,
                    details={"reason": exc.reason},
                ) from exc

            artifact_id = str(authorized.arguments["artifact_id"])
            artifact = session.get(AgentArtifact, artifact_id)
            if (
                authorized.arguments.get("run_id") != run.id
                or authorized.arguments.get("expected_status") != "draft"
                or artifact is None
                or artifact.producing_run_id != run.id
                or artifact.status != "draft"
                or authorized.arguments.get("artifact_digest")
                != artifact_content_digest(
                    title=artifact.title,
                    body_markdown=artifact.body_markdown,
                    structured_payload_json=artifact.structured_payload_json,
                )
            ):
                raise ServiceError(
                    code="ARTIFACT_PROPOSAL_CONFLICT",
                    message="The artifact changed after approval was requested.",
                    status_code=409,
                )

            now = datetime.now(UTC)
            tool_call.status = "running"
            tool_call.started_at = now
            artifact.status = "final"
            artifact.finalized_at = now
            tool_call.status = "completed"
            tool_call.finished_at = now
            tool_call.result_json = canonical_json(
                {"artifact_id": artifact.id, "status": artifact.status}
            )
            run.final_artifact_id = artifact.id
            run.status = RunStatus.COMPLETED.value
            run.phase = RunPhase.PERSIST_ARTIFACT.value
            run.termination_reason = "sufficient_evidence"
            run.finished_at = now
            run.version += 1
            journal = SqlAgentJournal(session)
            journal.append_event(
                run,
                event_type="tool.started",
                payload={"tool_call_id": tool_call.id, "tool": tool_call.tool_name},
                tool_call_id=tool_call.id,
            )
            journal.append_event(
                run,
                event_type="artifact.finalized",
                payload={"artifact_id": artifact.id},
            )
            journal.append_event(
                run,
                event_type="tool.completed",
                payload={"tool_call_id": tool_call.id, "artifact_id": artifact.id},
                tool_call_id=tool_call.id,
            )
            journal.append_event(
                run,
                event_type="artifact.published",
                payload={
                    "artifact_id": artifact.id,
                    "final_artifact_id": artifact.id,
                    "title": artifact.title,
                    "kind": artifact.kind,
                    "status": artifact.status,
                },
            )
            final_event = journal.append_event(
                run,
                event_type="run.completed",
                payload={"artifact_id": artifact.id},
            )
            session.flush()
            journal.checkpoint(run, final_event.id)
            return self._result(run, applied=True, reason="completed")

    def _insufficient(
        self,
        session: Session,
        run: AgentRun,
        *,
        reason: str,
        event_cursor: int | None = None,
        increment_version: bool = True,
    ) -> AdvanceResult:
        missing = session.scalars(
            select(AgentRequirement.text).where(
                AgentRequirement.run_id == run.id,
                AgentRequirement.status.in_(["uncovered", "partial"]),
            ).order_by(AgentRequirement.ordinal)
        ).all()
        artifact = session.scalar(select(AgentArtifact).where(AgentArtifact.producing_run_id == run.id))
        if artifact is None:
            artifact = AgentArtifact(
                id=str(uuid4()),
                producing_run_id=run.id,
                kind="evidence_gap_report",
                title="证据缺口报告",
                body_markdown="# 证据缺口报告\n\n" + "\n".join(f"- {item}" for item in missing),
                structured_payload_json=canonical_json({"schema_version": 1, "reason": reason, "gaps": missing}),
                status="final",
                schema_version=1,
                finalized_at=datetime.now(UTC),
            )
            session.add(artifact)
            session.flush()
        run.final_artifact_id = artifact.id
        run.status = RunStatus.INSUFFICIENT_EVIDENCE.value
        run.phase = RunPhase.ASSESS.value
        run.termination_reason = reason
        run.finished_at = datetime.now(UTC)
        if increment_version:
            run.version += 1
        journal = SqlAgentJournal(session)
        journal.append_event(
            run,
            event_type="artifact.published",
            payload={
                "artifact_id": artifact.id,
                "final_artifact_id": artifact.id,
                "title": artifact.title,
                "kind": artifact.kind,
                "status": artifact.status,
            },
        )
        event = journal.append_event(
            run,
            event_type="run.insufficient_evidence",
            payload={"reason": reason, "gaps": missing, "artifact_id": artifact.id},
        )
        session.flush()
        journal.checkpoint(run, event.id if event_cursor is None else max(event.id, event_cursor))
        return self._result(run, applied=True, reason=reason)

    def _fail_search(
        self,
        run_id: str,
        tool_call_id: str,
        *,
        expected_version: int,
        execution_epoch: int,
        error: Exception,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = session.get(AgentRun, run_id)
            tool = session.get(AgentToolCall, tool_call_id)
            if run is None or tool is None:
                raise error
            if run.version != expected_version or run.execution_epoch != execution_epoch:
                tool.status = "abandoned"
                tool.error_code = "execution_fence_changed"
                tool.finished_at = datetime.now(UTC)
                return self._result(run, applied=False, reason="execution_fence_changed")
            tool.status = "failed"
            tool.error_code = type(error).__name__
            tool.finished_at = datetime.now(UTC)
            run.status = RunStatus.FAILED.value
            run.termination_reason = "evidence_search_failed"
            run.finished_at = datetime.now(UTC)
            run.version += 1
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="run.failed",
                payload={"reason": "evidence_search_failed", "error_type": type(error).__name__},
            )
            session.flush()
            journal.checkpoint(run, event.id)
            return self._result(run, applied=True, reason="evidence_search_failed")

    def _fail_evidence_read(
        self,
        run_id: str,
        tool_call_id: str,
        *,
        expected_version: int,
        execution_epoch: int,
        error: Exception,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = session.get(AgentRun, run_id)
            tool = session.get(AgentToolCall, tool_call_id)
            if run is None or tool is None:
                raise error
            if run.version != expected_version or run.execution_epoch != execution_epoch:
                tool.status = "abandoned"
                tool.error_code = "execution_fence_changed"
                tool.finished_at = datetime.now(UTC)
                return self._result(
                    run,
                    applied=False,
                    reason="execution_fence_changed",
                )
            tool.status = "failed"
            tool.error_code = type(error).__name__
            tool.finished_at = datetime.now(UTC)
            run.status = RunStatus.FAILED.value
            run.termination_reason = "evidence_read_failed"
            run.finished_at = datetime.now(UTC)
            run.version += 1
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="run.failed",
                payload={
                    "reason": "evidence_read_failed",
                    "tool": tool.tool_name,
                    "error_type": type(error).__name__,
                },
            )
            session.flush()
            journal.checkpoint(run, event.id)
            return self._result(run, applied=True, reason="evidence_read_failed")

    def _fail_configuration(
        self,
        run_id: str,
        expected_version: int,
        execution_epoch: int,
        *,
        reason: str,
    ) -> AdvanceResult:
        with self._sessions() as session, session.begin():
            run = self._locked_run(session, run_id, expected_version, execution_epoch)
            if run is None:
                return self._stale_result(session, run_id)
            run.status = RunStatus.FAILED.value
            run.termination_reason = reason
            run.finished_at = datetime.now(UTC)
            run.version += 1
            journal = SqlAgentJournal(session)
            event = journal.append_event(
                run,
                event_type="run.failed",
                payload={"reason": reason, "error_code": "LLM_NOT_CONFIGURED"},
            )
            session.flush()
            journal.checkpoint(run, event.id)
            return self._result(run, applied=True, reason=reason)

    def _space_id(self, run_id: str) -> int:
        with self._sessions() as session:
            value = session.scalar(select(AgentRun.space_id).where(AgentRun.id == run_id))
            if value is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            return value

    @staticmethod
    def _reference_payload(evidence: PinnedEvidenceRef) -> dict[str, object]:
        return {
            "source_id": evidence.source_id,
            "revision_id": evidence.revision_id,
            "index_revision_id": evidence.index_revision_id,
            "chunk_id": evidence.chunk_id,
            "content_hash": evidence.content_hash,
            "locator": dict(evidence.locator),
        }

    @staticmethod
    def _revision_ids(run: AgentRun) -> tuple[int, ...]:
        snapshot = json.loads(run.scope_snapshot_json)
        return tuple(int(item["revision_id"]) for item in snapshot.get("revisions", []))

    @staticmethod
    def _select_mode(requested: RunMode, goal: str) -> RunMode:
        if requested is not RunMode.AUTO:
            return requested
        complex_markers = ("比较", "对比", "跨来源", "分别", "冲突", "时间线", ";", "；", "\n")
        return RunMode.FORCE_AGENT if any(marker in goal for marker in complex_markers) else RunMode.FORCE_QUICK

    @staticmethod
    def _requirements(goal: str) -> list[str]:
        parts = [part.strip(" ，,。") for part in re.split(r"[；;\n]+|(?:以及|并且|同时)", goal) if part.strip()]
        unique: list[str] = []
        for part in parts or [goal.strip()]:
            if part and part not in unique:
                unique.append(part)
        return unique[:8]

    @staticmethod
    def _requirement_contexts(
        session: Session,
        run_id: str,
        *,
        include_candidates: bool = False,
    ) -> list[RequirementModelContext]:
        requirements = session.scalars(
            select(AgentRequirement)
            .where(AgentRequirement.run_id == run_id)
            .order_by(AgentRequirement.ordinal)
        ).all()
        contexts: list[RequirementModelContext] = []
        for requirement in requirements:
            evidence_rows = session.execute(
                select(AgentEvidence, RequirementEvidence.relation)
                .join(RequirementEvidence, RequirementEvidence.evidence_id == AgentEvidence.id)
                .where(
                    RequirementEvidence.requirement_id == requirement.id,
                    RequirementEvidence.relation.in_(
                        ["candidate", "contextual", "supports", "contradicts"]
                        if include_candidates
                        else ["supports", "contradicts"]
                    ),
                )
                .order_by(RequirementEvidence.id)
            ).all()
            contexts.append(
                RequirementModelContext(
                    ordinal=requirement.ordinal,
                    text=requirement.text,
                    status=requirement.status,
                    evidence=[
                        EvidenceModelContext(
                            evidence_id=evidence.id,
                            excerpt=evidence.excerpt_preview,
                            relation=relation,
                        )
                        for evidence, relation in evidence_rows
                    ],
                )
            )
        return contexts

    @staticmethod
    def _promote_selected_support(
        session: Session,
        run: AgentRun,
        missing: list[AgentRequirement],
        decision: SufficiencyDecision,
    ) -> list[_EvidenceRelationChange] | None:
        """Admit selected candidates and describe the durable public projection delta."""

        required_by_ordinal = {item.ordinal: item for item in missing}
        selected_by_ordinal = {
            item.requirement_ordinal: item.supporting_evidence_ids
            for item in decision.evidence_selections
        }
        if set(selected_by_ordinal) != set(required_by_ordinal):
            return None

        validated: list[
            tuple[
                AgentRequirement,
                list[RequirementEvidence],
                list[RequirementEvidence],
            ]
        ] = []
        for ordinal, evidence_ids in selected_by_ordinal.items():
            requirement = required_by_ordinal[ordinal]
            if requirement.status != "partial":
                return None
            available_rows = list(
                session.scalars(
                    select(RequirementEvidence)
                    .join(AgentEvidence, AgentEvidence.id == RequirementEvidence.evidence_id)
                    .where(
                        RequirementEvidence.requirement_id == requirement.id,
                        RequirementEvidence.relation.in_(["candidate", "contextual"]),
                        AgentEvidence.run_id == run.id,
                    )
                )
            )
            available_by_id = {row.evidence_id: row for row in available_rows}
            if not set(evidence_ids).issubset(available_by_id):
                return None
            selected_rows = [available_by_id[evidence_id] for evidence_id in evidence_ids]
            excluded_rows = [
                row for row in available_rows if row.evidence_id not in set(evidence_ids)
            ]
            validated.append((requirement, selected_rows, excluded_rows))

        changes: list[_EvidenceRelationChange] = []
        for requirement, selected_rows, excluded_rows in validated:
            for row in selected_rows:
                previous_relation = row.relation
                row.relation = "supports"
                row.method = "model_assessment"
                row.confidence_millis = max(row.confidence_millis or 0, 800)
                row.reason_code = "model_selected_support"
                changes.append(
                    _EvidenceRelationChange(
                        evidence_id=row.evidence_id,
                        requirement_id=requirement.id,
                        requirement_ordinal=requirement.ordinal,
                        previous_relation=previous_relation,
                        relation=row.relation,
                        reason=row.reason_code,
                        method=row.method,
                    )
                )
            for row in excluded_rows:
                previous_relation = row.relation
                row.relation = "excluded"
                row.method = "model_assessment"
                row.confidence_millis = max(row.confidence_millis or 0, 700)
                row.reason_code = "model_not_selected"
                changes.append(
                    _EvidenceRelationChange(
                        evidence_id=row.evidence_id,
                        requirement_id=requirement.id,
                        requirement_ordinal=requirement.ordinal,
                        previous_relation=previous_relation,
                        relation=row.relation,
                        reason=row.reason_code,
                        method=row.method,
                    )
                )
            requirement.status = "covered"
        return changes

    @staticmethod
    def _classify_relations(excerpts: list[str]) -> list[str]:
        """Surface obvious quantitative conflicts without asking a model to set policy state."""

        if not excerpts:
            return []
        pattern = re.compile(
            r"(?<![\w.])(\d+(?:\.\d+)?)\s*(毫秒|ms|秒|s|元|万元|%|％|个|次)",
            re.IGNORECASE,
        )
        unit_aliases = {"毫秒": "ms", "％": "%", "秒": "s"}

        def values(text: str) -> dict[str, str]:
            found: dict[str, str] = {}
            for raw_value, raw_unit in pattern.findall(text):
                unit = unit_aliases.get(raw_unit.lower(), raw_unit.lower())
                found.setdefault(unit, raw_value)
            return found

        baseline = values(excerpts[0])
        relations = ["supports"]
        for excerpt in excerpts[1:]:
            candidate = values(excerpt)
            shared_units = baseline.keys() & candidate.keys()
            conflicts = any(baseline[unit] != candidate[unit] for unit in shared_units)
            relations.append("contradicts" if conflicts else "supports")
            for unit, value in candidate.items():
                baseline.setdefault(unit, value)
        return relations

    @staticmethod
    def _context_hits(hits: tuple[EvidenceHit, ...]) -> tuple[EvidenceHit, ...]:
        """Keep candidates near the retriever's best score without redoing relevance lexically."""

        if not hits:
            return ()
        best_score = max(hit.score for hit in hits)
        if best_score <= 0:
            return ()
        relative_floor = best_score * 0.75
        return tuple(hit for hit in hits if hit.score >= relative_floor)

    @staticmethod
    def _direct_fact_support(query: str, excerpt: str) -> bool:
        """Conservative zero-model coverage proof; semantic candidates stay partial."""

        generic_english = {
            "a",
            "an",
            "and",
            "are",
            "be",
            "can",
            "do",
            "does",
            "how",
            "is",
            "me",
            "of",
            "please",
            "tell",
            "the",
            "what",
        }
        excerpt_folded = excerpt.casefold()
        english_terms = [
            term
            for term in re.findall(r"[a-z0-9_]+", query.casefold())
            if term not in generic_english
        ]
        if english_terms and not all(term in excerpt_folded for term in english_terms):
            return False

        generic_cjk_prefixes = ("请问", "告诉我", "请", "核对", "说明")
        generic_cjk_suffixes = ("是什么", "事实", "多少", "如何")
        cjk_terms: list[str] = []
        for sequence in re.findall(r"[\u4e00-\u9fff]+", query):
            normalized = sequence
            for prefix in generic_cjk_prefixes:
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix) :]
                    break
            for suffix in generic_cjk_suffixes:
                if normalized.endswith(suffix):
                    normalized = normalized[: -len(suffix)]
                    break
            if normalized:
                cjk_terms.append(normalized)
        if cjk_terms and not all(term in excerpt for term in cjk_terms):
            return False
        return bool(english_terms or cjk_terms)

    @staticmethod
    def _claim_literals_supported(claim: str, excerpts: list[str]) -> bool:
        """Reject model claims that introduce checkable literals absent from evidence."""

        evidence_text = "\n".join(excerpts)
        number_pattern = re.compile(r"(?<![0-9A-Za-z])\d+(?:[.,]\d+)?(?![0-9A-Za-z])")

        def normalized_numbers(text: str) -> set[str]:
            return {value.replace(",", "") for value in number_pattern.findall(text)}

        if not normalized_numbers(claim).issubset(normalized_numbers(evidence_text)):
            return False

        proper_pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:[A-Z][A-Za-z0-9]*(?:[._-][A-Za-z0-9]+)*|[A-Z]{2,})(?![A-Za-z0-9])"
        )
        ignored = {"a", "an", "the", "this", "that", "based", "according", "evidence"}
        evidence_folded = evidence_text.casefold()
        proper_names = {
            name.casefold()
            for name in proper_pattern.findall(claim)
            if name.casefold() not in ignored
        }
        if any(name not in evidence_folded for name in proper_names):
            return False

        cjk_titles = re.findall(r"《([^》]{2,80})》", claim)
        return all(title.casefold() in evidence_folded for title in cjk_titles)

    @staticmethod
    def _locked_run(session: Session, run_id: str, version: int, epoch: int) -> AgentRun | None:
        return session.scalar(
            select(AgentRun).where(
                AgentRun.id == run_id,
                AgentRun.version == version,
                AgentRun.execution_epoch == epoch,
            )
        )

    @staticmethod
    def _stale_result(session: Session, run_id: str) -> AdvanceResult:
        run = session.get(AgentRun, run_id)
        if run is None:
            raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
        return AgentRunner._result(run, applied=False, reason="stale_wakeup")

    @staticmethod
    def _result(run: AgentRun, *, applied: bool, reason: str) -> AdvanceResult:
        return AdvanceResult(
            run_id=run.id,
            applied=applied,
            version=run.version,
            status=RunStatus(run.status),
            reason=reason,
        )
