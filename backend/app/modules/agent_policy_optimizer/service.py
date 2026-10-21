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
from app.models.optimizer import OptimizationStudy, OptimizationTrial
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
    policy_fingerprint,
)
from app.modules.agent_policy_optimizer.contracts import (
    ExecuteTrial,
    GetOptimizationPareto,
    GetOptimizationRecommendation,
    GetOptimizationStudy,
    GetOptimizationTrial,
    ListOptimizationStudies,
    ListOptimizationTrials,
    OptimizerInputError,
    RecommendationInput,
    ScoreWeights,
    SearchSpace,
    SearchSpaceBound,
    StudyBudget,
    CancelStudy,
    RecoverOptimizations,
    StartStudy,
    StudyCommand,
    StudyObjective,
    TrialMetrics,
)
from app.modules.agent_policy_optimizer.candidate_generation import generate_candidates
from app.modules.agent_policy_optimizer.executor import TrialExecutor, TrialPolicySnapshot
from app.modules.agent_policy_optimizer.objectives import normalize_metrics, weighted_score_millis
from app.modules.agent_policy_optimizer.pareto import pareto_frontier, qualify_trial
from app.modules.agent_policy_optimizer.recommendation import build_recommendations
from app.modules.agent_control.sanitization import contains_sensitive_text, sanitize_fact


