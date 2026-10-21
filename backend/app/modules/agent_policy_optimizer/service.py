"""Study/Trial lifecycle for the V5.4A offline retrieval optimizer.

Durable execution contract (mirrors the V5.2 evaluation control flow):

- submit: idempotent study creation (request_id replay + payload hash).
- start:  pending -> running, generates budgeted trials and outbox messages
          inside one transaction.
- execute: fence-claimed trial run; the write-back is a conditional UPDATE on
          (status, lease_owner) so late workers cannot overwrite fresh results.
- cancel: cancelled studies never spawn new trials; pending trials are cancelled.
- recover: expired leases are taken over atomically; completed results are never
          touched.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationRoundCommand, OptimizationStudy, OptimizationTrial
from app.models.workbench import OptimizationStudyEvent
from app.models.outbox import OutboxMessage
from app.modules.agent_control.executor import EvaluationExecutionError
from app.modules.agent_control.report import (
    EvaluationReportError,
    ValidatedEvaluationReport,
    validate_evaluation_report,
)
from app.modules.agent_policy.config import (
    RetrievalPolicyConfig,
    canonical_policy_json,
    policy_config_from_snapshot,
)
from app.modules.agent_policy_optimizer.contracts import (
    ConvertRecommendation,
    CategoryComparisonView,
    CandidatePolicy,
    ConvertDraftReceipt,
    DiffTrialAgainstActive,
    ExecuteTrial,
    ExportComparison,
    ExportComparisonReceipt,
    FailStudy,
    FailReceipt,
    NextRound,
    NextRoundReceipt,
    OptimizerReadQuery,
    OptimizerReadResult,
    GetOptimizationPareto,
    GetOptimizationRecommendation,
    GetOptimizationStudy,
    GetOptimizationTrial,
    ListOptimizationStudies,
    ListOptimizationTrials,
    OptimizerInputError,
    RecommendationInput,
    RecommendationView,
    RetryTrial,
    RetryReceipt,
    ScoreWeights,
    SearchSpace,
    SearchSpaceBound,
    StudyBudget,
    StudyCatalogView,
    StudyDetailView,
    StudyEventCatalogView,
    StudyMutationReceipt,
    StudyOverviewView,
    StudyTemplateReceipt,
    StudyTemplateCatalogView,
    RecoverOptimizations,
    StudyCommand,
    StudyObjective,
    TrialMetrics,
    TrialCatalogView,
    TrialView,
    DiffView,
    ParetoView,
)
from app.modules.agent_policy_optimizer.bayesian_generation import (
    Observation,
    generate_bayesian_candidates,
)
from app.modules.agent_policy_optimizer.category_analysis import (
    CaseResult,
    deserialize_case_results,
    serialize_case_results,
    summarize_categories,
)
from app.modules.agent_policy.interface import AgentPolicy
from app.modules.agent_policy_optimizer.candidate_generation import generate_candidates
from app.modules.agent_policy_optimizer.comparison_exporter import OptimizerComparisonExporter
from app.modules.agent_policy_optimizer.evaluation_facts import category_facts
from app.modules.agent_policy_optimizer.draft_conversion import OptimizerDraftConverter
from app.modules.agent_policy_optimizer.trial_inspection import OptimizerTrialInspector
from app.modules.agent_policy_optimizer.workbench_projection import OptimizerWorkbenchProjector
from app.modules.agent_policy_optimizer.terminal_commands import OptimizerTerminalCommands
from app.modules.agent_policy_optimizer.internal import (
    CANCELLED_MESSAGE,
    EVENT_RECOMMENDATION_UPDATED,
    EVENT_ROUND_STARTED,
    EVENT_STUDY_CANCELLED,
    EVENT_STUDY_COMPLETED,
    EVENT_STUDY_CREATED,
    EVENT_STUDY_FAILED,
    EVENT_STUDY_STARTED,
    EVENT_TRIAL_CANCELLED,
    EVENT_TRIAL_COMPLETED,
    EVENT_TRIAL_CREATED,
    EVENT_TRIAL_FAILED,
    PolicyServiceFactory,
    TRIAL_TOPIC,
    required_policy,
    lock_study,
    lock_trial_study,
    deadline_reached,
    execution_block_reason,
    effective_deadline,
    required_study,
    required_trial,
)
from app.modules.agent_policy_optimizer.executor import TrialExecutor, TrialPolicySnapshot
from app.modules.agent_policy_optimizer.templates import template_catalog, template_command
from app.modules.agent_policy_optimizer.objectives import normalize_metrics, weighted_score_millis
from app.modules.agent_policy_optimizer.pareto import pareto_frontier, qualify_trial
from app.modules.agent_policy_optimizer.recommendation import build_recommendations
from app.modules.agent_control.sanitization import contains_sensitive_text, sanitize_fact


SessionFactory = Callable[[], Session]
ROUND_BATCH_LIMIT = 3
class SqlAgentPolicyOptimizer:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        lease_seconds: int = 900,
        policy_service_factory: PolicyServiceFactory | None = None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._sessions = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_seconds = lease_seconds
        self._policy_service_factory = policy_service_factory
        self._comparison_exporter = OptimizerComparisonExporter(session_factory)
        self._draft_converter = OptimizerDraftConverter(
            session_factory,
            qualify_rows=self._qualify_rows,
            append_event=self._append_event,
        )
        self._trial_inspector = OptimizerTrialInspector(
            session_factory,
            policy_service=self._policy_service,
            qualify_rows=self._qualify_rows,
        )
        self._workbench_projector = OptimizerWorkbenchProjector(
            session_factory,
            qualify_rows=self._qualify_rows,
            inspect_study=self.inspect_study,
            read_budget=_budget_from_json,
            clock=self._clock,
        )
        self._terminal_commands = OptimizerTerminalCommands(
            session_factory,
            clock=self._clock,
            append_event=self._append_event,
        )

    # ------------------------------------------------------------------ submit

    def submit(self, command: StudyCommand) -> StudyMutationReceipt:
        label = command.label.strip()
        request_id = command.request_id.strip()
        if not request_id or len(request_id) > 120 or contains_sensitive_text(request_id):
            raise ServiceError(
                code="OPTIMIZER_REQUEST_ID_INVALID",
                message="Optimizer request id is blank, too long, or secret-looking.",
                status_code=422,
            )
        if not label or len(label) > 120 or contains_sensitive_text(label):
            raise ServiceError(
                code="OPTIMIZER_LABEL_INVALID",
                message="Optimizer label is blank, too long, or secret-looking.",
                status_code=422,
            )
        try:
            budget = StudyBudget(
                max_candidates=command.max_candidates,
                max_evaluations=command.max_evaluations,
            )
        except OptimizerInputError as exc:
            raise ServiceError(code=exc.code, message=str(exc), status_code=422) from exc
        deadline = _aware(command.deadline_at) if command.deadline_at is not None else None
        payload_hash = _digest(
            {
                "label": label,
                "base_policy_id": command.base_policy_id,
                "objective": command.objective.value,
                "max_candidates": budget.max_candidates,
                "max_evaluations": budget.max_evaluations,
                "search_space": _space_payload(command.search_space),
                "weights": _weights_payload(command.weights),
                "seed": command.seed,
                "warm_start_study_id": command.warm_start_study_id,
            }
        )
        try:
            with self._sessions() as session, session.begin():
                existing = session.scalar(
                    select(OptimizationStudy).where(OptimizationStudy.request_id == request_id)
                )
                if existing is not None:
                    return self._replay_or_conflict(existing, payload_hash, deadline)
                base_policy = required_policy(session, command.base_policy_id)
                warm_start_study: OptimizationStudy | None = None
                warm_snapshot: str | None = None
                if command.warm_start_study_id is not None:
                    warm_start_study = session.get(OptimizationStudy, command.warm_start_study_id)
                    if warm_start_study is None:
                        raise ServiceError(
                            code="OPTIMIZER_WARM_START_NOT_FOUND",
                            message="Warm start study does not exist.",
                            status_code=404,
                        )
                    lock_study(session, warm_start_study.id)
                    parent_trials = session.scalars(select(OptimizationTrial).where(
                        OptimizationTrial.study_id == warm_start_study.id,
                        OptimizationTrial.status == "completed",
                        OptimizationTrial.score_millis.is_not(None),
                    ).order_by(OptimizationTrial.ordinal, OptimizationTrial.id)).all()
                    warm_snapshot = _canonical({
                        "captured_at": self._clock().isoformat(),
                        "observations": [
                            {"config_json": row.config_json, "config_sha256": row.config_sha256,
                             "score_millis": row.score_millis} for row in parent_trials
                        ],
                    })
                study = OptimizationStudy(
                    id=str(uuid4()),
                    request_id=request_id,
                    request_payload_hash=payload_hash,
                    label=label,
                    objective=command.objective.value,
                    status="pending",
                    base_policy_id=base_policy.id,
                    search_space_json=_canonical(_space_payload(command.search_space)),
                    weights_json=_canonical(_weights_payload(command.weights)),
                    budget_json=_canonical(
                        {
                            "max_candidates": budget.max_candidates,
                            "max_evaluations": budget.max_evaluations,
                            **(
                                {"deadline_at": deadline.isoformat()}
                                if deadline is not None
                                else {}
                            ),
                        }
                    ),
                    budget_usage_json=_canonical({"created_trials": 0, "started_evaluations": 0}),
                    seed=command.seed,
                    algorithm_version="v5_6_bayesian_1",
                    base_policy_fingerprint=base_policy.config_sha256,
                    deadline_at=deadline,
                    warm_start_study_id=(
                        command.warm_start_study_id if warm_start_study is not None else None
                    ),
                    round_no=2 if warm_start_study is not None else 1,
                    warm_start_observations_json=warm_snapshot,
                )
                session.add(study)
                session.flush([study])
                self._append_event(
                    session,
                    study,
                    EVENT_STUDY_CREATED,
                    {"objective": study.objective, "seed": study.seed},
                )
                study_id = study.id
                study_status = study.status
            return {"study_id": study_id, "status": study_status, "replayed": False}
        except IntegrityError:
            with self._sessions() as session:
                winner = session.scalar(
                    select(OptimizationStudy).where(OptimizationStudy.request_id == request_id)
                )
                if winner is None:
                    raise
                return self._replay_or_conflict(winner, payload_hash, deadline)

    # ------------------------------------------------------------------- start

    def start(self, study_id: str) -> StudyMutationReceipt:
        now = self._clock()
        with self._sessions() as session, session.begin():
            study = lock_study(session, study_id)
            current_id = study.id
            current_status = study.status
            if current_status == "cancelled":
                return {"study_id": current_id, "status": current_status, "created": 0}
            if current_status in {"completed", "failed"}:
                return {"study_id": current_id, "status": current_status, "created": 0}
            if current_status == "running":
                return {"study_id": current_id, "status": current_status, "created": 0}
            existing_trials = session.scalars(
                select(OptimizationTrial).where(OptimizationTrial.study_id == study.id)
            ).all()
            if existing_trials:
                # A crashed start already produced trials; re-drive completes them.
                study.status = "running"
                study.started_at = study.started_at or now
                study.lease_owner = None
                study.lease_expires_at = None
                return {"study_id": current_id, "status": "running", "created": 0}
            if self._deadline_reached(study, now):
                study.status = "completed"
                study.finished_at = now
                self._append_event(
                    session,
                    study,
                    EVENT_STUDY_COMPLETED,
                    {"reason": "deadline_reached"},
                )
                return {"study_id": current_id, "status": "completed", "created": 0}
            base_policy = required_policy(session, study.base_policy_id)
            base_config = _policy_config(base_policy)
            space = _space_from_json(study.search_space_json)
            budget = _budget_from_json(study.budget_json)
            observations = self._collect_observations(session, study)
            candidate_limit = min(
                budget.max_candidates,
                budget.max_evaluations,
                ROUND_BATCH_LIMIT,
            )
            try:
                if study.round_no > 1 and observations:
                    guided = (
                        generate_bayesian_candidates(
                            base_config,
                            space,
                            round_no=study.round_no,
                            observations=observations,
                            max_candidates=candidate_limit - 1,
                            seed=study.seed,
                        )
                        if candidate_limit > 1
                        else ()
                    )
                    candidates = (
                        CandidatePolicy(
                            ordinal=1,
                            config=base_config,
                            fingerprint=base_policy.config_sha256,
                            is_baseline=True,
                        ),
                        *(
                            CandidatePolicy(
                                ordinal=index + 2,
                                config=item.config,
                                fingerprint=item.fingerprint,
                                is_baseline=False,
                            )
                            for index, item in enumerate(guided)
                        ),
                    )
                else:
                    candidates = generate_candidates(
                        base_config,
                        space,
                        max_candidates=candidate_limit,
                        seed=study.seed,
                    )
            except OptimizerInputError as exc:
                raise ServiceError(
                    code=exc.code,
                    message=str(exc),
                    status_code=409 if exc.code == "OPTIMIZER_SEARCH_SPACE_EXHAUSTED" else 422,
                ) from exc
            study.status = "running"
            study.started_at = now
            session.flush([study])
            self._append_event(
                session,
                study,
                EVENT_STUDY_STARTED if study.round_no == 1 else EVENT_ROUND_STARTED,
                {"planned": len(candidates), "round_no": study.round_no},
            )
            created = 0
            for candidate in candidates:
                if created >= budget.max_evaluations:
                    break
                trial = OptimizationTrial(
                    id=str(uuid4()),
                    study_id=study.id,
                    round_no=study.round_no,
                    ordinal=candidate.ordinal,
                    status="pending",
                    config_sha256=candidate.fingerprint,
                    config_json=canonical_policy_json(candidate.config),
                    is_baseline=1 if candidate.is_baseline else 0,
                    dominated=0,
                    attempt=0,
                )
                session.add(trial)
                session.flush([trial])
                session.add(
                    OutboxMessage(
                        id=str(uuid4()),
                        topic=TRIAL_TOPIC,
                        aggregate_type="optimization_trial",
                        aggregate_id=trial.id,
                        dedupe_key=f"{TRIAL_TOPIC}:{trial.id}",
                        payload_json=_canonical({"trial_id": trial.id, "study_id": study.id}),
                        status="pending",
                    )
                )
                self._append_event(
                    session,
                    study,
                    EVENT_TRIAL_CREATED,
                    {
                        "trial_id": trial.id,
                        "ordinal": trial.ordinal,
                        "config_sha256": trial.config_sha256,
                    },
                )
                created += 1
            prior_usage = json.loads(study.budget_usage_json or "{}")
            usage = {
                "created_trials": int(prior_usage.get("created_trials", 0)) + created,
                "started_evaluations": int(prior_usage.get("started_evaluations", 0)),
            }
            study.budget_usage_json = _canonical(usage)
            session.flush([study])
            return {"study_id": current_id, "status": "running", "created": created}

    # ----------------------------------------------------------------- execute

    def execute(self, command: ExecuteTrial, executor: TrialExecutor) -> TrialView:
        if not command.worker_id.strip():
            raise ValueError("worker_id cannot be empty")
        # Each attempt needs its own fence, even if the same Worker restarts it.
        command = ExecuteTrial(trial_id=command.trial_id, worker_id=f"attempt:{uuid4()}")
        claim = self._claim_trial(command)
        if not claim["claimed"]:
            return self._trial_public_state(claim["trial_id"])
        trial_id = command.trial_id
        snapshot = TrialPolicySnapshot(
            trial_id=trial_id,
            config_sha256=claim["config_sha256"],
            config_json=claim["config_json"],
        )
        try:
            report = validate_evaluation_report(executor.run(trial_id, snapshot))
            if report.policy_fingerprint != snapshot.config_sha256:
                raise EvaluationReportError(
                    "OPTIMIZER_TRIAL_FINGERPRINT_MISMATCH",
                    "The evaluator report does not match the candidate policy fingerprint.",
                )
            if "agent_p95" not in report.latency_ms:
                raise EvaluationReportError(
                    "OPTIMIZER_TRIAL_LATENCY_MISSING",
                    "The evaluator report does not contain the required agent_p95 latency.",
                )
        except EvaluationReportError as exc:
            self._fail_trial(command, code=exc.code)
        except EvaluationExecutionError as exc:
            self._fail_trial(command, code=exc.code)
        except Exception:  # noqa: BLE001 - convert unknown executor faults into bounded state.
            self._fail_trial(command, code="OPTIMIZER_EXECUTOR_FAILED")
        else:
            self._complete_trial(command, report)
        return self._trial_public_state(trial_id)

    def _score_and_recommend(self, session: Session, study: OptimizationStudy) -> None:
        """Persist derived facts in the same transaction as Trial completion."""
        if study.status in {"cancelled", "failed"}:
            return
        trials = session.scalars(select(OptimizationTrial).where(
            OptimizationTrial.study_id == study.id, OptimizationTrial.status == "completed"
        )).all()
        normalized = self._normalized_for_rows(trials)
        weights = _weights_from_json(study.weights_json)
        for trial in trials:
            if trial.id in normalized:
                trial.normalized_metrics_json = _canonical(normalized[trial.id])
                trial.score_millis = weighted_score_millis(normalized[trial.id], weights)
        session.flush()
        self._recommendation_for_session(session, study, persist=True)

    def write_back(
        self,
        *,
        trial_id: str,
        worker_id: str,
        report: dict[str, object],
        completed_at: datetime,
    ) -> bool:
        """Fenced completion path used by recovery tooling; never overwrites a
        result written by a different (fresh) worker."""

        with self._sessions() as session:
            trial = required_trial(session, trial_id)
            if trial.status != "running" or trial.lease_owner != worker_id:
                return False
            expected_fingerprint = trial.config_sha256
        validated = validate_evaluation_report(report)
        if validated.policy_fingerprint != expected_fingerprint:
            raise EvaluationReportError(
                "OPTIMIZER_TRIAL_FINGERPRINT_MISMATCH",
                "The evaluator report does not match the candidate policy fingerprint.",
            )
        if "agent_p95" not in validated.latency_ms:
            raise EvaluationReportError(
                "OPTIMIZER_TRIAL_LATENCY_MISSING",
                "The evaluator report does not contain the required agent_p95 latency.",
            )
        completed = self._complete_trial(
            ExecuteTrial(trial_id=trial_id, worker_id=worker_id),
            validated,
            finished_at=completed_at,
        )
        return completed

    # ------------------------------------------------------------------ cancel

    def cancel(self, study_id: str) -> StudyMutationReceipt:
        now = self._clock()
        with self._sessions() as session, session.begin():
            study = lock_study(session, study_id)
            current_id = study.id
            current_status = study.status
            if current_status not in {"pending", "running"}:
                return {"study_id": current_id, "status": current_status, "cancelled": False}
            study.status = "cancelled"
            study.cancelled_at = now
            study.finished_at = now
            cancelled_trials = session.scalars(
                select(OptimizationTrial).where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.status == "pending",
                )
            ).all()
            session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.status == "pending",
                )
                .values(
                    status="cancelled",
                    failure_code="OPTIMIZER_STUDY_CANCELLED",
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.aggregate_id.in_(
                        select(OptimizationTrial.id).where(OptimizationTrial.study_id == study.id)
                    ),
                    OutboxMessage.topic == TRIAL_TOPIC,
                    OutboxMessage.status.in_(["pending", "publishing"]),
                )
                .values(status="dead_letter", last_error=CANCELLED_MESSAGE)
                .execution_options(synchronize_session=False)
            )
            for trial in cancelled_trials:
                self._append_event(
                    session,
                    study,
                    EVENT_TRIAL_CANCELLED,
                    {"trial_id": trial.id, "ordinal": trial.ordinal},
                )
            self._append_event(session, study, EVENT_STUDY_CANCELLED, {})
            return {"study_id": current_id, "status": "cancelled", "cancelled": True}

    # ----------------------------------------------------------------- recover

    def recover(self, command: RecoverOptimizations) -> int:
        """Reconcile expired attempts and dispatch failures within the requested scope."""
        with self._sessions() as session:
            query = select(OptimizationStudy.id).where(
                OptimizationStudy.status.in_(["running", "cancelled", "failed"])
            )
            if command.study_id is not None:
                required_study(session, command.study_id)
                query = query.where(OptimizationStudy.id == command.study_id)
            study_ids = session.scalars(query.order_by(OptimizationStudy.id)).all()
        recovered = 0
        for study_id in study_ids:
            with self._sessions() as session, session.begin():
                study = lock_study(session, study_id)
                trials = session.scalars(select(OptimizationTrial).where(
                    OptimizationTrial.study_id == study_id,
                    OptimizationTrial.status.in_(["pending", "running"]),
                ).order_by(OptimizationTrial.ordinal)).all()
                for trial in trials:
                    message = session.scalar(select(OutboxMessage).where(
                        OutboxMessage.aggregate_id == trial.id, OutboxMessage.topic == TRIAL_TOPIC
                    ))
                    expired = trial.status == "running" and trial.lease_expires_at is not None and (
                        _aware(trial.lease_expires_at) <= command.now
                    )
                    if trial.status == "pending" and message is not None and message.status == "dead_letter":
                        trial.status = "failed"
                        trial.failure_code = "OPTIMIZER_DISPATCH_DEAD_LETTER"
                        trial.finished_at = command.now
                        self._append_event(session, study, EVENT_TRIAL_FAILED, {
                            "trial_id": trial.id, "ordinal": trial.ordinal, "failure_code": trial.failure_code
                        })
                    elif expired:
                        reason = execution_block_reason(study, command.now)
                        trial.lease_owner = None
                        trial.lease_expires_at = None
                        if reason is not None:
                            trial.status = "cancelled"
                            trial.failure_code = reason
                            trial.finished_at = command.now
                            self._append_event(session, study, EVENT_TRIAL_CANCELLED,
                                               {"trial_id": trial.id, "ordinal": trial.ordinal})
                        else:
                            trial.status = "pending"
                            trial.failure_code = None
                            if message is None:
                                message = OutboxMessage(
                                    id=str(uuid4()), topic=TRIAL_TOPIC, aggregate_type="optimization_trial",
                                    aggregate_id=trial.id, dedupe_key=f"{TRIAL_TOPIC}:{trial.id}",
                                    payload_json=_canonical({"trial_id": trial.id, "study_id": study.id}),
                                )
                                session.add(message)
                            message.status = "pending"
                            message.attempt = 0
                            message.available_at = command.now
                            message.lease_owner = None
                            message.lease_expires_at = None
                            message.published_at = None
                            message.last_error = None
                            recovered += 1
                if execution_block_reason(study, command.now) is not None:
                    self._cancel_pending_for_limit(
                        session, study, command.now, execution_block_reason(study, command.now)
                    )
                session.flush()
                self._maybe_settle(session, study, command.now)
        return recovered

    # ----------------------------------------------------------------- inspect

    def inspect(self, query: OptimizerReadQuery) -> OptimizerReadResult:
        if isinstance(query, ListOptimizationStudies):
            return self._list_studies(query)
        if isinstance(query, GetOptimizationStudy):
            return self.inspect_study(query.study_id)
        if isinstance(query, ListOptimizationTrials):
            return self._list_trials(query)
        if isinstance(query, GetOptimizationTrial):
            return self.inspect_trial(query.trial_id)
        if isinstance(query, GetOptimizationPareto):
            return self.inspect_pareto(query.study_id)
        if isinstance(query, GetOptimizationRecommendation):
            return self.inspect_recommendation(query.study_id)
        if isinstance(query, DiffTrialAgainstActive):
            return self.diff_trial_against_active(query.study_id, query.trial_id)
        raise TypeError(f"Unsupported optimizer query: {type(query).__name__}")

    def inspect_study(self, study_id: str) -> StudyDetailView:
        with self._sessions() as session:
            study = required_study(session, study_id)
            return {
                "id": study.id,
                "request_id": study.request_id,
                "label": sanitize_fact(study.label, maximum_length=120),
                "objective": study.objective,
                "status": study.status,
                "base_policy_id": study.base_policy_id,
                "base_policy_fingerprint": study.base_policy_fingerprint,
                "search_space": json.loads(study.search_space_json),
                "weights": json.loads(study.weights_json),
                "budget": json.loads(study.budget_json),
                "budget_usage": json.loads(study.budget_usage_json),
                "seed": study.seed,
                "algorithm_version": study.algorithm_version,
                "round_no": study.round_no,
                "warm_start_study_id": study.warm_start_study_id,
                "next_round_request_id": study.next_round_request_id,
                "created_at": _aware(study.created_at).isoformat(),
                "started_at": _aware(study.started_at).isoformat() if study.started_at else None,
                "finished_at": _aware(study.finished_at).isoformat() if study.finished_at else None,
                "cancelled_at": _aware(study.cancelled_at).isoformat() if study.cancelled_at else None,
            }

    def inspect_trial(self, trial_id: str) -> TrialView:
        return self._trial_public_state(trial_id)

    def list_studies(self, *, limit: int, status: str | None = None) -> StudyCatalogView:
        return self._list_studies(ListOptimizationStudies(limit=limit, status=status))

    def list_trials(
        self, study_id: str, *, limit: int, status: str | None = None
    ) -> TrialCatalogView:
        return self._list_trials(
            ListOptimizationTrials(study_id=study_id, limit=limit, status=status)
        )

    def _list_studies(self, query: ListOptimizationStudies) -> StudyCatalogView:
        with self._sessions() as session:
            statement = select(OptimizationStudy).order_by(
                OptimizationStudy.created_at.desc(), OptimizationStudy.id.desc()
            )
            if query.status is not None:
                statement = statement.where(OptimizationStudy.status == query.status)
            rows = session.scalars(statement.limit(max(1, min(query.limit, 100)))).all()
            return {
                "items": [
                    {
                        "id": row.id,
                        "label": sanitize_fact(row.label, maximum_length=120),
                        "objective": row.objective,
                        "status": row.status,
                        "base_policy_fingerprint": row.base_policy_fingerprint,
                        "budget_usage": json.loads(row.budget_usage_json),
                        "created_at": _aware(row.created_at).isoformat(),
                    }
                    for row in rows
                ]
            }

    def _list_trials(self, query: ListOptimizationTrials) -> TrialCatalogView:
        with self._sessions() as session:
            statement = select(OptimizationTrial).where(OptimizationTrial.study_id == query.study_id)
            if query.status is not None:
                statement = statement.where(OptimizationTrial.status == query.status)
            rows = session.scalars(
                statement.order_by(OptimizationTrial.ordinal.asc()).limit(max(1, min(query.limit, 200)))
            ).all()
            return {"items": [self._trial_public_state(row.id) for row in rows]}

    def inspect_pareto(self, study_id: str) -> ParetoView:
        with self._sessions() as session:
            study = required_study(session, study_id)
            trials = session.scalars(
                select(OptimizationTrial).where(OptimizationTrial.study_id == study.id)
            ).all()
            rows = self._qualify_rows(session, trials)
            frontier = pareto_frontier(row for row, _ in rows)
            return {
                "study_id": study.id,
                "items": [
                    {
                        "trial_id": item.trial_id,
                        "ordinal": item.ordinal,
                        "score_millis": item.score_millis,
                        "eligible": item.eligible,
                        "config_sha256": item.policy_fingerprint,
                        "metrics": item.metrics.as_dict() if item.metrics else None,
                    }
                    for item in frontier
                ],
            }

    def inspect_recommendation(self, study_id: str) -> RecommendationView:
        with self._sessions() as session:
            study = required_study(session, study_id)
            return self._recommendation_for_session(session, study, persist=False)

    def _recommendation_for_session(
        self, session: Session, study: OptimizationStudy, *, persist: bool
    ) -> RecommendationView:
        trials = session.scalars(
            select(OptimizationTrial).where(OptimizationTrial.study_id == study.id).order_by(
                OptimizationTrial.ordinal.asc()
            )
        ).all()
        rows = self._qualify_rows(session, trials)
        frontier = pareto_frontier(row for row, _ in rows)
        if persist:
            self._persist_frontier_flags(session, trials, frontier)
        inputs = self._recommendation_inputs(session, rows)
        if not inputs:
            return {
                "study_id": study.id,
                "algorithm_version": "v5_6_bayesian_1",
                "candidates": [],
            }
        baseline_input = next(
            (item for item in inputs if item.trial_id == _trial_id_of(rows, 1)),
            None,
        )
        if baseline_input is None or study.status in {"cancelled", "failed"}:
            return {"study_id": study.id, "algorithm_version": study.algorithm_version, "candidates": []}
        candidate_inputs = tuple(
            item
            for item in inputs
            if item.trial_id != baseline_input.trial_id and item.trial_id in {f.trial_id for f in frontier}
        )
        bundle = build_recommendations(
            study_id=study.id,
            objective=StudyObjective(study.objective),
            weights=_weights_from_json(study.weights_json),
            baseline=baseline_input,
            candidates=candidate_inputs,
            frontier_trial_ids=frozenset(item.trial_id for item in frontier),
        )
        if persist:
            self._persist_recommendations(session, bundle)

        baseline_row = session.scalars(
            select(OptimizationTrial).where(
                OptimizationTrial.study_id == study.id,
                OptimizationTrial.ordinal == 1,
            )
        ).first()

        candidates_payload = []
        for item in bundle.candidates:
            candidate_row = session.get(OptimizationTrial, item.trial_id)
            summary_sentence = ""
            baseline_facts = category_facts(session, baseline_row) if baseline_row is not None else None
            candidate_facts = category_facts(session, candidate_row) if candidate_row is not None else None
            if baseline_facts is not None and candidate_facts is not None:
                summary = summarize_categories(
                    deserialize_case_results(baseline_facts),
                    deserialize_case_results(candidate_facts),
                )
                summary_sentence = summary["sentence"]
            rationale = item.rationale
            if summary_sentence:
                rationale = f"{rationale} {summary_sentence}"
            candidates_payload.append(
                {
                    "rank": item.rank,
                    "trial_id": item.trial_id,
                    "policy_fingerprint": item.policy_fingerprint,
                    "policy_snapshot_json": item.policy_snapshot_json,
                    "evaluation_id": item.evaluation_id,
                    "evaluation_fingerprint": item.evaluation_fingerprint,
                    "evaluation_report_sha256": item.evaluation_report_sha256,
                    "score_millis": item.score_millis,
                    "dominates_baseline": item.dominates_baseline,
                    "improved_metrics": list(item.improved_metrics),
                    "unchanged_metrics": list(item.unchanged_metrics),
                    "regressed_metrics": list(item.regressed_metrics),
                    "rationale": rationale,
                    "algorithm_version": item.algorithm_version,
                }
            )
        return {
            "study_id": study.id,
            "algorithm_version": bundle.algorithm_version,
            "candidates": candidates_payload,
        }

    # ----------------------------------------------------- v5.7 workbench

    def _append_event(
        self,
        session: Session,
        study: OptimizationStudy,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Append one lifecycle event row inside the caller's transaction.

        Event payloads carry identifiers, counts, and fingerprints only; any
        free-text reason must be sanitized by the caller before reaching here.
        Events share the caller's transaction: an invalid event rolls back
        together with the state change it describes (all-or-nothing).
        """

        moment = self._clock()
        latest = session.scalar(
            select(func.max(OptimizationStudyEvent.created_at)).where(
                OptimizationStudyEvent.study_id == study.id
            )
        )
        if latest is not None:
            latest_aware = _aware(latest)
            if moment <= latest_aware:
                moment = latest_aware + timedelta(microseconds=1)
        session.add(
            OptimizationStudyEvent(
                id=str(uuid4()),
                study_id=study.id,
                event_type=event_type,
                round_no=study.round_no,
                payload_json=_canonical(payload or {}),
                created_at=moment,
            )
        )

    def create_from_template(
        self,
        *,
        request_id: str,
        label: str,
        base_policy_id: str,
        template_key: str,
        seed: int | None,
        max_candidates: int | None,
        max_evaluations: int | None,
        warm_start_study_id: str | None,
    ) -> StudyTemplateReceipt:
        try:
            command = template_command(
                request_id=request_id,
                label=label,
                base_policy_id=base_policy_id,
                template_key=template_key,
                seed=seed,
                max_candidates=max_candidates,
                max_evaluations=max_evaluations,
                warm_start_study_id=warm_start_study_id,
            )
        except OptimizerInputError as exc:
            raise ServiceError(code=exc.code, message=str(exc), status_code=404 if exc.code == "OPTIMIZER_TEMPLATE_NOT_FOUND" else 422) from exc
        receipt = self.submit(command)
        # The study_created event is written by submit(); templates are
        # deliberately not re-logged to avoid duplicate lifecycle rows.
        return {**receipt, "template_key": template_key}

    def list_templates(self) -> StudyTemplateCatalogView:
        return template_catalog()

    def inspect_events(
        self, study_id: str, *, limit: int = 100, after: str | None = None
    ) -> StudyEventCatalogView:
        return self._workbench_projector.inspect_events(
            study_id, limit=limit, after=after
        )

    def inspect_overview(self, study_id: str) -> StudyOverviewView:
        return self._workbench_projector.inspect_overview(study_id)

    def export_comparison(self, command: "ExportComparison") -> ExportComparisonReceipt:
        return self._comparison_exporter.export(command)

    # ------------------------------------------------------ v5.6 next round

    def start_next_round(self, command: NextRound) -> NextRoundReceipt:
        """Append a Bayesian-guided round of trials to a completed study.

        Idempotent per request_id; honors the study's total budgets and
        continues the ordinal sequence without collisions.
        """

        request_id = command.request_id.strip()
        if not request_id or len(request_id) > 120 or contains_sensitive_text(request_id):
            raise ServiceError(
                code="OPTIMIZER_REQUEST_ID_INVALID",
                message="Next-round request id is blank, too long, or secret-looking.",
                status_code=422,
            )
        now = self._clock()
        try:
            with self._sessions() as session, session.begin():
                study = lock_study(session, command.study_id)
                current_id = study.id
                replay = session.scalar(
                    select(OptimizationRoundCommand).where(
                        OptimizationRoundCommand.request_id == request_id
                    )
                )
                if replay is not None:
                    if replay.study_id != study.id:
                        raise ServiceError(
                            code="OPTIMIZER_IDEMPOTENCY_CONFLICT",
                            message="Next-round request id belongs to another Study.",
                            status_code=409,
                        )
                    return {**json.loads(replay.receipt_json), "replayed": True}
                if study.status != "completed":
                    raise ServiceError(
                        code="OPTIMIZER_STUDY_NOT_COMPLETED",
                        message="Only a completed study can start a next round.",
                        status_code=409,
                    )
                if self._deadline_reached(study, now):
                    raise ServiceError(code="OPTIMIZER_DEADLINE_REACHED",
                                       message="Study deadline has passed.", status_code=409)
                budget = _budget_from_json(study.budget_json)
                usage = json.loads(study.budget_usage_json)
                started_total = int(usage.get("started_evaluations", 0))
                created_total = int(
                    session.scalar(
                        select(func.count(OptimizationTrial.id)).where(
                            OptimizationTrial.study_id == study.id
                        )
                    )
                    or 0
                )
                remaining_slots = min(
                    ROUND_BATCH_LIMIT,
                    budget.max_candidates - created_total,
                    budget.max_evaluations - started_total,
                )
                if remaining_slots <= 0:
                    raise ServiceError(
                        code="OPTIMIZER_BUDGET_EXHAUSTED",
                        message="Study budgets are exhausted; no next round can be created.",
                        status_code=409,
                    )
                base_policy = required_policy(session, study.base_policy_id)
                base_config = _policy_config(base_policy)
                space = _space_from_json(study.search_space_json)
                observations = self._collect_observations(session, study)
                next_round_no = study.round_no + 1
                attempted = frozenset(session.scalars(select(OptimizationTrial.config_sha256).where(
                    OptimizationTrial.study_id == study.id
                )).all())
                if not observations:
                    raise ServiceError(code="OPTIMIZER_OBSERVATIONS_UNAVAILABLE",
                                       message="Completed observations are required for a new round.", status_code=409)
                try:
                    candidates = generate_bayesian_candidates(
                        base_config,
                        space,
                        round_no=next_round_no,
                        observations=observations,
                        max_candidates=remaining_slots,
                        seed=(study.seed + next_round_no) % 2_147_483_648,
                        excluded_fingerprints=attempted,
                    )
                except OptimizerInputError as exc:
                    raise ServiceError(
                        code=exc.code,
                        message=str(exc),
                        status_code=(
                            409 if exc.code == "OPTIMIZER_SEARCH_SPACE_EXHAUSTED" else 422
                        ),
                    ) from exc
                max_ordinal = session.scalar(
                    select(func.max(OptimizationTrial.ordinal)).where(
                        OptimizationTrial.study_id == study.id
                    )
                )
                next_ordinal = int(max_ordinal or 0)
                study.round_no = next_round_no
                study.next_round_request_id = request_id
                study.status = "running"
                study.started_at = study.started_at or now
                study.finished_at = None
                session.flush([study])
                self._append_event(
                    session,
                    study,
                    EVENT_ROUND_STARTED,
                    {"round_no": next_round_no, "planned": len(candidates)},
                )
                created = 0
                for candidate in candidates:
                    next_ordinal += 1
                    trial = OptimizationTrial(
                        id=str(uuid4()),
                        study_id=study.id,
                        ordinal=next_ordinal,
                        status="pending",
                        config_sha256=candidate.fingerprint,
                        config_json=canonical_policy_json(candidate.config),
                        is_baseline=1 if candidate.is_baseline else 0,
                        dominated=0,
                        attempt=0,
                        round_no=next_round_no,
                    )
                    session.add(trial)
                    session.flush([trial])
                    session.add(
                        OutboxMessage(
                            id=str(uuid4()),
                            topic=TRIAL_TOPIC,
                            aggregate_type="optimization_trial",
                            aggregate_id=trial.id,
                            dedupe_key=f"{TRIAL_TOPIC}:{trial.id}",
                            payload_json=_canonical({"trial_id": trial.id, "study_id": study.id}),
                            status="pending",
                        )
                    )
                    self._append_event(
                        session,
                        study,
                        EVENT_TRIAL_CREATED,
                        {
                            "trial_id": trial.id,
                            "ordinal": trial.ordinal,
                            "config_sha256": trial.config_sha256,
                        },
                    )
                    created += 1
                usage["created_trials"] = created_total + created
                study.budget_usage_json = _canonical(usage)
                session.flush([study])
                receipt = {
                    "study_id": current_id,
                    "round_no": next_round_no,
                    "created": created,
                    "replayed": False,
                }
                session.add(
                    OptimizationRoundCommand(
                        id=str(uuid4()),
                        study_id=study.id,
                        request_id=request_id,
                        round_no=next_round_no,
                        created_count=created,
                        receipt_json=_canonical(receipt),
                    )
                )
                return receipt
        except IntegrityError as exc:
            with self._sessions() as replay_session:
                replay = replay_session.scalar(
                    select(OptimizationRoundCommand).where(
                        OptimizationRoundCommand.request_id == request_id
                    )
                )
                if replay is not None and replay.study_id == command.study_id:
                    return {**json.loads(replay.receipt_json), "replayed": True}
            raise ServiceError(
                code="OPTIMIZER_NEXT_ROUND_CONFLICT",
                message="Concurrent next-round creation conflicted; retry with a fresh request id.",
                status_code=409,
            ) from exc

    # ------------------------------------------------------- v5.5 closed loop

    def convert_to_draft(self, command: ConvertRecommendation) -> ConvertDraftReceipt:
        return self._draft_converter.convert(command)

    def inspect_categories(self, study_id: str, trial_id: str) -> CategoryComparisonView:
        return self._trial_inspector.inspect_categories(study_id, trial_id)

    def diff_trial_against_active(self, study_id: str, trial_id: str) -> DiffView:
        return self._trial_inspector.diff_against_active(study_id, trial_id)

    def retry_trial(self, command: RetryTrial) -> RetryReceipt:
        return self._terminal_commands.retry_trial(command)

    def fail_study(self, command: FailStudy) -> FailReceipt:
        return self._terminal_commands.fail_study(command)

    # ---------------------------------------------------------------- internals

    def _claim_trial(self, command: ExecuteTrial) -> dict[str, object]:
        now = self._clock()
        with self._sessions() as session, session.begin():
            study = lock_trial_study(session, command.trial_id)
            trial = session.get(OptimizationTrial, command.trial_id)
            if trial is None:
                raise ServiceError(code="OPTIMIZER_TRIAL_NOT_FOUND", message="Trial not found.", status_code=404)
            if trial.status != "pending":
                return {"claimed": False, "trial_id": trial.id, "status": trial.status,
                        "config_sha256": trial.config_sha256, "config_json": trial.config_json}
            blocked = execution_block_reason(study, now)
            if blocked is not None:
                self._cancel_pending_for_limit(session, study, now, blocked)
                session.refresh(trial)
                self._maybe_settle(session, study, now)
                return {"claimed": False, "trial_id": trial.id, "status": trial.status,
                        "config_sha256": trial.config_sha256, "config_json": trial.config_json}
            result = session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.id == trial.id,
                    OptimizationTrial.status == "pending",
                )
                .values(
                    status="running",
                    attempt=OptimizationTrial.attempt + 1,
                    lease_owner=command.worker_id,
                    lease_expires_at=now + timedelta(seconds=self._lease_seconds),
                    started_at=now,
                    failure_code=None,
                )
                .execution_options(synchronize_session=False)
            )
            claimed = result.rowcount == 1
            session.flush()
            session.refresh(trial)
            usage_study = session.get(OptimizationStudy, trial.study_id)
            if usage_study is not None and claimed:
                usage = json.loads(usage_study.budget_usage_json)
                usage["started_evaluations"] = int(usage.get("started_evaluations", 0)) + 1
                usage_study.budget_usage_json = _canonical(usage)
            return {
                "claimed": claimed,
                "trial_id": trial.id,
                "status": trial.status,
                "config_sha256": trial.config_sha256,
                "config_json": trial.config_json,
            }

    def _complete_trial(
        self,
        command: ExecuteTrial,
        report: ValidatedEvaluationReport,
        *,
        finished_at: datetime | None = None,
    ) -> bool:
        now = finished_at or self._clock()
        with self._sessions() as session, session.begin():
            lock_trial_study(session, command.trial_id)
            trial = session.get(OptimizationTrial, command.trial_id)
            if trial is None:
                return False
            study = session.get(OptimizationStudy, trial.study_id)
            if study is None:
                return False
            # Fence first: only the worker that still owns the running lease may
            # persist a result. Late workers from an earlier lease or duplicate
            # deliveries hit rowcount 0 and never write anything.
            claim_update = session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.id == trial.id,
                    OptimizationTrial.status == "running",
                    OptimizationTrial.lease_owner == command.worker_id,
                )
                .values(status="completing")
                .execution_options(synchronize_session=False)
            )
            if claim_update.rowcount != 1:
                return False
            evaluation = AgentEvaluation(
                id=str(uuid4()),
                request_id=f"optimizer-trial:{trial.id}",
                request_payload_hash=_digest({"trial_id": trial.id, "config": trial.config_sha256}),
                label=f"Optimizer trial {trial.ordinal} for study {study.label[:60]}",
                mode="deterministic_recording",
                status="passed" if report.status == "passed" else "failed",
                schema_version=report.schema_version,
                policy_fingerprint=trial.config_sha256,
                policy_snapshot_json=trial.config_json,
                dataset_name=report.dataset_name,
                dataset_path=report.dataset_path,
                dataset_sha256=report.dataset_sha256,
                evaluator_sha256=report.evaluator_sha256,
                report_sha256=report.report_sha256,
                case_count=report.case_count,
                case_pass_rate_millis=round(float(report.metrics["case_pass_rate"]) * 1_000),
                external_provider_calls=report.external_provider_calls,
                failure_case_count=len(report.failure_case_ids),
                category_counts_json=_canonical(report.category_counts),
                metrics_json=_canonical({**report.metrics, "latency_ms": report.latency_ms}),
                hard_gates_json=_canonical(report.hard_gates),
                failure_case_ids_json=_canonical(list(report.failure_case_ids)),
                report_json=report.canonical_json,
                provider_boundary=report.provider_boundary,
                error_code=None if report.status == "passed" else "EVALUATION_GATE_FAILED",
                error_message=None if report.status == "passed" else "One or more fixed quality gates failed.",
                attempt=1,
            )
            session.add(evaluation)
            session.flush([evaluation])
            metrics = _trial_metrics_from_report(report, trial)
            result = session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.id == trial.id,
                    OptimizationTrial.status == "completing",
                    OptimizationTrial.lease_owner == command.worker_id,
                )
                .values(
                    status="completed",
                    evaluation_id=evaluation.id,
                    metrics_json=_canonical(metrics.as_dict()),
                    category_stats_json=_canonical(_category_stats_from_report(report)),
                    external_provider_calls=report.external_provider_calls,
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                return False
            session.expire(trial)
            self._append_event(
                session,
                study,
                EVENT_TRIAL_COMPLETED,
                {"trial_id": trial.id, "ordinal": trial.ordinal},
            )
            self._maybe_settle(session, study, now)
            self._score_and_recommend(session, study)
            return True

    def _fail_trial(self, command: ExecuteTrial, *, code: str) -> bool:
        now = self._clock()
        with self._sessions() as session, session.begin():
            lock_trial_study(session, command.trial_id)
            result = session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.id == command.trial_id,
                    OptimizationTrial.status == "running",
                    OptimizationTrial.lease_owner == command.worker_id,
                )
                .values(
                    status="failed",
                    failure_code=sanitize_fact(code, maximum_length=80),
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                return False
            trial = session.get(OptimizationTrial, command.trial_id)
            study = session.get(OptimizationStudy, trial.study_id) if trial else None
            if study is not None:
                self._append_event(
                    session,
                    study,
                    EVENT_TRIAL_FAILED,
                    {
                        "trial_id": trial.id,
                        "ordinal": trial.ordinal,
                        "failure_code": sanitize_fact(code, maximum_length=80),
                    },
                )
                self._maybe_settle(session, study, now)
            return True

    def _trial_public_state(self, trial_id: str) -> TrialView:
        with self._sessions() as session:
            trial = session.get(OptimizationTrial, trial_id)
            if trial is None:
                raise ServiceError(code="OPTIMIZER_TRIAL_NOT_FOUND", message="Trial not found.", status_code=404)
            return {
                "id": trial.id,
                "study_id": trial.study_id,
                "ordinal": trial.ordinal,
                "status": trial.status,
                "config_sha256": trial.config_sha256,
                "is_baseline": bool(trial.is_baseline),
                "evaluation_id": trial.evaluation_id,
                "draft_policy_id": trial.draft_policy_id,
                "category_stats": category_facts(session, trial),
                "round_no": trial.round_no,
                "metrics": json.loads(trial.metrics_json) if trial.metrics_json else None,
                "normalized_metrics": (
                    json.loads(trial.normalized_metrics_json) if trial.normalized_metrics_json else None
                ),
                "score_millis": trial.score_millis,
                "recommendation_rank": trial.recommendation_rank,
                "failure_code": trial.failure_code,
                "attempt": trial.attempt,
                "external_provider_calls": trial.external_provider_calls,
                "created_at": _aware(trial.created_at).isoformat(),
                "finished_at": _aware(trial.finished_at).isoformat() if trial.finished_at else None,
            }

    def _qualify_rows(self, session: Session, trials: list[OptimizationTrial]):
        evaluation_ids = [trial.evaluation_id for trial in trials if trial.evaluation_id]
        evaluations = {
            row.id: row
            for row in session.scalars(
                select(AgentEvaluation).where(AgentEvaluation.id.in_(evaluation_ids))
            ).all()
        } if evaluation_ids else {}
        rows = []
        for trial in trials:
            evaluation = evaluations.get(trial.evaluation_id) if trial.evaluation_id else None
            hard_gates = None
            metrics = None
            if evaluation is not None and evaluation.status == "passed":
                try:
                    report = validate_evaluation_report(json.loads(evaluation.report_json or "{}"))
                    cached_gates = json.loads(evaluation.hard_gates_json or "{}")
                    if (
                        report.report_sha256 == evaluation.report_sha256
                        and report.policy_fingerprint == trial.config_sha256
                        and evaluation.policy_fingerprint == trial.config_sha256
                        and cached_gates == report.hard_gates
                        and report.status == "passed"
                    ):
                        hard_gates = report.hard_gates
                        metrics = _trial_metrics_from_report(report, trial)
                except (EvaluationReportError, OptimizerInputError, ValueError, TypeError, KeyError):
                    pass  # Incomplete/corrupt reports are visible but never recommendation-eligible.
            rows.append(
                (
                    qualify_trial(
                        trial_id=trial.id,
                        study_id=trial.study_id,
                        ordinal=trial.ordinal,
                        status=trial.status,
                        evaluation_status=evaluation.status if evaluation is not None else None,
                        hard_gates=hard_gates,
                        external_provider_calls=(
                            evaluation.external_provider_calls if evaluation is not None else None
                        ),
                        failure_case_count=(
                            evaluation.failure_case_count if evaluation is not None else None
                        ),
                        policy_fingerprint=trial.config_sha256,
                        evaluation_fingerprint=(
                            evaluation.policy_fingerprint if evaluation is not None else None
                        ),
                        metrics=metrics,
                        score_millis=trial.score_millis,
                    ),
                    trial,
                )
            )
        return rows

    def _recommendation_inputs(self, session: Session, rows) -> list[RecommendationInput]:
        inputs: list[RecommendationInput] = []
        for row, trial in sorted(rows, key=lambda item: item[1].ordinal):
            if not row.eligible or row.metrics is None or trial.evaluation_id is None:
                continue
            evaluation = session.get(AgentEvaluation, trial.evaluation_id)
            if evaluation is None or evaluation.report_sha256 is None:
                continue
            inputs.append(
                RecommendationInput(
                    study_id=trial.study_id,
                    trial_id=trial.id,
                    ordinal=trial.ordinal,
                    policy_fingerprint=trial.config_sha256,
                    policy_snapshot_json=trial.config_json,
                    evaluation_id=trial.evaluation_id,
                    evaluation_fingerprint=row.evaluation_fingerprint or "",
                    evaluation_report_sha256=evaluation.report_sha256,
                    metrics=row.metrics,
                    score_millis=trial.score_millis or 0,
                )
            )
        return inputs

    def _normalized_for_rows(self, rows: list[OptimizationTrial]) -> dict[str, dict[str, float]]:
        metrics_rows: list[TrialMetrics] = []
        row_ids: list[str] = []
        for row in rows:
            if row.metrics_json:
                try:
                    metrics_rows.append(TrialMetrics(**json.loads(row.metrics_json)))
                    row_ids.append(row.id)
                except (OptimizerInputError, TypeError, json.JSONDecodeError):
                    continue
        normalized_list = normalize_metrics(metrics_rows)
        return dict(zip(row_ids, normalized_list, strict=True))

    def _persist_frontier_flags(self, session: Session, trials: list[OptimizationTrial], frontier) -> None:
        frontier_ids = {item.trial_id for item in frontier}
        for trial in trials:
            trial.dominated = 0 if trial.id in frontier_ids else 1
            if trial.id not in frontier_ids and trial.recommendation_rank is not None:
                trial.recommendation_rank = None
                trial.recommendation_json = None

    def _persist_recommendations(self, session: Session, bundle) -> None:
        by_trial = {item.trial_id: item for item in bundle.candidates}
        trials = session.scalars(
            select(OptimizationTrial).where(OptimizationTrial.study_id == bundle.study_id)
        ).all()
        newly_ranked: list[str] = []
        for trial in trials:
            candidate = by_trial.get(trial.id)
            if candidate is not None:
                if trial.recommendation_rank != candidate.rank or trial.recommendation_json is None:
                    newly_ranked.append(trial.id)
                trial.recommendation_rank = candidate.rank
                trial.recommendation_json = _canonical(
                    {
                        "rank": candidate.rank,
                        "dominates_baseline": candidate.dominates_baseline,
                        "improved_metrics": list(candidate.improved_metrics),
                        "unchanged_metrics": list(candidate.unchanged_metrics),
                        "regressed_metrics": list(candidate.regressed_metrics),
                        "rationale": candidate.rationale,
                        "algorithm_version": candidate.algorithm_version,
                    }
                )
            elif trial.recommendation_rank is not None:
                trial.recommendation_rank = None
                trial.recommendation_json = None
        if newly_ranked:
            study = session.get(OptimizationStudy, bundle.study_id)
            if study is not None:
                self._append_event(
                    session,
                    study,
                    EVENT_RECOMMENDATION_UPDATED,
                    {"trial_ids": newly_ranked, "count": len(newly_ranked)},
                )

    def _policy_service(self) -> AgentPolicy:
        """Return the V5.3 policy collaborator bound to the same session factory."""

        if self._policy_service_factory is not None:
            return self._policy_service_factory()
        from app.modules.agent_policy.service import SqlAgentPolicy

        return SqlAgentPolicy(self._sessions)

    def _deadline_reached(self, study: OptimizationStudy, now: datetime) -> bool:
        return deadline_reached(study, now)

    def _collect_observations(
        self, session: Session, study: OptimizationStudy
    ) -> tuple[Observation, ...]:
        """Gather (config, score) observations from this study's completed
        trials and, when warm-started, from the parent study as well."""

        sources = [study]
        observations: list[Observation] = []
        seen_fingerprints: set[str] = set()
        if study.warm_start_observations_json:
            for row in json.loads(study.warm_start_observations_json)["observations"]:
                config = policy_config_from_snapshot(row["config_json"], row["config_sha256"])
                seen_fingerprints.add(row["config_sha256"])
                observations.append(Observation(config=config, score=float(row["score_millis"])))
        for source in sources:
            rows = session.scalars(
                select(OptimizationTrial).where(
                    OptimizationTrial.study_id == source.id,
                    OptimizationTrial.status == "completed",
                )
            ).all()
            for row in rows:
                if row.config_sha256 in seen_fingerprints or row.score_millis is None:
                    continue
                try:
                    config = policy_config_from_snapshot(row.config_json, row.config_sha256)
                except ValueError:
                    continue
                seen_fingerprints.add(row.config_sha256)
                observations.append(Observation(config=config, score=float(row.score_millis)))
        return tuple(observations)

    def _maybe_settle(self, session: Session, study: OptimizationStudy, now: datetime) -> None:
        """Settle the study once every trial reached a terminal state.

        At least one completed trial settles as `completed`; an all-failed or
        all-cancelled study settles as `failed`. Studies with work still
        pending/running stay `running`.
        """

        if study.status != "running":
            return
        if self._deadline_reached(study, now):
            self._cancel_pending_for_limit(session, study, now, "OPTIMIZER_DEADLINE_REACHED")
        statuses = session.scalars(
            select(OptimizationTrial.status).where(OptimizationTrial.study_id == study.id)
        ).all()
        if not statuses or any(status in {"pending", "running", "completing"} for status in statuses):
            return
        completed = any(status == "completed" for status in statuses)
        study.status = "completed" if completed else "failed"
        study.finished_at = now
        self._append_event(
            session,
            study,
            EVENT_STUDY_COMPLETED if completed else EVENT_STUDY_FAILED,
            {},
        )

    def _cancel_pending_for_limit(
        self, session: Session, study: OptimizationStudy, now: datetime, code: str
    ) -> None:
        pending = session.scalars(select(OptimizationTrial).where(
            OptimizationTrial.study_id == study.id, OptimizationTrial.status == "pending"
        )).all()
        for trial in pending:
            trial.status = "cancelled"
            trial.failure_code = code
            trial.finished_at = now
            self._append_event(session, study, EVENT_TRIAL_CANCELLED,
                               {"trial_id": trial.id, "ordinal": trial.ordinal})
        if pending:
            session.execute(update(OutboxMessage).where(
                OutboxMessage.topic == TRIAL_TOPIC,
                OutboxMessage.aggregate_id.in_([trial.id for trial in pending]),
                OutboxMessage.status.in_(["pending", "publishing"]),
            ).values(status="dead_letter", last_error=CANCELLED_MESSAGE))
            session.flush()

    @staticmethod
    def _replay_or_conflict(
        study: OptimizationStudy, payload_hash: str, deadline: datetime | None
    ) -> StudyMutationReceipt:
        stored_deadline = effective_deadline(study)
        if study.request_payload_hash != payload_hash or stored_deadline != deadline:
            raise ServiceError(
                code="OPTIMIZER_IDEMPOTENCY_CONFLICT",
                message="Optimizer request id was already used with a different payload.",
                status_code=409,
            )
        return {"study_id": study.id, "status": study.status, "replayed": True}


def _trial_id_of(rows, ordinal: int) -> str:
    for row, trial in rows:
        if trial.ordinal == ordinal:
            return trial.id
    return ""


def _trial_metrics_from_report(report: ValidatedEvaluationReport, trial: OptimizationTrial) -> TrialMetrics:
    agent_p95 = float(report.latency_ms["agent_p95"])
    config = policy_config_from_snapshot(trial.config_json, trial.config_sha256)
    return TrialMetrics(
        case_pass_rate=float(report.metrics["case_pass_rate"]),
        mean_source_recall=float(report.metrics["mean_source_recall"]),
        citation_completeness=float(report.metrics["citation_completeness"]),
        latency_ms=agent_p95,
        retrieval_window=config.factual_top_k + config.comparative_top_k + config.temporal_top_k,
        external_provider_calls=report.external_provider_calls,
    )


def _category_stats_from_report(report: ValidatedEvaluationReport) -> dict[str, object]:
    return serialize_case_results(
        CaseResult(
            case_id=item.case_id,
            category=item.category,
            passed=item.passed,
            source_recall=float(item.source_recall),
            latency_ms=float(item.latency_ms),
        )
        for item in report.cases
    )


def _policy_config(policy: AgentPolicyVersion) -> RetrievalPolicyConfig:
    return policy_config_from_snapshot(policy.config_json, policy.config_sha256)


def _space_payload(space: SearchSpace) -> dict[str, dict[str, int]]:
    return {
        name: {"minimum": getattr(space, name).minimum, "maximum": getattr(space, name).maximum}
        for name in (
            "factual_top_k",
            "comparative_top_k",
            "temporal_top_k",
            "minimum_score_millis",
            "max_hits_per_source",
            "neighbor_before",
            "neighbor_after",
        )
    }


def _weights_payload(weights: ScoreWeights) -> dict[str, int]:
    return {
        "quality_weight_permille": weights.quality_weight_permille,
        "cost_weight_permille": weights.cost_weight_permille,
    }


def _space_from_json(value: str) -> SearchSpace:
    payload = json.loads(value)
    bounds = {
        name: SearchSpaceBound(minimum=int(data["minimum"]), maximum=int(data["maximum"]))
        for name, data in payload.items()
    }
    return SearchSpace(**bounds)


def _weights_from_json(value: str) -> ScoreWeights:
    payload = json.loads(value)
    return ScoreWeights(**payload)


def _budget_from_json(value: str) -> StudyBudget:
    payload = json.loads(value)
    return StudyBudget(
        max_candidates=int(payload["max_candidates"]),
        max_evaluations=int(payload["max_evaluations"]),
    )


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _aware(value: datetime) -> datetime:
    return (value if value.tzinfo is not None else value.replace(tzinfo=UTC)).astimezone(UTC)
