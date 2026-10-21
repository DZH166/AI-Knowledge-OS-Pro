"""Typed internal seams and single-source lifecycle facts for the optimizer."""

from __future__ import annotations

from typing import Protocol

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
