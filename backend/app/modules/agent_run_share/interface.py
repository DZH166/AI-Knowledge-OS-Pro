from __future__ import annotations

from typing import Protocol

from app.modules.agent_control.contracts import RunTrace
from app.modules.agent_run_share.contracts import (
    GetSharedRunTrace,
    RevokeShareReceipt,
    ShareCommand,
    ShareLinkReceipt,
)


class AgentRunShare(Protocol):
    def submit(self, command: ShareCommand) -> ShareLinkReceipt | RevokeShareReceipt: ...

    def inspect(self, query: GetSharedRunTrace) -> RunTrace: ...
