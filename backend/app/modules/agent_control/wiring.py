from __future__ import annotations

from app.db.session import SessionLocal
from app.core.config import settings
from app.modules.agent_control.interface import AgentControl
from app.modules.agent_control.service import SqlAgentControl


_agent_control: AgentControl | None = None


def get_agent_control() -> AgentControl:
    global _agent_control
    if _agent_control is None:
        _agent_control = SqlAgentControl(
            SessionLocal,
            lease_seconds=settings.evaluation_lease_seconds,
        )
    return _agent_control
