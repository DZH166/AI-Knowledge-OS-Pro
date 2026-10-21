from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from app.modules.agent_control.sanitization import contains_sensitive_text


StudyObjectiveValue = Literal["quality_first", "balanced", "cost_first"]
StudyStatusValue = Literal["pending", "running", "completed", "cancelled", "failed"]
TrialStatusValue = Literal[
    "pending", "running", "completing", "completed", "failed", "cancelled"
]
MetricNameValue = Literal[
    "case_pass_rate",
    "mean_source_recall",
    "citation_completeness",
    "latency_ms",
    "retrieval_window",
    "external_provider_calls",
]
CategoryNameValue = Literal[
    "cancel_recovery",
    "cross_modal",
    "insufficient_evidence",
    "multi_hop",
    "prompt_injection",
    "single_hop",
    "version_conflict",
]
EventTypeValue = Literal[
    "study_created",
    "study_started",
    "trial_created",
    "trial_completed",
    "trial_failed",
    "trial_cancelled",
    "round_started",
    "recommendation_updated",
    "study_completed",
    "study_failed",
    "study_cancelled",
    "draft_converted",
]
ActionValue = Literal[
    "start", "next-round", "cancel", "fail", "retry", "convert-draft", "recover"
]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


_PROMPT_SHELL_CODE_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "reveal the system prompt",
    "you are now",
    "rm -rf",
    "__import__",
    "os.system",
    "subprocess",
    "eval(",
    "exec(",
)


def _reject_prompt_shell_code(value: str) -> str:
    lowered = value.lower()
    for pattern in _PROMPT_SHELL_CODE_PATTERNS:
        if pattern in lowered:
            raise ValueError("Free-text fields must not contain prompt, shell, or code fragments.")
    return value


_HARD_BOUNDS = {
    "factual_top_k": (1, 50),
    "comparative_top_k": (1, 50),
    "temporal_top_k": (1, 50),
    "minimum_score_millis": (0, 1000),
    "max_hits_per_source": (1, 20),
    "neighbor_before": (0, 3),
    "neighbor_after": (0, 3),
}


class SearchSpaceBoundSchema(StrictSchema):
    minimum: StrictInt = Field(ge=0)
    maximum: StrictInt = Field(ge=0)



class SearchSpaceSchema(StrictSchema):
    factual_top_k: SearchSpaceBoundSchema
    comparative_top_k: SearchSpaceBoundSchema
    temporal_top_k: SearchSpaceBoundSchema
    minimum_score_millis: SearchSpaceBoundSchema
    max_hits_per_source: SearchSpaceBoundSchema
    neighbor_before: SearchSpaceBoundSchema
    neighbor_after: SearchSpaceBoundSchema

    @model_validator(mode="after")
    def validate_bounds(self) -> "SearchSpaceSchema":
        for name, (hard_min, hard_max) in _HARD_BOUNDS.items():
            bound = getattr(self, name)
            if bound.minimum > bound.maximum:
                raise ValueError(f"{name} bound minimum exceeds maximum.")
            if bound.minimum < hard_min or bound.maximum > hard_max:
                raise ValueError(
                    f"{name} bounds must stay within the safe range {hard_min}..{hard_max}."
                )
        return self


class ScoreWeightsSchema(StrictSchema):
    quality_weight_permille: StrictInt = Field(ge=0, le=1000)
    cost_weight_permille: StrictInt = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def validate_positive_total(self) -> "ScoreWeightsSchema":
        if self.quality_weight_permille + self.cost_weight_permille <= 0:
            raise ValueError("At least one weight must be positive.")
        return self


class CreateStudySchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: StrictStr = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:@-]+$")
    label: StrictStr = Field(min_length=1, max_length=120)
    base_policy_id: StrictStr = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")
    objective: StudyObjectiveValue
    max_candidates: StrictInt = Field(ge=1, le=64)
    max_evaluations: StrictInt = Field(ge=1, le=128)
    search_space: SearchSpaceSchema
    weights: ScoreWeightsSchema
    seed: StrictInt = Field(ge=0, le=2_147_483_647)
    deadline_at: datetime | None = None
    warm_start_study_id: StrictStr | None = Field(
        default=None, min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$"
    )

    @field_validator("label")
    @classmethod
    def _label_is_safe(cls, value: str) -> str:
        return _reject_prompt_shell_code(value)

    @field_validator("deadline_at")
    @classmethod
    def _deadline_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("deadline_at must include an explicit timezone offset.")
        return value



