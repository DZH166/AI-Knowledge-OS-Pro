"""Stable read projections for the optimizer workbench screen."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import json

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.optimizer import OptimizationStudy, OptimizationTrial
from app.models.workbench import OptimizationStudyEvent
from app.modules.agent_policy_optimizer.contracts import RecommendationView, StudyEventCatalogView, StudyOverviewView
from app.modules.agent_policy_optimizer.internal import (
    BudgetReader,
    QualificationReader,
    StudyDetailReader,
    required_study,
    execution_block_reason,
    deadline_reached,
)
from app.modules.agent_policy_optimizer.pareto import pareto_frontier


SessionFactory = Callable[[], Session]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class OptimizerWorkbenchProjector:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        qualify_rows: QualificationReader,
        inspect_study: StudyDetailReader,
        recommendations_for_session: Callable[[Session, OptimizationStudy], RecommendationView],
        read_budget: BudgetReader,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._qualify_rows = qualify_rows
        self._inspect_study = inspect_study
        self._recommendations_for_session = recommendations_for_session
        self._read_budget = read_budget
        self._clock = clock or (lambda: datetime.now(UTC))

    def inspect_events(
        self, study_id: str, *, limit: int = 100, after: str | None = None
    ) -> StudyEventCatalogView:
        with self._sessions() as session:
            study = required_study(session, study_id)
            statement = (
                select(OptimizationStudyEvent)
                .where(OptimizationStudyEvent.study_id == study.id)
                .order_by(OptimizationStudyEvent.created_at.asc(), OptimizationStudyEvent.id.asc())
                .limit(max(1, min(limit, 200)))
            )
            if after:
                anchor_event = session.get(OptimizationStudyEvent, after)
                if anchor_event is not None and anchor_event.study_id == study.id:
                    statement = statement.filter(
                        or_(
                            OptimizationStudyEvent.created_at > anchor_event.created_at,
                            and_(
                                OptimizationStudyEvent.created_at == anchor_event.created_at,
                                OptimizationStudyEvent.id > anchor_event.id,
                            ),
                        )
                    )
            rows = session.scalars(statement).all()
            return {
                "study_id": study.id,
                "items": [
                    {
                        "id": row.id,
                        "event_type": row.event_type,
                        "round_no": row.round_no,
                        "payload": json.loads(row.payload_json or "{}"),
                        "created_at": _aware(row.created_at).isoformat(),
                    }
                    for row in rows
                ],
            }

    def inspect_overview(self, study_id: str) -> StudyOverviewView:
        """Aggregate everything a workbench screen needs in one read-only call."""

        with self._sessions() as session:
            study = required_study(session, study_id)
            trials = session.scalars(
                select(OptimizationTrial)
                .where(OptimizationTrial.study_id == study.id)
                .order_by(OptimizationTrial.ordinal.asc())
            ).all()
            rows = self._qualify_rows(session, trials)
            frontier_ids = [item.trial_id for item in pareto_frontier(row for row, _ in rows)]
            current_recommendations = self._recommendations_for_session(session, study)["candidates"]
            ranks_by_trial = {item["trial_id"]: item["rank"] for item in current_recommendations}
            trials_by_id = {trial.id: trial for trial in trials}

            rounds: dict[int, dict[str, object]] = {}
            trial_payload: list[dict[str, object]] = []
            for row, trial in rows:
                bucket = rounds.setdefault(
                    trial.round_no,
                    {
                        "round_no": trial.round_no,
                        "total": 0,
                        "completed": 0,
                        "failed": 0,
                        "cancelled": 0,
                        "best_score_millis": None,
                    },
                )
                bucket["total"] = int(bucket["total"]) + 1
                if trial.status in {"completed", "failed", "cancelled"}:
                    bucket[trial.status] = int(bucket[trial.status]) + 1
                if trial.status == "completed" and trial.score_millis is not None:
                    best = bucket["best_score_millis"]
                    if best is None or int(trial.score_millis) > int(best):
                        bucket["best_score_millis"] = int(trial.score_millis)
                trial_payload.append(
                    {
                        "id": trial.id,
                        "ordinal": trial.ordinal,
                        "round_no": trial.round_no,
                        "status": trial.status,
                        "score_millis": trial.score_millis,
                        "draft_policy_id": trial.draft_policy_id,
                        "recommendation_rank": ranks_by_trial.get(trial.id),
                        "failure_code": trial.failure_code,
                        "eligible": row.eligible,
                        "metrics": row.metrics.as_dict() if row.metrics else None,
                    }
                )

            recommendation_summary: list[dict[str, object]] = []
            for recommendation in current_recommendations:
                trial = trials_by_id[recommendation["trial_id"]]
                rationale = recommendation["rationale"]
                recommendation_summary.append(
                    {
                        "rank": recommendation["rank"],
                        "trial_id": trial.id,
                        "score_millis": trial.score_millis,
                        "converted": trial.draft_policy_id is not None,
                        "draft_policy_id": trial.draft_policy_id,
                        "rationale_first_line": rationale.splitlines()[0] if rationale else "",
                    }
                )
            recommendation_summary.sort(key=lambda item: int(item["rank"]))

            actions: list[dict[str, object]] = []
            if study.status == "pending":
                actions.append({"action": "start", "available": True, "reason": "study is pending"})
            if study.status == "running":
                actions.append({"action": "cancel", "available": True, "reason": "running studies can be cancelled"})
                actions.append({"action": "fail", "available": True, "reason": "running studies can be failed"})
                actions.append({"action": "recover", "available": True, "reason": "running studies may recover expired worker leases"})
            if study.status == "completed":
                budget = self._read_budget(study.budget_json)
                usage = json.loads(study.budget_usage_json)
                has_budget = (
                    int(usage.get("created_trials", 0)) < budget.max_candidates
                    and int(usage.get("started_evaluations", 0)) < budget.max_evaluations
                    and not deadline_reached(study, self._clock())
                )
                actions.append(
                    {
                        "action": "next-round",
                        "available": has_budget,
                        "reason": "budget available" if has_budget else "evaluation budget exhausted",
                    }
                )
            unconverted = any(
                item["recommendation_rank"] is not None and item["draft_policy_id"] is None
                for item in trial_payload
            )
            if unconverted and study.status not in {"cancelled", "failed"}:
                actions.append(
                    {"action": "convert-draft", "available": True, "reason": "unconverted recommendation candidates exist"}
                )
            retryable = any(
                item["status"] == "failed"
                and item["failure_code"] not in {"OPTIMIZER_STUDY_CANCELLED", "OPTIMIZER_STUDY_FAILED"}
                for item in trial_payload
            )
            if retryable and study.status == "running":
                blocked = execution_block_reason(study, self._clock())
                actions.append({"action": "retry", "available": blocked is None,
                                "reason": "可重试失败候选" if blocked is None else "评测预算或截止时间已到，无法重试"})

            return {
                "study": self._inspect_study(study.id),
                "rounds": [rounds[key] for key in sorted(rounds)],
                "trials": trial_payload,
                "frontier": [
                    {
                        "trial_id": trial_id,
                        "ordinal": next(
                            item["ordinal"] for item in trial_payload if item["id"] == trial_id
                        ),
                    }
                    for trial_id in frontier_ids
                ],
                "recommendation": recommendation_summary,
                "actions": actions,
            }