SessionFactory = Callable[[], Session]
TRIAL_TOPIC = "agent.optimize.trial"
CANCELLED_MESSAGE = "Study cancelled by operator."
class SqlAgentPolicyOptimizer:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        lease_seconds: int = 900,
        evaluation_lease_seconds: int = 1020,
    ) -> None:
        if lease_seconds <= 0 or evaluation_lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._sessions = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_seconds = lease_seconds

    # ------------------------------------------------------------------ submit

    def submit(self, command: StudyCommand) -> dict[str, object]:
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
            }
        )
        try:
            with self._sessions() as session, session.begin():
                existing = session.scalar(
                    select(OptimizationStudy).where(OptimizationStudy.request_id == request_id)
                )
                if existing is not None:
                    return self._replay_or_conflict(existing, payload_hash)
                base_policy = self._required_policy(session, command.base_policy_id)
                base_config = _policy_config(base_policy)
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
                                {"deadline_at": command.deadline_at.isoformat()}
                                if command.deadline_at is not None
                                else {}
                            ),
                        }
                    ),
                    budget_usage_json=_canonical({"created_trials": 0, "started_evaluations": 0}),
                    seed=command.seed,
                    algorithm_version="v5_4a_1",
                    base_policy_fingerprint=base_policy.config_sha256,
                    deadline_at=command.deadline_at,
                )
                session.add(study)
                session.flush([study])
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
                return self._replay_or_conflict(winner, payload_hash)

    # ------------------------------------------------------------------- start

    def start(self, study_id: str) -> dict[str, object]:
        now = self._clock()
        with self._sessions() as session, session.begin():
            study = self._required_study(session, study_id)
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
            if study.deadline_at is not None and study.deadline_at <= now:
                study.status = "completed"
                study.finished_at = now
                return {"study_id": current_id, "status": "completed", "created": 0}
            base_policy = self._required_policy(session, study.base_policy_id)
            base_config = _policy_config(base_policy)
            space = _space_from_json(study.search_space_json)
            budget = _budget_from_json(study.budget_json)
            candidates = generate_candidates(
                base_config,
                space,
                max_candidates=budget.max_candidates,
                seed=study.seed,
            )
            created = 0
            for candidate in candidates:
                if created >= budget.max_evaluations:
                    break
                trial = OptimizationTrial(
                    id=str(uuid4()),
                    study_id=study.id,
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
                created += 1
            usage = {
                "created_trials": created,
                "started_evaluations": 0,
            }
            study.budget_usage_json = _canonical(usage)
            study.status = "running"
            study.started_at = now
            session.flush([study])
            return {"study_id": current_id, "status": "running", "created": created}

    # ----------------------------------------------------------------- execute

    def execute(self, command: ExecuteTrial, executor: TrialExecutor) -> dict[str, object]:
        if not command.worker_id.strip():
            raise ValueError("worker_id cannot be empty")
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
            if report.policy_fingerprint is not None and report.policy_fingerprint != snapshot.config_sha256:
                raise EvaluationReportError(
                    "OPTIMIZER_TRIAL_FINGERPRINT_MISMATCH",
                    "The evaluator report does not match the candidate policy fingerprint.",
                )
        except EvaluationReportError as exc:
            self._fail_trial(command, code=exc.code)
        except EvaluationExecutionError as exc:
            self._fail_trial(command, code=exc.code)
        except Exception as exc:  # noqa: BLE001 - convert unknown executor faults into bounded state.
            self._fail_trial(command, code="OPTIMIZER_EXECUTOR_FAILED")
        else:
            if self._complete_trial(command, report):
                self._rescore_study(trial_id)
        return self._trial_public_state(trial_id)

    def _rescore_study(self, trial_id: str) -> None:
        """Recompute normalized metrics and scores for every completed trial of
        the study over the full completed set, keeping scores comparable."""

        with self._sessions() as session, session.begin():
            trial = session.get(OptimizationTrial, trial_id)
            if trial is None:
                return
            study = session.get(OptimizationStudy, trial.study_id)
            if study is None:
                return
            trials = session.scalars(
                select(OptimizationTrial).where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.status == "completed",
                )
            ).all()
            weights = _weights_from_json(study.weights_json)
            normalized_by_id = self._normalized_for_rows(trials)
            normalized_ids = set(normalized_by_id)
            for trial_row in trials:
                if trial_row.id not in normalized_ids:
                    continue
                trial_row.normalized_metrics_json = _canonical(normalized_by_id[trial_row.id])
                trial_row.score_millis = weighted_score_millis(normalized_by_id[trial_row.id], weights)

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

        validated = validate_evaluation_report(report)
        return self._complete_trial(
            ExecuteTrial(trial_id=trial_id, worker_id=worker_id),
            validated,
            finished_at=completed_at,
        )

    # ------------------------------------------------------------------ cancel

    def cancel(self, study_id: str) -> dict[str, object]:
        now = self._clock()
        with self._sessions() as session, session.begin():
            study = self._required_study(session, study_id)
            current_id = study.id
            current_status = study.status
            if current_status not in {"pending", "running"}:
                return {"study_id": current_id, "status": current_status, "cancelled": False}
            study.status = "cancelled"
            study.cancelled_at = now
            study.finished_at = now
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
            return {"study_id": current_id, "status": "cancelled", "cancelled": True}

    # ----------------------------------------------------------------- recover

    def recover(self, command: RecoverOptimizations) -> int:
        recovered = 0
        with self._sessions() as session, session.begin():
            study_scope = (
                select(OptimizationStudy.id).where(OptimizationStudy.id == command.study_id)
                if command.study_id is not None
                else select(OptimizationStudy.id)
            )
            trial_scope = select(OptimizationTrial.id).where(
                OptimizationTrial.study_id.in_(study_scope)
            )
            result = session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.id.in_(trial_scope),
                    OptimizationTrial.status == "running",
                    OptimizationTrial.lease_expires_at.is_not(None),
                    OptimizationTrial.lease_expires_at <= command.now,
                )
                .values(
                    status="pending",
                    lease_owner=None,
                    lease_expires_at=None,
                    failure_code=None,
                )
                .execution_options(synchronize_session=False)
            )
            recovered += int(result.rowcount or 0)
            stale_running_studies = session.scalars(
                select(OptimizationStudy.id).where(
                    OptimizationStudy.status == "running",
                    OptimizationStudy.lease_expires_at.is_not(None),
                    OptimizationStudy.lease_expires_at <= command.now,
                )
            ).all()
            session.execute(
                update(OptimizationStudy)
                .where(
                    OptimizationStudy.id.in_(stale_running_studies),
                    OptimizationStudy.status == "running",
                    OptimizationStudy.lease_expires_at <= command.now,
                )
                .values(
                    status="running",
                    lease_owner=None,
                    lease_expires_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            # Expired evaluation leases on optimizer evaluations: fail them so
            # their trials can be retried without overwriting completed work.
            session.execute(
                update(AgentEvaluation)
                .where(
                    AgentEvaluation.status == "running",
                    AgentEvaluation.lease_expires_at.is_not(None),
                    AgentEvaluation.lease_expires_at <= command.now,
                    AgentEvaluation.id.in_(
                        select(OptimizationTrial.evaluation_id).where(
                            OptimizationTrial.evaluation_id.is_not(None),
                            OptimizationTrial.status == "running",
                        )
                    ),
                )
                .values(
                    status="failed",
                    error_code="OPTIMIZER_EVALUATION_WORKER_INTERRUPTED",
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=command.now,
                )
                .execution_options(synchronize_session=False)
            )
            return recovered

    # ----------------------------------------------------------------- inspect

    def inspect(self, query: OptimizerQuery) -> dict[str, object]:
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
        raise TypeError(f"Unsupported optimizer query: {type(query).__name__}")

    def inspect_study(self, study_id: str) -> dict[str, object]:
        with self._sessions() as session:
            study = self._required_study(session, study_id)
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
                "created_at": _aware(study.created_at).isoformat(),
                "started_at": _aware(study.started_at).isoformat() if study.started_at else None,
                "finished_at": _aware(study.finished_at).isoformat() if study.finished_at else None,
                "cancelled_at": _aware(study.cancelled_at).isoformat() if study.cancelled_at else None,
            }

    def inspect_trial(self, trial_id: str) -> dict[str, object]:
        return self._trial_public_state(trial_id)

    def _list_studies(self, query: ListOptimizationStudies) -> dict[str, object]:
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

    def _list_trials(self, query: ListOptimizationTrials) -> dict[str, object]:
        with self._sessions() as session:
            statement = select(OptimizationTrial).where(OptimizationTrial.study_id == query.study_id)
            if query.status is not None:
                statement = statement.where(OptimizationTrial.status == query.status)
            rows = session.scalars(
                statement.order_by(OptimizationTrial.ordinal.asc()).limit(max(1, min(query.limit, 200)))
            ).all()
            return {"items": [self._trial_public_state(row.id) for row in rows]}

    def inspect_pareto(self, study_id: str) -> dict[str, object]:
        with self._sessions() as session:
            study = self._required_study(session, study_id)
            trials = session.scalars(
                select(OptimizationTrial).where(OptimizationTrial.study_id == study.id)
            ).all()
            rows = self._qualify_rows(session, trials)
            frontier = pareto_frontier(row for row, _ in rows)
            self._persist_frontier_flags(session, trials, frontier)
            session.commit()
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

    def inspect_recommendation(self, study_id: str) -> dict[str, object]:
        with self._sessions() as session:
            study = self._required_study(session, study_id)
            trials = session.scalars(
                select(OptimizationTrial).where(OptimizationTrial.study_id == study.id).order_by(
                    OptimizationTrial.ordinal.asc()
                )
            ).all()
            rows = self._qualify_rows(session, trials)
            frontier = pareto_frontier(row for row, _ in rows)
            inputs = self._recommendation_inputs(session, rows)
            if not inputs:
                return {
                    "study_id": study.id,
                    "algorithm_version": "v5_4a_1",
                    "candidates": [],
                }
            baseline_input = next(
                (item for item in inputs if item.trial_id == _trial_id_of(rows, 1)),
                inputs[0],
            )
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
            self._persist_recommendations(session, bundle)
            session.commit()
            return {
                "study_id": study.id,
                "algorithm_version": bundle.algorithm_version,
                "candidates": [
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
                        "rationale": item.rationale,
                        "algorithm_version": item.algorithm_version,
                    }
                    for item in bundle.candidates
                ],
            }

    # ---------------------------------------------------------------- internals

    def _claim_trial(self, command: ExecuteTrial) -> dict[str, object]:
        now = self._clock()
        with self._sessions() as session, session.begin():
            trial = session.get(OptimizationTrial, command.trial_id)
            if trial is None:
                raise ServiceError(code="OPTIMIZER_TRIAL_NOT_FOUND", message="Trial not found.", status_code=404)
            if trial.status != "pending":
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
                metrics_json=_canonical(report.metrics),
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
                    external_provider_calls=report.external_provider_calls,
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                return False
            budget = _budget_from_json(study.budget_json)
            completed_count = session.scalar(
                select(func.count()).select_from(OptimizationTrial).where(
                    OptimizationTrial.study_id == trial.study_id,
                    OptimizationTrial.status == "completed",
                )
            )
            if completed_count >= budget.max_evaluations or self._deadline_reached(study, now):
                study.status = "completed"
                study.finished_at = now
            return True

    def _fail_trial(self, command: ExecuteTrial, *, code: str) -> bool:
        now = self._clock()
        with self._sessions() as session, session.begin():
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
            return result.rowcount == 1

    def _trial_public_state(self, trial_id: str) -> dict[str, object]:
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
            hard_gates = (
                json.loads(evaluation.hard_gates_json)
                if evaluation is not None and evaluation.hard_gates_json
                else None
            )
            metrics = (
                _metrics_from_evaluation(evaluation, trial)
                if evaluation is not None and evaluation.status == "passed"
                else None
            )
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
        for trial in trials:
            candidate = by_trial.get(trial.id)
            if candidate is not None:
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

    def _deadline_reached(self, study: OptimizationStudy, now: datetime) -> bool:
        if study.deadline_at is None:
            return False
        deadline = study.deadline_at if study.deadline_at.tzinfo else study.deadline_at.replace(tzinfo=UTC)
        return deadline <= now

    @staticmethod
    def _required_study(session: Session, study_id: str) -> OptimizationStudy:
        study = session.get(OptimizationStudy, study_id)
        if study is None:
            raise ServiceError(code="OPTIMIZER_STUDY_NOT_FOUND", message="Optimization study not found.", status_code=404)
        return study

    @staticmethod
    def _required_policy(session: Session, policy_id: str) -> AgentPolicyVersion:
        policy = session.get(AgentPolicyVersion, policy_id)
        if policy is None:
            raise ServiceError(code="OPTIMIZER_POLICY_NOT_FOUND", message="Agent policy not found.", status_code=404)
        return policy

    @staticmethod
    def _replay_or_conflict(study: OptimizationStudy, payload_hash: str) -> dict[str, object]:
        if study.request_payload_hash != payload_hash:
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


