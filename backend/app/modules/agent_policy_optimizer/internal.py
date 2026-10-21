"""Typed internal seams and single-source lifecycle facts for the optimizer."""

from __future__ import annotations

from typing import Protocol
from datetime import UTC, datetime
import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationStudy, OptimizationTrial
from app.modules.agent_policy.interface import AgentPolicy
from app.modules.agent_policy_optimizer.contracts import (
    QualifiedTrial,
    StudyBudget,
    StudyDetailView,
)


TRIAL_TOPIC = "agent.optimize.trial"
CANCELLED_MESSAGE = "Study cancelled by operator."

EVENT_STUDY_CREATED = "study_created"
EVENT_STUDY_STARTED = "study_started"
EVENT_TRIAL_CREATED = "trial_created"
EVENT_TRIAL_COMPLETED = "trial_completed"
EVENT_TRIAL_FAILED = "trial_failed"
EVENT_TRIAL_CANCELLED = "trial_cancelled"
EVENT_ROUND_STARTED = "round_started"
EVENT_RECOMMENDATION_UPDATED = "recommendation_updated"
EVENT_STUDY_COMPLETED = "study_completed"
EVENT_STUDY_FAILED = "study_failed"
EVENT_STUDY_CANCELLED = "study_cancelled"
EVENT_DRAFT_CONVERTED = "draft_converted"


class QualificationReader(Protocol):
    def __call__(
        self, session: Session, trials: list[OptimizationTrial]
    ) -> list[tuple[QualifiedTrial, OptimizationTrial]]: ...


class EventAppender(Protocol):
    def __call__(
        self,
        session: Session,
        study: OptimizationStudy,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None: ...


class BudgetReader(Protocol):
    def __call__(self, value: str) -> StudyBudget: ...


class StudyDetailReader(Protocol):
    def __call__(self, study_id: str) -> StudyDetailView: ...


class PolicyServiceFactory(Protocol):
    def __call__(self) -> AgentPolicy: ...


def lock_study(session: Session, study_id: str) -> OptimizationStudy:
    """Serialize mutations before reading a Study's shared budget and state.

    The no-op UPDATE obtains a write lock on SQLite and a row lock on SQL
    servers. It must precede lifecycle reads, not just the final write.
    """
    session.execute(
        update(OptimizationStudy).where(OptimizationStudy.id == study_id)
        .values(id=OptimizationStudy.id).execution_options(synchronize_session=False)
    )
    session.expire_all()
    return required_study(session, study_id)


def lock_trial_study(session: Session, trial_id: str) -> OptimizationStudy:
    study_id = session.scalar(select(OptimizationTrial.study_id).where(OptimizationTrial.id == trial_id))
    if study_id is None:
        required_trial(session, trial_id)
    return lock_study(session, study_id)


def deadline_reached(study: OptimizationStudy, now: datetime) -> bool:
    deadline = effective_deadline(study)
    return deadline is not None and deadline <= now


def effective_deadline(study: OptimizationStudy) -> datetime | None:
    # Pre-audit SQLite rows lost offsets; the budget JSON retained them.
    raw = json.loads(study.budget_json).get("deadline_at")
    deadline = datetime.fromisoformat(raw) if raw else study.deadline_at
    if deadline is None:
        return None
    return (deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)).astimezone(UTC)


def execution_block_reason(study: OptimizationStudy, now: datetime) -> str | None:
    if study.status != "running":
        return "OPTIMIZER_STUDY_NOT_RUNNING"
    if deadline_reached(study, now):
        return "OPTIMIZER_DEADLINE_REACHED"
    budget = json.loads(study.budget_json)
    usage = json.loads(study.budget_usage_json)
    if int(usage.get("started_evaluations", 0)) >= int(budget["max_evaluations"]):
        return "OPTIMIZER_BUDGET_EXHAUSTED"
    return None


def required_study(session: Session, study_id: str) -> OptimizationStudy:
    study = session.get(OptimizationStudy, study_id)
    if study is None:
        raise ServiceError(
            code="OPTIMIZER_STUDY_NOT_FOUND",
            message="Optimizer study does not exist.",
            status_code=404,
        )
    return study


def required_trial(session: Session, trial_id: str) -> OptimizationTrial:
    trial = session.get(OptimizationTrial, trial_id)
    if trial is None:
        raise ServiceError(
            code="OPTIMIZER_TRIAL_NOT_FOUND",
            message="Optimizer trial does not exist.",
            status_code=404,
        )
    return trial


def required_policy(session: Session, policy_id: str) -> AgentPolicyVersion:
    policy = session.get(AgentPolicyVersion, policy_id)
    if policy is None:
        raise ServiceError(
            code="OPTIMIZER_POLICY_NOT_FOUND",
            message="Agent policy not found.",
            status_code=404,
        )
    return policy