class StudyIdempotencyNoteSchema(StrictSchema):
    replayed: bool = False


class BudgetUsageSchema(StrictSchema):
    created_trials: StrictInt = Field(ge=0)
    started_evaluations: StrictInt = Field(ge=0)


class StudyBudgetSchema(StrictSchema):
    max_candidates: StrictInt = Field(ge=1, le=64)
    max_evaluations: StrictInt = Field(ge=1, le=128)
    deadline_at: datetime | None = None

    @field_validator("deadline_at")
    @classmethod
    def normalize_deadline(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC)


class TrialMetricsSchema(StrictSchema):
    case_pass_rate: StrictFloat = Field(ge=0.0, le=1.0)
    mean_source_recall: StrictFloat = Field(ge=0.0, le=1.0)
    citation_completeness: StrictFloat = Field(ge=0.0, le=1.0)
    latency_ms: StrictFloat = Field(ge=0.0)
    retrieval_window: StrictInt = Field(ge=1)
    external_provider_calls: Literal[0]


class NormalizedMetricsSchema(StrictSchema):
    case_pass_rate: StrictFloat = Field(ge=0.0, le=1.0)
    mean_source_recall: StrictFloat = Field(ge=0.0, le=1.0)
    citation_completeness: StrictFloat = Field(ge=0.0, le=1.0)
    latency_ms: StrictFloat = Field(ge=0.0, le=1.0)
    retrieval_window: StrictFloat = Field(ge=0.0, le=1.0)
    external_provider_calls: StrictFloat = Field(ge=0.0, le=1.0)


class CategoryAggregateSchema(StrictSchema):
    passed: StrictInt = Field(ge=0)
    total: StrictInt = Field(ge=1)
    mean_source_recall: StrictFloat = Field(ge=0.0, le=1.0)


class CaseFactSchema(StrictSchema):
    case_id: StrictStr = Field(min_length=1, max_length=120)
    category: CategoryNameValue
    passed: StrictBool
    source_recall: StrictFloat = Field(ge=0.0, le=1.0)
    latency_ms: StrictFloat = Field(ge=0.0)


class CategoryStatsSchema(StrictSchema):
    schema_version: Literal[1]
    categories: dict[CategoryNameValue, CategoryAggregateSchema]
    cases: list[CaseFactSchema] = Field(min_length=60, max_length=60)

    @model_validator(mode="after")
    def validate_complete_categories(self) -> "CategoryStatsSchema":
        expected = {
            "cancel_recovery",
            "cross_modal",
            "insufficient_evidence",
            "multi_hop",
            "prompt_injection",
            "single_hop",
            "version_conflict",
        }
        if set(self.categories) != expected or {item.category for item in self.cases} != expected:
            raise ValueError("Category facts must contain all 7 fixed evaluation categories.")
        return self


class StudySummarySchema(StrictSchema):
    id: str
    label: str
    objective: StudyObjectiveValue
    status: StudyStatusValue
    base_policy_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    budget_usage: BudgetUsageSchema
    created_at: datetime


class StudyCatalogSchema(StrictSchema):
    items: list[StudySummarySchema]


class StudyDetailSchema(StrictSchema):
    id: str
    request_id: str
    label: str
    objective: StudyObjectiveValue
    status: StudyStatusValue
    base_policy_id: str
    base_policy_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    search_space: SearchSpaceSchema
    weights: ScoreWeightsSchema
    budget: StudyBudgetSchema
    budget_usage: BudgetUsageSchema
    seed: StrictInt
    algorithm_version: str
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    cancelled_at: datetime | None
    round_no: StrictInt = Field(default=1, ge=1)
    warm_start_study_id: str | None = None
    next_round_request_id: str | None = None