def _metrics_from_evaluation(evaluation: AgentEvaluation, trial: OptimizationTrial) -> TrialMetrics | None:
    try:
        payload = json.loads(evaluation.metrics_json or "{}")
        latency = payload.get("latency_ms") or {}
        agent_p95 = float((latency or {}).get("agent_p95") or 0.0)
        config = policy_config_from_snapshot(trial.config_json, trial.config_sha256)
        window = config.factual_top_k + config.comparative_top_k + config.temporal_top_k
        return TrialMetrics(
            case_pass_rate=float(payload["case_pass_rate"]),
            mean_source_recall=float(payload["mean_source_recall"]),
            citation_completeness=float(payload["citation_completeness"]),
            latency_ms=agent_p95,
            retrieval_window=window,
            external_provider_calls=int(evaluation.external_provider_calls or 0),
        )
    except (KeyError, TypeError, ValueError, OptimizerInputError, json.JSONDecodeError):
        return None


def _trial_metrics_from_report(report: ValidatedEvaluationReport, trial: OptimizationTrial) -> TrialMetrics:
    latency = report.metrics.get("latency_ms")
    agent_p95 = 0.0
    if isinstance(latency, dict):
        agent_p95 = float(latency.get("agent_p95") or 0.0)
    config = policy_config_from_snapshot(trial.config_json, trial.config_sha256)
    return TrialMetrics(
        case_pass_rate=float(report.metrics["case_pass_rate"]),
        mean_source_recall=float(report.metrics["mean_source_recall"]),
        citation_completeness=float(report.metrics["citation_completeness"]),
        latency_ms=agent_p95,
        retrieval_window=config.factual_top_k + config.comparative_top_k + config.temporal_top_k,
        external_provider_calls=report.external_provider_calls,
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
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
