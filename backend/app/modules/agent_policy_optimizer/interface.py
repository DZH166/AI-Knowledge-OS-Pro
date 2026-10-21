from __future__ import annotations

from typing import Protocol

from app.modules.agent_policy_optimizer.contracts import (
    CancelStudy,
    ExecuteTrial,
    OptimizerReadQuery,
    RecoverOptimizations,
    StartStudy,
    StudyCommand,
)


class AgentPolicyOptimizer(Protocol):
    """Small public surface for the V5.4A retrieval optimizer."""

    def submit(self, command: StudyCommand) -> dict[str, object]: ...

    def inspect(self, query: OptimizerReadQuery) -> dict[str, object]: ...

    def execute(self, command: ExecuteTrial, executor: "object") -> dict[str, object]: ...

    def recover(self, command: RecoverOptimizations) -> int: ...


__all__ = [
    "AgentPolicyOptimizer",
    "CancelStudy",
    "ExecuteTrial",
    "RecoverOptimizations",
    "StartStudy",
    "StudyCommand",
]
