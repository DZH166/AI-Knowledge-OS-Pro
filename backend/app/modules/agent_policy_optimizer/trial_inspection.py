"""Read-only detailed Trial inspection for the optimizer workbench."""

from __future__ import annotations

from collections.abc import Callable
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evaluation import AgentEvaluation
from app.models.optimizer import OptimizationTrial
from app.modules.agent_policy.config import policy_config_from_snapshot
from app.modules.agent_policy_optimizer.category_analysis import compare_categories, deserialize_case_results
from app.modules.agent_policy_optimizer.contracts import CategoryComparisonView, DiffView, OptimizerInputError
from app.modules.agent_policy_optimizer.internal import (
    PolicyServiceFactory,
    QualificationReader,
    required_study,
    required_trial,
)


SessionFactory = Callable[[], Session]


class OptimizerTrialInspector:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        policy_service: PolicyServiceFactory,
        qualify_rows: QualificationReader,
    ) -> None:
        self._sessions = session_factory
        self._policy_service = policy_service
        self._qualify_rows = qualify_rows

    def inspect_categories(self, study_id: str, trial_id: str) -> CategoryComparisonView:
        """Per-category comparison of one trial against the ordinal-1 baseline."""

        with self._sessions() as session:
            study = required_study(session, study_id)
            trial = required_trial(session, trial_id)
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

            try:
                baseline_cases = deserialize_case_results(json.loads(baseline.category_stats_json))
                trial_cases = deserialize_case_results(json.loads(trial.category_stats_json))
            except (OptimizerInputError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ServiceError(
                    code="OPTIMIZER_CATEGORIES_UNAVAILABLE",
                    message="Exact category case facts are unavailable for this Trial.",
                    status_code=409,
                ) from exc
            rows = compare_categories(baseline_cases, trial_cases)
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

    def diff_against_active(self, study_id: str, trial_id: str) -> DiffView:
        """Compare a trial configuration against the current active policy."""

        from app.modules.agent_policy.comparison import compare_policy_configs
        from app.modules.agent_policy.contracts import GetActivePolicy

        with self._sessions() as session, session.begin():
            study = required_study(session, study_id)
            trial = required_trial(session, trial_id)
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

