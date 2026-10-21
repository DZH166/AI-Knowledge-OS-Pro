"""Human-gated optimizer recommendation to policy-draft conversion."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_policy import AgentPolicyVersion
from app.models.optimizer import OptimizationTrial
from app.modules.agent_control.sanitization import contains_sensitive_text
from app.modules.agent_policy.config import policy_config_from_snapshot
from app.modules.agent_policy_optimizer.contracts import ConvertDraftReceipt, ConvertRecommendation
from app.modules.agent_policy_optimizer.pareto import pareto_frontier
from app.modules.agent_policy_optimizer.internal import (
    EVENT_DRAFT_CONVERTED,
    EventAppender,
    PolicyServiceFactory,
    QualificationReader,
    required_study,
    required_trial,
)


SessionFactory = Callable[[], Session]


class OptimizerDraftConverter:
    """Creates a draft only; activation remains outside this collaborator."""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        policy_service: PolicyServiceFactory,
        qualify_rows: QualificationReader,
        append_event: EventAppender,
    ) -> None:
        self._sessions = session_factory
        self._policy_service = policy_service
        self._qualify_rows = qualify_rows
        self._append_event = append_event

    def convert(self, command: ConvertRecommendation) -> ConvertDraftReceipt:
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
            study = required_study(session, command.study_id)
            trial = required_trial(session, command.trial_id)
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
                winner = required_trial(session, command.trial_id)
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
            self._append_event(
                session,
                study,
                EVENT_DRAFT_CONVERTED,
                {
                    "trial_id": trial.id,
                    "policy_id": policy.id,
                    "config_sha256": policy.config_sha256,
                },
            )
            return {
                "command_id": receipt.command_id,
                "policy_id": policy.id,
                "policy_version": policy.version,
                "status": policy.status,
                "policy_config_sha256": policy.config_sha256,
                "replayed": bool(receipt.replayed),
            }
