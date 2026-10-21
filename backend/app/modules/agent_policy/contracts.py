from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from app.modules.agent_policy.config import RetrievalPolicyConfig


RequirementKind = Literal["factual", "comparative", "temporal"]


class PolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class CreatePolicy:
    request_id: str
    label: str
    base_policy_id: str
    config: RetrievalPolicyConfig


@dataclass(frozen=True, slots=True)
class ActivatePolicy:
    request_id: str
    policy_id: str
    expected_active_policy_id: str
    evaluation_id: str


@dataclass(frozen=True, slots=True)
class RollbackPolicy:
    request_id: str
    policy_id: str
    expected_active_policy_id: str


@dataclass(frozen=True, slots=True)
class ListPolicies:
    status: PolicyStatus | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class GetPolicy:
    policy_id: str


@dataclass(frozen=True, slots=True)
class GetActivePolicy:
    pass


@dataclass(frozen=True, slots=True)
class ComparePolicies:
    left_id: str
    right_id: str


@dataclass(frozen=True, slots=True)
class SimulatePolicy:
    run_id: str
    policy_id: str


AgentPolicyCommand = CreatePolicy | ActivatePolicy | RollbackPolicy
AgentPolicyQuery = ListPolicies | GetPolicy | GetActivePolicy | ComparePolicies


@dataclass(frozen=True, slots=True)
class PolicyReceipt:
    command_id: str
    policy_id: str
    version: int
    status: PolicyStatus
    active_policy_id: str
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class PolicySummary:
    id: str
    policy_key: str
    version: int
    label: str
    status: PolicyStatus
    config_sha256: str
    base_policy_id: str | None
    has_been_active: bool
    created_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None


@dataclass(frozen=True, slots=True)
class PolicyDetail:
    id: str
    policy_key: str
    version: int
    label: str
    status: PolicyStatus
    config_sha256: str
    base_policy_id: str | None
    has_been_active: bool
    created_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None
    config: RetrievalPolicyConfig


@dataclass(frozen=True, slots=True)
class PolicyCatalog:
    items: tuple[PolicySummary, ...]


@dataclass(frozen=True, slots=True)
class PolicyConfigChange:
    field: str
    left: int
    right: int


@dataclass(frozen=True, slots=True)
class PolicyConfigComparison:
    compatible: bool
    incompatibility_reasons: tuple[str, ...]
    changes: tuple[PolicyConfigChange, ...]


@dataclass(frozen=True, slots=True)
class PolicyComparison:
    left_id: str
    right_id: str
    left_fingerprint: str
    right_fingerprint: str
    compatible: bool
    incompatibility_reasons: tuple[str, ...]
    changes: tuple[PolicyConfigChange, ...]


@dataclass(frozen=True, slots=True)
class SearchPolicyDecision:
    policy_id: str
    policy_version: int
    requirement_kind: RequirementKind
    top_k: int
    minimum_score_millis: int
    max_hits_per_source: int

    def audit_payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "reason_code": f"requirement_kind:{self.requirement_kind}",
            "top_k": self.top_k,
            "minimum_score_millis": self.minimum_score_millis,
            "max_hits_per_source": self.max_hits_per_source,
        }


@dataclass(frozen=True, slots=True)
class NeighborPolicyDecision:
    policy_id: str
    policy_version: int
    before: int
    after: int

    def audit_payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "reason_code": "bounded_neighbor_context",
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True, slots=True)
class PolicySimulationDecision:
    sequence: int
    tool: Literal["search_evidence", "read_neighbors"]
    changed: bool
    recorded_top_k: int | None = None
    candidate_top_k: int | None = None
    recorded_before: int | None = None
    candidate_before: int | None = None
    recorded_after: int | None = None
    candidate_after: int | None = None


@dataclass(frozen=True, slots=True)
class PolicySimulation:
    run_id: str
    policy_id: str
    policy_version: int
    changed_decision_count: int
    projected_candidate_window_delta: int
    projected_neighbor_context_delta: int
    digest: str
    boundary: str
    decisions: tuple[PolicySimulationDecision, ...]


AgentPolicyResult = PolicyCatalog | PolicyDetail | PolicyComparison
