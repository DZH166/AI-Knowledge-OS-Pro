from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeSelectorSchema(StrictSchema):
    source_ids: list[int] = Field(default_factory=list)


class DeliverableSchema(StrictSchema):
    kind: Literal["answer", "research_report", "comparison", "evidence_gap_report"] = "answer"
    title: str | None = Field(default=None, max_length=255)


class BudgetLimitsSchema(StrictSchema):
    max_steps: int = Field(default=8, ge=1, le=64)
    max_tool_calls: int = Field(default=12, ge=1, le=128)
    max_model_calls: int = Field(default=6, ge=1, le=32)
    max_model_input_tokens: int = Field(default=24_000, ge=1, le=1_000_000)
    max_model_output_tokens: int = Field(default=6_000, ge=1, le=128_000)
    max_cost_micros: int = Field(default=1_000_000, ge=1, le=100_000_000)
    max_active_ms: int = Field(default=180_000, ge=1_000, le=3_600_000)
    max_no_new_evidence_rounds: int = Field(default=2, ge=1, le=10)
    max_query_rewrites: int = Field(default=3, ge=1, le=20)
    max_evidence_records: int = Field(default=40, ge=1, le=500)
    max_context_tokens: int = Field(default=16_000, ge=1, le=1_000_000)


class PermissionPolicySchema(StrictSchema):
    read_only: bool = True
    allow_scope_expansion: bool = False


class OpenRunSchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=120)
    space_id: int = Field(gt=0)
    goal: str = Field(min_length=1, max_length=4_000)
    scope: ScopeSelectorSchema = Field(default_factory=ScopeSelectorSchema)
    deliverable: DeliverableSchema = Field(default_factory=DeliverableSchema)
    mode: Literal["auto", "force_quick", "force_agent"] = "auto"
    budget: BudgetLimitsSchema = Field(default_factory=BudgetLimitsSchema)
    permissions: PermissionPolicySchema = Field(default_factory=PermissionPolicySchema)
    provider_mode: Literal["real", "demo", "recording"] = "real"


class SignalRunSchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=120)
    expected_version: int = Field(ge=1)
    signal: Literal["provide_input", "approve", "reject", "modify", "pause", "resume", "cancel"]
    response: dict[str, object] = Field(default_factory=dict)
    proposal_digest: str | None = Field(default=None, min_length=64, max_length=64)


class SubmissionSchema(StrictSchema):
    schema_version: Literal[1] = 1
    command_id: str
    run_id: str
    run_version: int
    status: str
    cursor: int
    replayed: bool


class ScopedRevisionSchema(StrictSchema):
    source_id: int
    revision_id: int
    index_revision_id: int
    content_hash: str


class ScopeSnapshotSchema(StrictSchema):
    space_id: int
    revisions: list[ScopedRevisionSchema] = Field(default_factory=list)


class DecisionPolicyViewSchema(StrictSchema):
    id: str
    version: int = Field(ge=1)
    config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class ArtifactOutcomeSchema(StrictSchema):
    kind: Literal["artifact"] = "artifact"
    artifact_id: str


class InsufficientEvidenceOutcomeSchema(StrictSchema):
    kind: Literal["insufficient_evidence"] = "insufficient_evidence"
    reason: str
    gaps: list[str] = Field(default_factory=list)


ResearchOutcomeSchema = Annotated[
    ArtifactOutcomeSchema | InsufficientEvidenceOutcomeSchema,
    Field(discriminator="kind"),
]


class RunViewSchema(StrictSchema):
    schema_version: Literal[1] = 1
    id: str
    space_id: int
    goal: str
    requested_mode: str
    effective_mode: str | None
    status: str
    phase: str
    version: int
    execution_epoch: int
    scope_snapshot: ScopeSnapshotSchema
    budget_limits: dict[str, int]
    budget_usage: dict[str, int]
    provider_mode: str
    last_event_cursor: int
    decision_policy: DecisionPolicyViewSchema | None = None
    final_artifact_id: str | None
    termination_reason: str | None
    cost_measurement: Literal["reported", "estimated", "unknown", "partial_unknown"]
    outcome: ResearchOutcomeSchema | None = None


class RunCatalogSchema(StrictSchema):
    schema_version: Literal[1] = 1
    items: list[RunViewSchema]
