from __future__ import annotations

from app.db.session import SessionLocal
from app.core.config import settings
from app.modules.agent_control.interface import AgentControl
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_policy.contracts import GetActivePolicy, GetPolicy, PolicyDetail
from app.modules.agent_policy.wiring import get_agent_policy


_agent_control: AgentControl | None = None


def _resolve_policy(policy_id: str | None) -> PolicyDetail:
    query = GetPolicy(policy_id) if policy_id else GetActivePolicy()
    result = get_agent_policy().inspect(query)
    if not isinstance(result, PolicyDetail):
        raise RuntimeError("AgentPolicy returned an invalid policy detail result.")
    return result


def get_agent_control() -> AgentControl:
    global _agent_control
    if _agent_control is None:
        _agent_control = SqlAgentControl(
            SessionLocal,
            lease_seconds=settings.evaluation_lease_seconds,
            policy_resolver=_resolve_policy,
        )
    return _agent_control
