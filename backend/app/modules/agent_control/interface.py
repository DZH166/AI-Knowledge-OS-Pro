from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from app.modules.agent_control.contracts import (
    AgentControlCommand,
    AgentControlQuery,
    AgentControlResult,
    EvaluationDetail,
    EvaluationReceipt,
    ExecuteEvaluation,
    RecoverEvaluations,
)

if TYPE_CHECKING:
    from app.modules.agent_control.executor import EvaluationExecutor


class AgentControl(Protocol):
    def submit(self, command: AgentControlCommand) -> EvaluationReceipt: ...

    def inspect(self, query: AgentControlQuery) -> AgentControlResult: ...

    def execute(self, command: ExecuteEvaluation, executor: "EvaluationExecutor") -> EvaluationDetail: ...

    def recover(self, command: RecoverEvaluations) -> int: ...
