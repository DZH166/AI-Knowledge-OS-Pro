from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.modules.evidence_agent.contracts import (
    AgentQuery,
    AgentQueryResult,
    ContinueRun,
    OpenRun,
    RunFrame,
    SignalRun,
    Submission,
)


class EvidenceAgent(Protocol):
    """Stable application seam; transport and worker adapters depend only on this."""

    def submit(self, command: OpenRun | ContinueRun | SignalRun) -> Submission: ...

    def inspect(self, query: AgentQuery) -> AgentQueryResult: ...

    def follow(self, run_id: str, cursor: int | None = None) -> AsyncIterator[RunFrame]: ...
