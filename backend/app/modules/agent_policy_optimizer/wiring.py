from __future__ import annotations

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.agent_policy_optimizer.interface import AgentPolicyOptimizer
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer


_optimizer: AgentPolicyOptimizer | None = None


def get_agent_policy_optimizer() -> AgentPolicyOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = SqlAgentPolicyOptimizer(
            SessionLocal,
            lease_seconds=settings.evaluation_lease_seconds,
        )
    return _optimizer
