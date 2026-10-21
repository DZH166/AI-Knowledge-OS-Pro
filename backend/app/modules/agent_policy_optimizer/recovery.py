"""Crash recovery helpers for the V5.4A optimizer (lease takeover).

The durable invariants enforced here:

- Expired running trials return to `pending` so any worker can re-claim them.
- Completed/failed/cancelled trials are never touched by recovery.
- Duplicate outbox rows for one trial cannot enqueue the evaluation twice
  (unique dedupe_key + unique trial evaluation_id act as write fences).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.agent_policy_optimizer.contracts import RecoverOptimizations
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer


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
        return {"recovered_trials": recovered, "requeued_trials": recovered}


__all__ = ["OptimizerRecovery"]
