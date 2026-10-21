from __future__ import annotations

import os
import socket

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.agent_control.contracts import ExecuteEvaluation
from app.modules.agent_control.executor import FixedSubprocessEvaluationAdapter
from app.modules.agent_control.service import SqlAgentControl


def run_agent_evaluation(evaluation_id: str) -> dict[str, object]:
    """RQ entrypoint for one fixed, deterministic, zero-provider evaluation."""

    worker_id = f"{settings.worker_name or socket.gethostname()}:{os.getpid()}:{evaluation_id}"
    control = SqlAgentControl(
        SessionLocal,
        lease_seconds=settings.evaluation_lease_seconds,
    )
    detail = control.execute(
        ExecuteEvaluation(evaluation_id=evaluation_id, worker_id=worker_id),
        FixedSubprocessEvaluationAdapter(timeout_seconds=settings.evaluation_timeout_seconds),
    )
    return {
        "evaluation_id": evaluation_id,
        "status": detail.summary.status.value,
        "case_count": detail.summary.case_count,
        "case_pass_rate": detail.summary.case_pass_rate,
        "external_provider_calls": detail.summary.external_provider_calls,
        "failure_case_count": detail.summary.failure_case_count,
        "error_code": detail.error_code,
    }
