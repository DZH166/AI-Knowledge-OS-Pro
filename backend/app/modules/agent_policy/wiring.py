from __future__ import annotations

from app.db.session import SessionLocal
from app.modules.agent_policy.interface import AgentPolicy
from app.modules.agent_policy.service import SqlAgentPolicy


_agent_policy: AgentPolicy | None = None


def get_agent_policy() -> AgentPolicy:
    global _agent_policy
    if _agent_policy is None:
        _agent_policy = SqlAgentPolicy(SessionLocal)
    return _agent_policy
