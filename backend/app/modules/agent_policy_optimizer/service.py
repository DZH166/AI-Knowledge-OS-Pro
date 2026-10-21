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
    EXPECTED_CATEGORY_COUNTS,
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
    DiffTrialAgainstActive,
    ExecuteTrial,
    NextRound,
    OptimizerReadQuery,
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
from app.modules.agent_policy_optimizer.bayesian_generation import (
    Observation,
    generate_bayesian_candidates,
)
from app.modules.agent_policy_optimizer.category_analysis import compare_categories
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
        policy_service_factory: Callable[[], object] | None = None,
    ) -> None:
        if lease_seconds <= 0 or evaluation_lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._sessions = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_seconds = lease_seconds
        self._policy_service_factory = policy_service_factory

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
                "warm_start_study_id": command.warm_start_study_id,
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
                warm_start_study: OptimizationStudy | None = None
                if command.warm_start_study_id is not None:
                    warm_start_study = session.get(OptimizationStudy, command.warm_start_study_id)
                    if warm_start_study is None:
                        raise ServiceError(
                            code="OPTIMIZER_WARM_START_NOT_FOUND",
                            message="Warm start study does not exist.",
                            status_code=404,
                        )
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
                    algorithm_version="v5_6_bayesian_1",
                    base_policy_fingerprint=base_policy.config_sha256,
                    deadline_at=command.deadline_at,
                    warm_start_study_id=(
                        command.warm_start_study_id if warm_start_study is not None else None
                    ),
                    round_no=2 if warm_start_study is not None else 1,
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
            observations = self._collect_observations(session, study)
            if study.round_no > 1 and observations:
                candidates = generate_bayesian_candidates(
                    base_config,
                    space,
                    round_no=study.round_no,
                    observations=observations,
                    max_candidates=budget.max_candidates,
                    seed=study.seed,
                )
            else:
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
                created += 1
            prior_usage = json.loads(study.budget_usage_json or "{}")
            usage = {
                "created_trials": max(created, int(prior_usage.get("created_trials", 0))),
                "started_evaluations": int(prior_usage.get("started_evaluations", 0)),
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

    def inspect(self, query: OptimizerReadQuery) -> dict[str, object]:
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
                "round_no": study.round_no,
                "warm_start_study_id": study.warm_start_study_id,
                "next_round_request_id": study.next_round_request_id,
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

            baseline_row = session.scalars(
                select(OptimizationTrial).where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.ordinal == 1,
                )
            ).first()

            def _cases(stats_json: str):
                from app.modules.agent_policy_optimizer.category_analysis import CaseResult

                payload = json.loads(stats_json)
                cases = []
                for category, stat in payload.items():
                    total = int(stat["total"])
                    passed = int(stat["passed"])
                    recall = float(stat["mean_source_recall"])
                    for index in range(1, total + 1):
                        cases.append(
                            CaseResult(
                                case_id=f"{category}-{index:02d}",
                                category=category,
                                passed=index <= passed,
                                source_recall=recall,
                                latency_ms=0.0,
                            )
                        )
                return cases

            candidates_payload = []
            for item in bundle.candidates:
                candidate_row = session.get(OptimizationTrial, item.trial_id)
                summary_sentence = ""
                if (
                    candidate_row is not None
                    and candidate_row.category_stats_json
                    and baseline_row is not None
                    and baseline_row.category_stats_json
                ):
                    from app.modules.agent_policy_optimizer.category_analysis import summarize_categories

                    summary = summarize_categories(
                        _cases(baseline_row.category_stats_json),
                        _cases(candidate_row.category_stats_json),
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

    # ------------------------------------------------------ v5.6 next round

    def start_next_round(self, command: NextRound) -> dict[str, object]:
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
                study = self._required_study(session, command.study_id)
                current_id = study.id
                if study.next_round_request_id == request_id:
                    return {
                        "study_id": current_id,
                        "round_no": study.round_no,
                        "created": 0,
                        "replayed": True,
                    }
                if study.status != "completed":
                    raise ServiceError(
                        code="OPTIMIZER_STUDY_NOT_COMPLETED",
                        message="Only a completed study can start a next round.",
                        status_code=409,
                    )
                budget = _budget_from_json(study.budget_json)
                usage = json.loads(study.budget_usage_json)
                started_total = int(usage.get("started_evaluations", 0))
                # max_candidates is a per-round cap; max_evaluations is the
                # total evaluation cap across all rounds.
                remaining_slots = min(
                    budget.max_candidates,
                    budget.max_evaluations - started_total,
                )
                if remaining_slots <= 0:
                    raise ServiceError(
                        code="OPTIMIZER_BUDGET_EXHAUSTED",
                        message="Study budgets are exhausted; no next round can be created.",
                        status_code=409,
                    )
                base_policy = self._required_policy(session, study.base_policy_id)
                base_config = _policy_config(base_policy)
                space = _space_from_json(study.search_space_json)
                observations = self._collect_observations(session, study)
                next_round_no = study.round_no + 1
                candidates = generate_bayesian_candidates(
                    base_config,
                    space,
                    round_no=next_round_no,
                    observations=observations,
                    max_candidates=remaining_slots,
                    seed=study.seed + next_round_no,
                )
                max_ordinal = session.scalar(
                    select(func.max(OptimizationTrial.ordinal)).where(
                        OptimizationTrial.study_id == study.id
                    )
                )
                next_ordinal = int(max_ordinal or 0)
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
                    created += 1
                usage["created_trials"] = int(usage.get("created_trials", 0)) + created
                study.budget_usage_json = _canonical(usage)
                study.round_no = next_round_no
                study.next_round_request_id = request_id
                study.status = "running"
                study.started_at = study.started_at or now
                study.finished_at = None
                session.flush([study])
                return {
                    "study_id": current_id,
                    "round_no": next_round_no,
                    "created": created,
                    "replayed": False,
                }
        except IntegrityError as exc:
            with self._sessions() as replay_session:
                replay_target = self._required_study(replay_session, command.study_id)
                if replay_target.next_round_request_id == request_id:
                    return {
                        "study_id": replay_target.id,
                        "round_no": replay_target.round_no,
                        "created": 0,
                        "replayed": True,
                    }
            raise ServiceError(
                code="OPTIMIZER_NEXT_ROUND_CONFLICT",
                message="Concurrent next-round creation conflicted; retry with a fresh request id.",
                status_code=409,
            ) from exc

    # ------------------------------------------------------- v5.5 closed loop

    def convert_to_draft(self, command: ConvertRecommendation) -> dict[str, object]:
        """Convert one recommendation candidate into a V5.3 draft policy.

        Never activates anything: the produced policy row is a draft, and the
        only path to active remains the human-gated V5.3 activation flow.
        """

        request_id = command.request_id.strip()
        if not request_id or len(request_id) > 120 or contains_sensitive_text(request_id):
            raise ServiceError(
                code="OPTIMIZER_REQUEST_ID_INVALID",
                message="Convert request id is blank, too long, or secret-looking.",
                status_code=422,
            )
        label = command.label.strip() if command.label else None
        if label is not None and (not label or len(label) > 120 or contains_sensitive_text(label)):
            raise ServiceError(
                code="OPTIMIZER_LABEL_INVALID",
                message="Convert label is blank, too long, or secret-looking.",
                status_code=422,
            )
        with self._sessions() as session, session.begin():
            study = self._required_study(session, command.study_id)
            trial = self._required_trial(session, command.trial_id)
            if trial.study_id != study.id:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_NOT_FOUND",
                    message="Trial does not belong to this study.",
                    status_code=404,
                )
            if trial.draft_policy_id is not None:
                policy = session.get(AgentPolicyVersion, trial.draft_policy_id)
                if policy is not None:
                    if policy.config_sha256 != trial.config_sha256:
                        raise ServiceError(
                            code="OPTIMIZER_CONVERT_CONFLICT",
                            message="Existing draft fingerprint no longer matches the trial.",
                            status_code=409,
                        )
                    # The draft may have since been activated by the human flow;
                    # replay reports its CURRENT lifecycle status, not "draft".
                    from app.models.agent_policy import AgentPolicyCommand

                    command_row = (
                        session.scalar(
                            select(AgentPolicyCommand).where(
                                AgentPolicyCommand.request_id == (trial.request_id or command.request_id)
                            )
                        )
                        if (trial.request_id or command.request_id)
                        else None
                    )
                    return {
                        "command_id": command_row.id if command_row is not None else "",
                        "policy_id": policy.id,
                        "policy_version": policy.version,
                        "status": policy.status,
                        "policy_config_sha256": policy.config_sha256,
                        "replayed": True,
                    }
            if trial.status != "completed" or trial.recommendation_rank is None:
                raise ServiceError(
                    code="OPTIMIZER_RECOMMENDATION_REQUIRED",
                    message="Only a ranked recommendation candidate can be converted.",
                    status_code=409,
                )
            try:
                config = policy_config_from_snapshot(trial.config_json, trial.config_sha256)
            except ValueError as exc:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_CONFIG_INVALID",
                    message="Trial configuration does not match its fingerprint.",
                    status_code=422,
                ) from exc
            all_trials = session.scalars(
                select(OptimizationTrial).where(OptimizationTrial.study_id == study.id)
            ).all()
            frontier = pareto_frontier(row for row, _ in self._qualify_rows(session, all_trials))
            if not any(item.trial_id == trial.id for item in frontier):
                raise ServiceError(
                    code="OPTIMIZER_RECOMMENDATION_REQUIRED",
                    message="Trial is no longer on the Pareto frontier.",
                    status_code=409,
                )
            from app.modules.agent_policy.contracts import CreatePolicy

            final_label = label or f"Optimizer {study.label[:60]} - trial {trial.ordinal}"
            receipt = self._policy_service().submit(
                CreatePolicy(
                    request_id=request_id,
                    label=final_label,
                    base_policy_id=study.base_policy_id,
                    config=config,
                )
            )
            policy = session.get(AgentPolicyVersion, receipt.policy_id)
            if policy is None or policy.status != "draft" or policy.config_sha256 != trial.config_sha256:
                raise ServiceError(
                    code="OPTIMIZER_CONVERT_CONFLICT",
                    message="Converted policy does not match the trial fingerprint.",
                    status_code=409,
                )
            trial.draft_policy_id = policy.id
            trial.request_id = request_id
            try:
                session.flush([trial])
            except IntegrityError:
                # A concurrent conversion won the unique slot; return its draft.
                session.rollback()
                winner = self._required_trial(session, command.trial_id)
                if winner.draft_policy_id is None:
                    raise ServiceError(
                        code="OPTIMIZER_CONVERT_CONFLICT",
                        message="Concurrent conversion could not allocate the trial draft slot.",
                        status_code=409,
                    ) from None
                won_policy = session.get(AgentPolicyVersion, winner.draft_policy_id)
                if won_policy is None:
                    raise ServiceError(
                        code="OPTIMIZER_CONVERT_CONFLICT",
                        message="Concurrent conversion produced an unreadable draft.",
                        status_code=409,
                    ) from None
                return {
                    "command_id": winner.request_id or "",
                    "policy_id": won_policy.id,
                    "policy_version": won_policy.version,
                    "status": won_policy.status,
                    "policy_config_sha256": won_policy.config_sha256,
                    "replayed": True,
                }
            return {
                "command_id": receipt.command_id,
                "policy_id": policy.id,
                "policy_version": policy.version,
                "status": policy.status,
                "policy_config_sha256": policy.config_sha256,
                "replayed": bool(receipt.replayed),
            }

    def inspect_categories(self, study_id: str, trial_id: str) -> dict[str, object]:
        """Per-category comparison of one trial against the ordinal-1 baseline."""

        from app.modules.agent_policy_optimizer.category_analysis import (
            CaseResult,
            compare_categories,
        )

        with self._sessions() as session:
            study = self._required_study(session, study_id)
            trial = self._required_trial(session, trial_id)
            if trial.study_id != study.id:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_NOT_FOUND",
                    message="Trial does not belong to this study.",
                    status_code=404,
                )
            if not trial.category_stats_json:
                raise ServiceError(
                    code="OPTIMIZER_CATEGORIES_UNAVAILABLE",
                    message="Category statistics are only available for completed trials.",
                    status_code=409,
                )
            baseline = session.scalars(
                select(OptimizationTrial).where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.ordinal == 1,
                )
            ).first()
            if baseline is None or not baseline.category_stats_json:
                raise ServiceError(
                    code="OPTIMIZER_CATEGORIES_UNAVAILABLE",
                    message="Baseline trial statistics are unavailable.",
                    status_code=409,
                )

            def _cases(stats_json: str) -> list[CaseResult]:
                payload = json.loads(stats_json)
                cases: list[CaseResult] = []
                for category, stat in payload.items():
                    total = int(stat["total"])
                    passed = int(stat["passed"])
                    recall = float(stat["mean_source_recall"])
                    for index in range(1, total + 1):
                        cases.append(
                            CaseResult(
                                case_id=f"{category}-{index:02d}",
                                category=category,
                                passed=index <= passed,
                                source_recall=recall,
                                latency_ms=0.0,
                            )
                        )
                return cases

            rows = compare_categories(_cases(baseline.category_stats_json), _cases(trial.category_stats_json))
            return {
                "study_id": study.id,
                "trial_id": trial.id,
                "baseline_trial_id": baseline.id,
                "items": [
                    {
                        "category": row.category,
                        "case_count": row.case_count,
                        "pass_rate_left": row.pass_rate_left,
                        "pass_rate_right": row.pass_rate_right,
                        "mean_source_recall_left": row.mean_source_recall_left,
                        "mean_source_recall_right": row.mean_source_recall_right,
                        "wins": row.wins,
                        "ties": row.ties,
                        "losses": row.losses,
                        "verdict": row.verdict,
                    }
                    for row in rows
                ],
            }

    def diff_trial_against_active(self, study_id: str, trial_id: str) -> dict[str, object]:
        """Compare a trial configuration against the current active policy."""

        from app.modules.agent_policy.comparison import compare_policy_configs
        from app.modules.agent_policy.contracts import GetActivePolicy

        with self._sessions() as session, session.begin():
            study = self._required_study(session, study_id)
            trial = self._required_trial(session, trial_id)
            if trial.study_id != study.id:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_NOT_FOUND",
                    message="Trial does not belong to this study.",
                    status_code=404,
                )
            try:
                trial_config = policy_config_from_snapshot(trial.config_json, trial.config_sha256)
            except ValueError as exc:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_CONFIG_INVALID",
                    message="Trial configuration does not match its fingerprint.",
                    status_code=422,
                ) from exc
            try:
                active = self._policy_service().inspect(GetActivePolicy())
            except ServiceError as exc:
                raise ServiceError(
                    code="OPTIMIZER_ACTIVE_POLICY_UNAVAILABLE",
                    message="Active Agent policy is unavailable.",
                    status_code=503,
                ) from exc
            comparison = compare_policy_configs(active.config, trial_config)
            evaluation = (
                session.get(AgentEvaluation, trial.evaluation_id)
                if trial.evaluation_id
                else None
            )
            rows = self._qualify_rows(session, [trial])
            qualified = rows[0][0] if rows else None
            evaluation_summary = {
                "eligible": qualified.eligible if qualified else False,
                "score_millis": trial.score_millis,
                "case_pass_rate": (
                    float(evaluation.metrics_json and json.loads(evaluation.metrics_json).get("case_pass_rate", 0.0))
                    if evaluation is not None and evaluation.metrics_json
                    else None
                ),
            }
            return {
                "study_id": study.id,
                "trial_id": trial.id,
                "trial_config_sha256": trial.config_sha256,
                "active_policy_id": active.id,
                "active_policy_version": active.version,
                "active_config_sha256": active.config_sha256,
                "compatible": comparison.compatible,
                "incompatibility_reasons": list(comparison.incompatibility_reasons),
                "changes": [
                    {"field": change.field, "left": change.left, "right": change.right}
                    for change in comparison.changes
                ],
                "trial_summary": evaluation_summary,
            }

    def retry_trial(self, command: RetryTrial) -> dict[str, object]:
        """Revive one failed trial: failed -> pending with its outbox row back.

        Guarded by the owning study lifecycle (only running studies retry) and
        by the evaluation budget (started_evaluations < max_evaluations).
        """

        now = self._clock()
        with self._sessions() as session, session.begin():
            trial = self._required_trial(session, command.trial_id)
            if trial.status != "failed":
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_RETRY_REJECTED",
                    message="Only a failed trial can be retried.",
                    status_code=409,
                )
            if trial.failure_code in {"OPTIMIZER_STUDY_CANCELLED", "OPTIMIZER_STUDY_FAILED"}:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_RETRY_REJECTED",
                    message="A trial stopped by study-level termination cannot be retried.",
                    status_code=409,
                )
            study = session.get(OptimizationStudy, trial.study_id)
            if study is None or study.status != "running":
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_RETRY_REJECTED",
                    message="Only trials of a running study can be retried.",
                    status_code=409,
                )
            budget = _budget_from_json(study.budget_json)
            usage = json.loads(study.budget_usage_json)
            if int(usage.get("started_evaluations", 0)) >= budget.max_evaluations:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_RETRY_REJECTED",
                    message="Evaluation budget is exhausted; retry would exceed max_evaluations.",
                    status_code=409,
                )
            result = session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.id == trial.id,
                    OptimizationTrial.status == "failed",
                )
                .values(
                    status="pending",
                    failure_code=None,
                    lease_owner=None,
                    lease_expires_at=None,
                    started_at=None,
                    finished_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ServiceError(
                    code="OPTIMIZER_TRIAL_RETRY_REJECTED",
                    message="Trial changed state before retry could apply.",
                    status_code=409,
                )
            session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.aggregate_id == trial.id,
                    OutboxMessage.topic == TRIAL_TOPIC,
                    OutboxMessage.status.in_(["dead_letter", "published"]),
                    OutboxMessage.last_error.is_(None)
                    | OutboxMessage.last_error.notin_([CANCELLED_MESSAGE]),
                )
                .values(
                    status="pending",
                    attempt=0,
                    available_at=now,
                    lease_owner=None,
                    lease_expires_at=None,
                    last_error=None,
                )
                .execution_options(synchronize_session=False)
            )
            return {"trial_id": trial.id, "status": "pending"}

    def fail_study(self, command: FailStudy) -> dict[str, object]:
        """Operator stop: mark the study failed and terminate unfinished work."""

        now = self._clock()
        with self._sessions() as session, session.begin():
            study = self._required_study(session, command.study_id)
            current_id = study.id
            current_status = study.status
            if current_status not in {"pending", "running"}:
                return {"study_id": current_id, "status": current_status, "cancelled": False}
            study.status = "failed"
            study.finished_at = now
            reason = sanitize_fact(command.reason or "operator request", maximum_length=200)
            session.execute(
                update(OptimizationTrial)
                .where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.status.in_(["pending", "running", "completing"]),
                )
                .values(
                    status="cancelled",
                    failure_code="OPTIMIZER_STUDY_FAILED",
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
                .values(status="dead_letter", last_error=reason)
                .execution_options(synchronize_session=False)
            )
            return {"study_id": current_id, "status": "failed", "cancelled": False}

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
            self._maybe_settle(session, study, now)
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
            if result.rowcount != 1:
                return False
            trial = session.get(OptimizationTrial, command.trial_id)
            study = session.get(OptimizationStudy, trial.study_id) if trial else None
            if study is not None:
                self._maybe_settle(session, study, now)
            return True

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
                "draft_policy_id": trial.draft_policy_id,
                "category_stats": json.loads(trial.category_stats_json) if trial.category_stats_json else None,
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

    def _policy_service(self):
        """Return the V5.3 policy collaborator bound to the same session factory."""

        if self._policy_service_factory is not None:
            return self._policy_service_factory()
        from app.modules.agent_policy.service import SqlAgentPolicy

        return SqlAgentPolicy(self._sessions)

    def _deadline_reached(self, study: OptimizationStudy, now: datetime) -> bool:
        if study.deadline_at is None:
            return False
        deadline = study.deadline_at if study.deadline_at.tzinfo else study.deadline_at.replace(tzinfo=UTC)
        return deadline <= now

    def _collect_observations(
        self, session: Session, study: OptimizationStudy
    ) -> tuple[Observation, ...]:
        """Gather (config, score) observations from this study's completed
        trials and, when warm-started, from the parent study as well."""

        sources: list[OptimizationStudy] = []
        if study.warm_start_study_id is not None:
            parent = session.get(OptimizationStudy, study.warm_start_study_id)
            if parent is not None:
                sources.append(parent)
        sources.append(study)
        observations: list[Observation] = []
        seen_fingerprints: set[str] = set()
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
            study.status = "completed"
            study.finished_at = now
            return
        statuses = session.scalars(
            select(OptimizationTrial.status).where(OptimizationTrial.study_id == study.id)
        ).all()
        if not statuses or any(status in {"pending", "running", "completing"} for status in statuses):
            return
        completed = any(status == "completed" for status in statuses)
        study.status = "completed" if completed else "failed"
        study.finished_at = now

    @staticmethod
    def _required_study(session: Session, study_id: str) -> OptimizationStudy:
        study = session.get(OptimizationStudy, study_id)
        if study is None:
            raise ServiceError(code="OPTIMIZER_STUDY_NOT_FOUND", message="Optimization study not found.", status_code=404)
        return study

    @staticmethod
    def _required_trial(session: Session, trial_id: str) -> OptimizationTrial:
        trial = session.get(OptimizationTrial, trial_id)
        if trial is None:
            raise ServiceError(code="OPTIMIZER_TRIAL_NOT_FOUND", message="Optimization trial not found.", status_code=404)
        return trial

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


def _category_stats_from_report(report: ValidatedEvaluationReport) -> dict[str, dict[str, object]]:
    stats: dict[str, dict[str, object]] = {}
    for category in EXPECTED_CATEGORY_COUNTS:
        cases = [item for item in report.cases if item.category == category]
        if not cases:
            continue
        stats[category] = {
            "passed": sum(1 for item in cases if item.passed),
            "total": len(cases),
            "mean_source_recall": round(
                sum(float(item.source_recall) for item in cases) / len(cases), 4
            ),
        }
    return stats


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