class TrialSummarySchema(StrictSchema):
    id: str
    study_id: str
    ordinal: StrictInt = Field(ge=1)
    status: TrialStatusValue
    config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    is_baseline: bool
    evaluation_id: str | None
    draft_policy_id: str | None = None
    category_stats: CategoryStatsSchema | None = None
    round_no: StrictInt = Field(default=1, ge=1)
    metrics: TrialMetricsSchema | None
    normalized_metrics: NormalizedMetricsSchema | None
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    recommendation_rank: StrictInt | None = Field(default=None, ge=1)
    failure_code: str | None
    attempt: StrictInt = Field(ge=0)
    external_provider_calls: StrictInt | None = Field(default=None, ge=0)
    created_at: datetime | None
    finished_at: datetime | None


class TrialCatalogSchema(StrictSchema):
    items: list[TrialSummarySchema]


class ParetoItemSchema(StrictSchema):
    trial_id: str
    ordinal: StrictInt = Field(ge=1)
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    eligible: bool
    config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    metrics: TrialMetricsSchema | None


class ParetoFrontierSchema(StrictSchema):
    study_id: str
    items: list[ParetoItemSchema]


class RecommendationCandidateSchema(StrictSchema):
    rank: StrictInt = Field(ge=1)
    trial_id: str
    policy_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    policy_snapshot_json: str
    evaluation_id: str
    evaluation_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    evaluation_report_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    score_millis: StrictInt = Field(ge=0, le=1000)
    dominates_baseline: bool
    improved_metrics: list[MetricNameValue]
    unchanged_metrics: list[MetricNameValue]
    regressed_metrics: list[MetricNameValue]
    rationale: str
    algorithm_version: str


class RecommendationBundleSchema(StrictSchema):
    study_id: str
    algorithm_version: str
    candidates: list[RecommendationCandidateSchema]


class StudyMutationReceiptSchema(StrictSchema):
    study_id: str
    status: StudyStatusValue
    created: StrictInt | None = Field(default=None, ge=0)
    cancelled: bool | None = None
    replayed: bool = False


class TrialReceiptSchema(TrialSummarySchema):
    pass


class RecoverReceiptSchema(StrictSchema):
    recovered_trials: StrictInt = Field(ge=0)


class CancelReceiptSchema(StrictSchema):
    study_id: str
    status: StudyStatusValue
    cancelled: bool


class ConvertDraftSchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: StrictStr = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:@-]+$")
    label: StrictStr | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("label")
    @classmethod
    def _label_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else _reject_prompt_shell_code(value)


class ConvertReceiptSchema(StrictSchema):
    command_id: str
    policy_id: str
    policy_version: StrictInt = Field(ge=1)
    status: Literal["draft", "active", "retired"]
    policy_config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    replayed: bool


class DiffChangeSchema(StrictSchema):
    field: str
    left: StrictInt
    right: StrictInt


class TrialSummaryForDiffSchema(StrictSchema):
    eligible: bool
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    case_pass_rate: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)


class DiffReceiptSchema(StrictSchema):
    study_id: str
    trial_id: str
    trial_config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    active_policy_id: str
    active_policy_version: StrictInt = Field(ge=1)
    active_config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    compatible: bool
    incompatibility_reasons: list[str]
    changes: list[DiffChangeSchema]
    trial_summary: TrialSummaryForDiffSchema


class RetryReceiptSchema(StrictSchema):
    trial_id: str
    status: Literal["pending"]


class FailStudySchema(StrictSchema):
    schema_version: Literal[1] = 1
    reason: StrictStr | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def _reason_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        checked = _reject_prompt_shell_code(value)
        if contains_sensitive_text(checked):
            raise ValueError("Reason must not contain secret-looking text.")
        return checked


class FailReceiptSchema(StrictSchema):
    study_id: str
    status: StudyStatusValue
    cancelled: bool


class NextRoundSchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: StrictStr = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:@-]+$")


class NextRoundReceiptSchema(StrictSchema):
    study_id: str
    round_no: StrictInt = Field(ge=1)
    created: StrictInt = Field(ge=0)
    replayed: bool


class CategoryComparisonRowSchema(StrictSchema):
    category: CategoryNameValue
    case_count: StrictInt = Field(ge=1)
    pass_rate_left: StrictFloat = Field(ge=0.0, le=1.0)
    pass_rate_right: StrictFloat = Field(ge=0.0, le=1.0)
    mean_source_recall_left: StrictFloat = Field(ge=0.0, le=1.0)
    mean_source_recall_right: StrictFloat = Field(ge=0.0, le=1.0)
    wins: StrictInt = Field(ge=0)
    ties: StrictInt = Field(ge=0)
    losses: StrictInt = Field(ge=0)
    verdict: Literal["improved", "regressed", "tied"]


