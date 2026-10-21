from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import ServiceError
from app.models.agent_run import AgentRun
from app.modules.agent_policy.config import RetrievalPolicyConfig, policy_config_from_snapshot
from app.modules.agent_policy.decision import RetrievalDecisionPolicy


@dataclass(frozen=True, slots=True)
class PinnedDecisionPolicy:
    id: str
    version: int
    config_sha256: str
    config_json: str
    config: RetrievalPolicyConfig

    @classmethod
    def from_run(cls, run: AgentRun) -> PinnedDecisionPolicy | None:
        values = (
            run.decision_policy_id,
            run.decision_policy_version,
            run.decision_policy_fingerprint,
            run.decision_policy_snapshot_json,
        )
        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise ServiceError(
                code="POLICY_SNAPSHOT_INVALID",
                message="The Run policy snapshot is incomplete.",
                status_code=409,
            )
        try:
            config = policy_config_from_snapshot(
                str(run.decision_policy_snapshot_json),
                str(run.decision_policy_fingerprint),
            )
        except ValueError as exc:
            raise ServiceError(
                code="POLICY_SNAPSHOT_INVALID",
                message="The Run policy snapshot is invalid.",
                status_code=409,
            ) from exc
        return cls(
            id=str(run.decision_policy_id),
            version=int(run.decision_policy_version),
            config_sha256=str(run.decision_policy_fingerprint),
            config_json=str(run.decision_policy_snapshot_json),
            config=config,
        )

    def retrieval_policy(self) -> RetrievalDecisionPolicy:
        return RetrievalDecisionPolicy(
            self.config,
            policy_id=self.id,
            policy_version=self.version,
        )
