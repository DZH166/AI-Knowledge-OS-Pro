from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


Sha256 = Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartEvaluationSchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)


class EvaluationReceiptSchema(StrictSchema):
    schema_version: Literal[1] = 1
    evaluation_id: str = Field(min_length=1)
    status: Literal["queued", "running", "passed", "failed"]
    replayed: bool


class FailureTriageSchema(StrictSchema):
    category: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    retryable: bool
    supporting_facts: list[str]
    suggested_action: str = Field(min_length=1)


class EvaluationSummarySchema(StrictSchema):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: Literal["queued", "running", "passed", "failed"]
    mode: Literal["deterministic_recording"]
    policy_fingerprint: Sha256
    dataset_sha256: Sha256 | None
    case_count: int = Field(ge=0)
    case_pass_rate: float | None = Field(default=None, ge=0, le=1)
    external_provider_calls: int | None = Field(default=None, ge=0)
    failure_case_count: int = Field(ge=0)
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvaluationCaseSchema(StrictSchema):
    case_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    passed: bool
    expected_status: str
    actual_status: str
    source_recall: float = Field(ge=0, le=1)
    supported_claims: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    failure_reason: str | None


class EvaluationDetailSchema(StrictSchema):
    schema_version: Literal[1] = 1
    summary: EvaluationSummarySchema
    report_schema_version: int | None = Field(default=None, ge=1)
    evaluator_sha256: Sha256 | None
    dataset_name: str | None
    category_counts: dict[str, int]
    metrics: dict[str, int | float]
    hard_gates: dict[str, bool]
    cases: list[EvaluationCaseSchema]
    failure_case_ids: list[str]
    provider_boundary: str = Field(min_length=1)
    triage: FailureTriageSchema
    error_code: str | None
    error_message: str | None


class EvaluationCatalogSchema(StrictSchema):
    schema_version: Literal[1] = 1
    items: list[EvaluationSummarySchema]


class MetricDeltaSchema(StrictSchema):
    metric: str
    left: float
    right: float
    delta: float
    preferred_direction: Literal["higher", "lower"]
    improved: bool
    regressed: bool


class GateChangeSchema(StrictSchema):
    gate: str
    left: bool
    right: bool


class EvaluationComparisonSchema(StrictSchema):
    schema_version: Literal[1] = 1
    left_id: str
    right_id: str
    compatible: bool
    incompatibility_reasons: list[str]
    verdict: Literal["improved", "stable", "regressed", "incomparable"]
    policy_changed: bool
    left_policy_fingerprint: Sha256
    right_policy_fingerprint: Sha256
    metric_deltas: list[MetricDeltaSchema]
    gate_changes: list[GateChangeSchema]
    new_failure_case_ids: list[str]
    resolved_failure_case_ids: list[str]

    @model_validator(mode="after")
    def validate_policy_change_disclosure(self) -> Self:
        changed = self.left_policy_fingerprint != self.right_policy_fingerprint
        if self.policy_changed != changed:
            raise ValueError("policy_changed must match the policy fingerprints")
        return self


class TraceEventSchema(StrictSchema):
    sequence: int = Field(ge=1)
    run_version: int = Field(ge=1)
    event_type: str
    visibility: str
    redacted: bool
    facts: list[str]
    elapsed_ms: int = Field(ge=0)
    delta_ms: int = Field(ge=0)
    step_id: str | None
    tool_call_id: str | None


class TraceToolCallSchema(StrictSchema):
    id: str
    tool_name: str
    tool_version: str
    effect: str
    status: str
    arguments_digest: Sha256
    error_code: str | None
    duration_ms: int | None = Field(default=None, ge=0)


class TraceModelCallSchema(StrictSchema):
    id: str
    operation: str
    provider: str
    model: str
    status: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    retries: int = Field(ge=0)
    usage_estimated: bool
    error_code: str | None


class PolicyFactSchema(StrictSchema):
    policy_id: str
    version: str
    source: str


class ReplayIntegritySchema(StrictSchema):
    digest: Sha256
    sequence_contiguous: bool
    trace_id_consistent: bool
    stored_terminal_state: str
    replayed_terminal_state: str | None
    stored_state_matches: bool
    event_count: int = Field(ge=0)
    redacted_event_count: int = Field(ge=0)
    checkpoint_count: int = Field(ge=0)
    latest_checkpoint_checksum: Sha256 | None


class RunTraceSchema(StrictSchema):
    schema_version: Literal[1] = 1
    run_id: str
    trace_id: str
    goal: str
    requested_mode: str
    effective_mode: str | None
    status: str
    phase: str
    provider_mode: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    active_elapsed_ms: int = Field(ge=0)
    budget_limits: dict[str, int]
    budget_usage: dict[str, int]
    events: list[TraceEventSchema]
    tool_calls: list[TraceToolCallSchema]
    model_calls: list[TraceModelCallSchema]
    policies: list[PolicyFactSchema]
    replay: ReplayIntegritySchema
    triage: FailureTriageSchema
    warnings: list[str]