class CategoryComparisonSchema(StrictSchema):
    study_id: str
    trial_id: str
    baseline_trial_id: str
    items: list[CategoryComparisonRowSchema]


class OverviewActionSchema(StrictSchema):
    action: ActionValue
    available: bool
    reason: str


class OverviewRoundSchema(StrictSchema):
    round_no: StrictInt = Field(ge=1)
    total: StrictInt = Field(ge=0)
    completed: StrictInt = Field(ge=0)
    failed: StrictInt = Field(ge=0)
    cancelled: StrictInt = Field(ge=0)
    best_score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)


class OverviewTrialRowSchema(StrictSchema):
    id: str
    ordinal: StrictInt = Field(ge=1)
    round_no: StrictInt = Field(ge=1)
    status: TrialStatusValue
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    draft_policy_id: str | None = None
    recommendation_rank: StrictInt | None = Field(default=None, ge=1)
    failure_code: str | None = None
    eligible: bool
    metrics: TrialMetricsSchema | None = None


class OverviewFrontierItemSchema(StrictSchema):
    trial_id: str
    ordinal: StrictInt = Field(ge=1)


class OverviewRecommendationSchema(StrictSchema):
    rank: StrictInt = Field(ge=1)
    trial_id: str
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    converted: bool
    draft_policy_id: str | None = None
    rationale_first_line: str


class StudyOverviewSchema(StrictSchema):
    study: StudyDetailSchema
    rounds: list[OverviewRoundSchema]
    trials: list[OverviewTrialRowSchema]
    frontier: list[OverviewFrontierItemSchema]
    recommendation: list[OverviewRecommendationSchema]
    actions: list[OverviewActionSchema]


class StudyTemplateSchema(StrictSchema):
    key: StudyObjectiveValue
    description: str
    objective: StudyObjectiveValue
    max_candidates: StrictInt = Field(ge=1)
    max_evaluations: StrictInt = Field(ge=1)
    seed: StrictInt = Field(ge=0)
    search_space: SearchSpaceSchema
    weights: ScoreWeightsSchema


class StudyTemplateCatalogSchema(StrictSchema):
    items: list[StudyTemplateSchema]


class TemplateOverridesSchema(StrictSchema):
    seed: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)
    max_candidates: StrictInt | None = Field(default=None, ge=1, le=4)
    max_evaluations: StrictInt | None = Field(default=None, ge=1, le=8)
    warm_start_study_id: StrictStr | None = Field(
        default=None, min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$"
    )


class CreateStudyFromTemplateSchema(StrictSchema):
    schema_version: Literal[1] = 1
    request_id: StrictStr = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:@-]+$")
    label: StrictStr = Field(min_length=1, max_length=120)
    base_policy_id: StrictStr = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")
    template_key: StrictStr = Field(min_length=1, max_length=40)
    overrides: TemplateOverridesSchema = Field(default_factory=TemplateOverridesSchema)

    @field_validator("label")
    @classmethod
    def _label_is_safe(cls, value: str) -> str:
        return _reject_prompt_shell_code(value)


class StudyEventSchema(StrictSchema):
    id: str
    event_type: EventTypeValue
    round_no: StrictInt = Field(ge=1)
    payload: dict[str, StrictStr | StrictInt | StrictBool | list[StrictStr]]
    created_at: datetime


class StudyEventCatalogSchema(StrictSchema):
    study_id: str
    items: list[StudyEventSchema]


class ExportComparisonSchema(StrictSchema):
    schema_version: Literal[1] = 1
    trial_ids: list[StrictStr] = Field(min_length=2, max_length=3)
    include_categories: StrictBool = False


class ExportComparisonReceiptSchema(StrictSchema):
    study_id: str
    markdown: str
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    generated_trial_ids: list[str]


class CreateShareLinkSchema(StrictSchema):
    schema_version: Literal[1] = 1
    expires_in_days: StrictInt | None = Field(default=None, ge=1, le=30)


class ShareLinkReceiptSchema(StrictSchema):
    token: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    url_path: str
    expires_at: datetime


class ShareLinkCatalogSchema(StrictSchema):
    items: list[ShareLinkReceiptSchema]
