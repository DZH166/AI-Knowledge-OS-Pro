from __future__ import annotations

from typing import Protocol

from app.modules.agent_policy.contracts import (
    AgentPolicyCommand,
    AgentPolicyQuery,
    AgentPolicyResult,
    PolicyReceipt,
    PolicySimulation,
    SimulatePolicy,
)


class AgentPolicy(Protocol):
    def submit(self, command: AgentPolicyCommand) -> PolicyReceipt: ...

    def inspect(self, query: AgentPolicyQuery) -> AgentPolicyResult: ...

    def simulate(self, query: SimulatePolicy) -> PolicySimulation: ...
