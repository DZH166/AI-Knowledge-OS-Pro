"""Bounded retry and operator-failure commands for optimizer Studies."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.optimizer import OptimizationStudy, OptimizationTrial
from app.models.outbox import OutboxMessage
from app.modules.agent_control.sanitization import sanitize_fact
from app.modules.agent_policy_optimizer.contracts import FailReceipt, FailStudy, RetryReceipt, RetryTrial
from app.modules.agent_policy_optimizer.internal import (
    BudgetReader,
    CANCELLED_MESSAGE,
    EVENT_STUDY_FAILED,
    EVENT_TRIAL_CANCELLED,
    EventAppender,
    TRIAL_TOPIC,
    required_study,
    required_trial,
)


SessionFactory = Callable[[], Session]


class OptimizerTerminalCommands:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        clock: Callable[[], datetime],
        append_event: EventAppender,
        read_budget: BudgetReader,
    ) -> None:
        self._sessions = session_factory
        self._clock = clock
        self._append_event = append_event
        self._read_budget = read_budget

    def retry_trial(self, command: RetryTrial) -> RetryReceipt:
        """Revive one failed trial: failed -> pending with its outbox row back.

        Guarded by the owning study lifecycle (only running studies retry) and
        by the evaluation budget (started_evaluations < max_evaluations).
        """

        now = self._clock()
        with self._sessions() as session, session.begin():
            trial = required_trial(session, command.trial_id)
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
            budget = self._read_budget(study.budget_json)
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

    def fail_study(self, command: FailStudy) -> FailReceipt:
        """Operator stop: mark the study failed and terminate unfinished work."""

        now = self._clock()
        with self._sessions() as session, session.begin():
            study = required_study(session, command.study_id)
            current_id = study.id
            current_status = study.status
            if current_status not in {"pending", "running"}:
                return {"study_id": current_id, "status": current_status, "cancelled": False}
            study.status = "failed"
            study.finished_at = now
            reason = sanitize_fact(command.reason or "operator request", maximum_length=200)
            cancelled_trials = session.scalars(
                select(OptimizationTrial).where(
                    OptimizationTrial.study_id == study.id,
                    OptimizationTrial.status.in_(["pending", "running", "completing"]),
                )
            ).all()
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
            for trial in cancelled_trials:
                self._append_event(
                    session,
                    study,
                    EVENT_TRIAL_CANCELLED,
                    {"trial_id": trial.id, "ordinal": trial.ordinal},
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
            self._append_event(
                session,
                study,
                EVENT_STUDY_FAILED,
                {"reason": reason},
            )
            return {"study_id": current_id, "status": "failed", "cancelled": False}

