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
    """Small public surface for the V5.4A/V5.5 retrieval optimizer."""

    def submit(self, command: StudyCommand) -> dict[str, object]: ...

    def inspect(self, query: OptimizerReadQuery) -> dict[str, object]: ...

    def execute(self, command: ExecuteTrial, executor: "object") -> dict[str, object]: ...

    def recover(self, command: RecoverOptimizations) -> int: ...

    def convert_to_draft(self, command: ConvertRecommendation) -> dict[str, object]: ...

    def retry_trial(self, command: RetryTrial) -> dict[str, object]: ...

    def fail_study(self, command: FailStudy) -> dict[str, object]: ...

    def start_next_round(self, command: NextRound) -> dict[str, object]: ...


__all__ = [
    "AgentPolicyOptimizer",
    "NextRound",
    "ConvertRecommendation",
    "FailStudy",
    "RetryTrial",
    "CancelStudy",
    "ExecuteTrial",
    "RecoverOptimizations",
    "StartStudy",
    "StudyCommand",
]
