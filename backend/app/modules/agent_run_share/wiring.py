from __future__ import annotations

from typing import cast

from app.db.session import SessionLocal
from app.modules.agent_control.contracts import GetRunTrace, RunTrace
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_run_share.interface import AgentRunShare
from app.modules.agent_run_share.service import SqlAgentRunShare


def get_agent_run_share() -> AgentRunShare:
    control = SqlAgentControl(SessionLocal)
    return SqlAgentRunShare(
        SessionLocal,
        trace_reader=lambda run_id: cast(RunTrace, control.inspect(GetRunTrace(run_id=run_id))),
    )
