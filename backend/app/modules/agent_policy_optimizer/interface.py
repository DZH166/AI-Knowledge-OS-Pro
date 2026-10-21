from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.modules.agent_policy_optimizer.contracts import (
    CancelStudy,
    ConvertRecommendation,
    ExecuteTrial,
    ExportComparison,
    FailStudy,
    NextRound,
    OptimizerReadQuery,
    RecoverOptimizations,
    RetryTrial,
    StartStudy,
    StudyCommand,
)


class AgentPolicyOptimizer(Protocol):
    """Small public surface for the V5.4A-V5.7 retrieval optimizer workbench."""

    def submit(self, command: StudyCommand) -> dict[str, object]: ...

    def inspect(self, query: OptimizerReadQuery) -> dict[str, object]: ...

    def execute(self, command: ExecuteTrial, executor: "object") -> dict[str, object]: ...

    def recover(self, command: RecoverOptimizations) -> int: ...

    def convert_to_draft(self, command: ConvertRecommendation) -> dict[str, object]: ...

    def retry_trial(self, command: RetryTrial) -> dict[str, object]: ...

    def fail_study(self, command: FailStudy) -> dict[str, object]: ...

    def start_next_round(self, command: NextRound) -> dict[str, object]: ...

    def inspect_overview(self, study_id: str) -> dict[str, object]: ...

    def create_from_template(self, **kwargs) -> dict[str, object]: ...

    def inspect_events(
        self, study_id: str, *, limit: int = 100, after: str | None = None
    ) -> dict[str, object]: ...

    def export_comparison(self, command: ExportComparison) -> dict[str, object]: ...

    def create_share_link(
        self, *, run_id: str, expires_in_days: int
    ) -> dict[str, object]: ...

    def resolve_share_link(self, *, token: str, now: datetime | None = None) -> dict[str, object]: ...

    def revoke_share_link(self, *, token: str) -> bool: ...


__all__ = [
    "AgentPolicyOptimizer",
    "NextRound",
    "ConvertRecommendation",
    "ExportComparison",
    "FailStudy",
    "RetryTrial",
    "CancelStudy",
    "ExecuteTrial",
    "RecoverOptimizations",
    "StartStudy",
    "StudyCommand",
]
