from __future__ import annotations

import os
import socket

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.agent_policy_optimizer.contracts import ExecuteTrial
from app.modules.agent_policy_optimizer.executor import FixedSubprocessTrialAdapter
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer


def run_optimization_trial(trial_id: str) -> dict[str, object]:
    """RQ entrypoint for one durable, deterministic, zero-provider trial."""

    worker_id = f"{settings.worker_name or socket.gethostname()}:{os.getpid()}:{trial_id}"
    optimizer = SqlAgentPolicyOptimizer(
        SessionLocal,
        lease_seconds=settings.evaluation_lease_seconds,
        evaluation_lease_seconds=settings.evaluation_lease_seconds,
    )
    detail = optimizer.execute(
        ExecuteTrial(trial_id=trial_id, worker_id=worker_id),
        FixedSubprocessTrialAdapter(timeout_seconds=settings.evaluation_timeout_seconds),
    )
    return {
        "trial_id": trial_id,
        "status": detail.get("status"),
        "score_millis": detail.get("score_millis"),
        "external_provider_calls": detail.get("external_provider_calls"),
        "failure_code": detail.get("failure_code"),
    }
