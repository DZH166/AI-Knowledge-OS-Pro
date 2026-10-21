from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


Sha256 = str
SafeId = str


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrievalPolicyConfigSchema(StrictSchema):
    schema_version: Literal[1] = 1
    factual_top_k: StrictInt = Field(default=8, ge=1, le=50)
    comparative_top_k: StrictInt = Field(default=14, ge=1, le=50)
    temporal_top_k: StrictInt = Field(default=12, ge=1, le=50)
    minimum_score_millis: StrictInt = Field(default=0, ge=0, le=1_000)
    max_hits_per_source: StrictInt = Field(default=3, ge=1, le=20)
    neighbor_before: StrictInt = Field(default=1, ge=0, le=3)
    neighbor_after: StrictInt = Field(default=1, ge=0, le=3)


class CreatePolicySchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    base_policy_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")
    config: RetrievalPolicyConfigSchema


class ActivatePolicySchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=120)
    expected_active_policy_id: str = Field(
        min_length=1,
        max_length=36,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    evaluation_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")


class RollbackPolicySchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=120)
    expected_active_policy_id: str = Field(
        min_length=1,
        max_length=36,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class SimulatePolicySchema(StrictSchema):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")
    policy_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")


class PolicyReceiptSchema(StrictSchema):
    schema_version: Literal[1] = 1
    command_id: str
    policy_id: str
    version: int = Field(ge=1)
    status: Literal["draft", "active", "retired"]
    active_policy_id: str
    replayed: bool


class PolicySummarySchema(StrictSchema):
    id: str
    policy_key: str
    version: int = Field(ge=1)
    label: str
    status: Literal["draft", "active", "retired"]
    config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    base_policy_id: str | None
    has_been_active: bool
    created_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None


class PolicyDetailSchema(PolicySummarySchema):
    config: RetrievalPolicyConfigSchema


class PolicyCatalogSchema(StrictSchema):
    schema_version: Literal[1] = 1
    items: list[PolicySummarySchema] = Field(max_length=100)


class PolicyConfigChangeSchema(StrictSchema):
    field: Literal[
        "factual_top_k",
        "comparative_top_k",
        "temporal_top_k",
        "minimum_score_millis",
        "max_hits_per_source",
        "neighbor_before",
        "neighbor_after",
    ]
    left: int
    right: int


class PolicyComparisonSchema(StrictSchema):
    schema_version: Literal[1] = 1
    left_id: str
    right_id: str
    left_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    right_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    compatible: bool
    incompatibility_reasons: list[str]
    changes: list[PolicyConfigChangeSchema]

    @model_validator(mode="after")
    def validate_comparison(self) -> "PolicyComparisonSchema":
        if not self.compatible and self.changes:
            raise ValueError("Incompatible policies cannot expose field changes.")
        return self


class PolicySimulationDecisionSchema(StrictSchema):
    sequence: int = Field(ge=1)
    tool: Literal["search_evidence", "read_neighbors"]
    changed: bool
    recorded_top_k: int | None = None
    candidate_top_k: int | None = None
    recorded_before: int | None = None
    candidate_before: int | None = None
    recorded_after: int | None = None
    candidate_after: int | None = None


class PolicySimulationSchema(StrictSchema):
    schema_version: Literal[1] = 1
    run_id: str
    policy_id: str
    policy_version: int = Field(ge=1)
    changed_decision_count: int = Field(ge=0)
    projected_candidate_window_delta: int
    projected_neighbor_context_delta: int
    digest: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    boundary: str = Field(min_length=1)
    decisions: list[PolicySimulationDecisionSchema]

    @model_validator(mode="after")
    def validate_simulation(self) -> "PolicySimulationSchema":
        if "no model, retrieval, evidence query, tool, provider, or write" not in self.boundary:
            raise ValueError("Counterfactual execution boundary is missing.")
        if self.changed_decision_count != sum(item.changed for item in self.decisions):
            raise ValueError("Changed decision count does not match decision rows.")
        if [item.sequence for item in self.decisions] != list(range(1, len(self.decisions) + 1)):
            raise ValueError("Simulation decisions must be contiguous and ordered.")
        return self
