from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal


MetricValue = int | float


class EvaluationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class ComparisonVerdict(StrEnum):
    IMPROVED = "improved"
    STABLE = "stable"
    REGRESSED = "regressed"
    INCOMPARABLE = "incomparable"


class FailureCategory(StrEnum):
    NONE = "none"
    DISPATCH_FAILED = "dispatch_failed"
    WORKER_INTERRUPTED = "worker_interrupted"
    EXECUTOR_TIMEOUT = "executor_timeout"
    EXECUTOR_FAILED = "executor_failed"
    MALFORMED_REPORT = "malformed_report"
    EVALUATION_GATE_FAILED = "evaluation_gate_failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    TOOL_FAILED = "tool_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    USER_CANCELLED = "user_cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FailureTriage:
    category: FailureCategory
    summary: str
    retryable: bool
    supporting_facts: tuple[str, ...]
    suggested_action: str


@dataclass(frozen=True, slots=True)
class StartEvaluation:
    request_id: str
    label: str


@dataclass(frozen=True, slots=True)
class ExecuteEvaluation:
    evaluation_id: str
    worker_id: str


@dataclass(frozen=True, slots=True)
class RecoverEvaluations:
    now: datetime


@dataclass(frozen=True, slots=True)
class ListEvaluations:
    status: EvaluationStatus | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class GetEvaluation:
    evaluation_id: str


@dataclass(frozen=True, slots=True)
class CompareEvaluations:
    left_id: str
    right_id: str


@dataclass(frozen=True, slots=True)
class GetRunTrace:
    run_id: str


AgentControlCommand = StartEvaluation
AgentControlQuery = ListEvaluations | GetEvaluation | CompareEvaluations | GetRunTrace


@dataclass(frozen=True, slots=True)
class EvaluationReceipt:
    evaluation_id: str
    status: EvaluationStatus
    replayed: bool


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    case_id: str
    category: str
    passed: bool
    expected_status: str
    actual_status: str
    source_recall: float
    supported_claims: int
    latency_ms: float
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    id: str
    label: str
    status: EvaluationStatus
    mode: str
    policy_fingerprint: str
    dataset_sha256: str | None
    case_count: int
    case_pass_rate: float | None
    external_provider_calls: int | None
    failure_case_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class EvaluationDetail:
    summary: EvaluationSummary
    schema_version: int | None
    evaluator_sha256: str | None
    dataset_name: str | None
    category_counts: dict[str, int]
    metrics: dict[str, MetricValue]
    hard_gates: dict[str, bool]
    cases: tuple[EvaluationCaseResult, ...]
    failure_case_ids: tuple[str, ...]
    provider_boundary: str
    triage: FailureTriage
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationCatalog:
    items: tuple[EvaluationSummary, ...]


@dataclass(frozen=True, slots=True)
class MetricDelta:
    metric: str
    left: float
    right: float
    delta: float
    preferred_direction: Literal["higher", "lower"]
    improved: bool
    regressed: bool


@dataclass(frozen=True, slots=True)
class GateChange:
    gate: str
    left: bool
    right: bool


@dataclass(frozen=True, slots=True)
class EvaluationComparison:
    left_id: str
    right_id: str
    compatible: bool
    incompatibility_reasons: tuple[str, ...]
    verdict: ComparisonVerdict
    policy_changed: bool
    left_policy_fingerprint: str
    right_policy_fingerprint: str
    metric_deltas: tuple[MetricDelta, ...]
    gate_changes: tuple[GateChange, ...]
    new_failure_case_ids: tuple[str, ...]
    resolved_failure_case_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TraceEvent:
    sequence: int
    run_version: int
    event_type: str
    visibility: str
    redacted: bool
    facts: tuple[str, ...]
    elapsed_ms: int
    delta_ms: int
    step_id: str | None
    tool_call_id: str | None


@dataclass(frozen=True, slots=True)
class TraceToolCall:
    id: str
    tool_name: str
    tool_version: str
    effect: str
    status: str
    arguments_digest: str
    error_code: str | None
    duration_ms: int | None


@dataclass(frozen=True, slots=True)
class TraceModelCall:
    id: str
    operation: str
    provider: str
    model: str
    status: str
    input_tokens: int
    output_tokens: int
    cost_micros: int
    latency_ms: int
    retries: int
    usage_estimated: bool
    error_code: str | None


@dataclass(frozen=True, slots=True)
class PolicyFact:
    policy_id: str
    version: str
    source: str


@dataclass(frozen=True, slots=True)
class ReplayIntegrity:
    digest: str
    sequence_contiguous: bool
    trace_id_consistent: bool
    stored_terminal_state: str
    replayed_terminal_state: str | None
    stored_state_matches: bool
    event_count: int
    redacted_event_count: int
    checkpoint_count: int
    latest_checkpoint_checksum: str | None


@dataclass(frozen=True, slots=True)
class RunTrace:
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
    active_elapsed_ms: int
    budget_limits: dict[str, int]
    budget_usage: dict[str, int]
    events: tuple[TraceEvent, ...]
    tool_calls: tuple[TraceToolCall, ...]
    model_calls: tuple[TraceModelCall, ...]
    policies: tuple[PolicyFact, ...]
    replay: ReplayIntegrity
    triage: FailureTriage
    warnings: tuple[str, ...] = field(default_factory=tuple)


AgentControlResult = EvaluationCatalog | EvaluationDetail | EvaluationComparison | RunTrace
