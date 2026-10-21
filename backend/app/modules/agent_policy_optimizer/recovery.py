"""Crash recovery helpers for the V5.4A optimizer (lease takeover).

The durable invariants enforced here:

- Expired running trials return to `pending` so any worker can re-claim them.
- Completed/failed/cancelled trials are never touched by recovery.
- Duplicate outbox rows for one trial cannot enqueue the evaluation twice
  (unique dedupe_key + unique trial evaluation_id act as write fences).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models.optimizer import OptimizationStudy, OptimizationTrial
from app.modules.agent_policy_optimizer.contracts import RecoverOptimizations
from app.modules.agent_policy_optimizer.service import CANCELLED_MESSAGE, TRIAL_TOPIC, SqlAgentPolicyOptimizer


class OptimizerRecovery:
    """Take over expired optimizer leases and re-drive interrupted studies."""

    def __init__(
        self,
        optimizer: SqlAgentPolicyOptimizer,
        *,
        grace_seconds: int = 30,
    ) -> None:
        if grace_seconds < 0:
            raise ValueError("grace_seconds must be non-negative")
        self._optimizer = optimizer
        self._grace_seconds = grace_seconds

    def recover_once(self, *, now: datetime | None = None) -> dict[str, int]:
        moment = now or datetime.now(UTC)
        cutoff = moment - timedelta(seconds=self._grace_seconds)
        recovered = self._optimizer.recover(RecoverOptimizations(now=cutoff))
        redriven = self._redrive_running_studies()
        return {"recovered_trials": recovered, "redriven_studies": redriven}

    def _redrive_running_studies(self) -> int:
        """Requeue pending trials of running studies whose outbox rows died.

        Dead-lettered dispatch rows for still-pending trials are reset to the
        pending queue so the work is not lost after a broker outage.
        """

        from app.models.outbox import OutboxMessage

        redriven = 0
        with self._optimizer._sessions() as session, session.begin():  # noqa: SLF001 - recovery owns the same session contract
            pending_trial_ids = session.scalars(
                select(OptimizationTrial.id).where(
                    OptimizationTrial.status == "pending",
                    OptimizationTrial.study_id.in_(
                        select(OptimizationStudy.id).where(OptimizationStudy.status == "running")
                    ),
                )
            ).all()
            if not pending_trial_ids:
                return 0
            result = session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.topic == TRIAL_TOPIC,
                    OutboxMessage.aggregate_id.in_(pending_trial_ids),
                    OutboxMessage.status == "dead_letter",
                    OutboxMessage.last_error != CANCELLED_MESSAGE,
                )
                .values(
                    status="pending",
                    attempt=0,
                    available_at=datetime.now(UTC),
                    lease_owner=None,
                    lease_expires_at=None,
                    last_error=None,
                )
                .execution_options(synchronize_session=False)
            )
            redriven = int(result.rowcount or 0)
        return redriven


__all__ = ["OptimizerRecovery"]
