"""Optimizer executor protocol and the fixed subprocess trial adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from app.modules.agent_policy.config import policy_config_from_snapshot
from app.modules.agent_control.executor import (
    EvaluationExecutionError,
    EvaluationPolicySnapshot,
    FixedSubprocessEvaluationAdapter,
)


@dataclass(frozen=True, slots=True)
class TrialPolicySnapshot:
    trial_id: str
    config_sha256: str
    config_json: str

    def __post_init__(self) -> None:
        policy_config_from_snapshot(self.config_json, self.config_sha256)


@runtime_checkable
class TrialExecutor(Protocol):
    def run(self, trial_id: str, policy_snapshot: TrialPolicySnapshot | None) -> Mapping[str, object]: ...


class FixedSubprocessTrialAdapter:
    """Run the reviewed fixed deterministic evaluator for one candidate trial.

    The adapter reuses the audited V5.2 subprocess adapter verbatim; the
    candidate configuration is injected as a policy snapshot file so the
    evaluator consumes exactly the intended frozen configuration.
    """

    def __init__(
        self,
        *,
        timeout_seconds: int = 900,
        temporary_root: Path | None = None,
        root: Path | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._temporary_root = temporary_root
        self._root = root

    def _adapter(self) -> FixedSubprocessEvaluationAdapter:
        options: dict[str, object] = {"timeout_seconds": self._timeout_seconds}
        if self._temporary_root is not None:
            options["temporary_root"] = self._temporary_root
        if self._root is not None:
            options["root"] = self._root
        return FixedSubprocessEvaluationAdapter(**options)  # type: ignore[arg-type]

    def run(self, trial_id: str, policy_snapshot: TrialPolicySnapshot | None) -> Mapping[str, object]:
        if policy_snapshot is None:
            raise EvaluationExecutionError(
                "OPTIMIZER_TRIAL_SNAPSHOT_MISSING",
                "Optimizer trials must run against an explicit candidate snapshot.",
            )
        evaluation_snapshot = EvaluationPolicySnapshot(
            policy_id=policy_snapshot.trial_id,
            policy_version=1,
            config_sha256=policy_snapshot.config_sha256,
            config_json=policy_snapshot.config_json,
        )
        return self._adapter().run(trial_id, evaluation_snapshot)


__all__ = [
    "EvaluationExecutionError",
    "FixedSubprocessTrialAdapter",
    "TrialExecutor",
    "TrialPolicySnapshot",
]
