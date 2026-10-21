from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, field_validator, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    objective: Literal["quality_first", "balanced", "cost_first"]
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



class StudyIdempotencyNoteSchema(StrictSchema):
    replayed: bool = False


class BudgetUsageSchema(StrictSchema):
    created_trials: StrictInt = Field(ge=0)
    started_evaluations: StrictInt = Field(ge=0)


class StudySummarySchema(StrictSchema):
    id: str
    label: str
    objective: str
    status: str
    base_policy_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    budget_usage: dict[str, StrictInt]
    created_at: str


class StudyCatalogSchema(StrictSchema):
    items: list[StudySummarySchema]


class StudyDetailSchema(StrictSchema):
    id: str
    request_id: str
    label: str
    objective: str
    status: str
    base_policy_id: str
    base_policy_fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    search_space: dict[str, object]
    weights: dict[str, object]
    budget: dict[str, object]
    budget_usage: dict[str, StrictInt]
    seed: StrictInt
    algorithm_version: str
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    cancelled_at: str | None
    round_no: StrictInt = Field(default=1, ge=1)
    warm_start_study_id: str | None = None
    next_round_request_id: str | None = None


class TrialSummarySchema(StrictSchema):
    id: str
    study_id: str
    ordinal: StrictInt = Field(ge=1)
    status: str
    config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    is_baseline: bool
    evaluation_id: str | None
    draft_policy_id: str | None = None
    category_stats: dict[str, object] | None = None
    round_no: StrictInt = Field(default=1, ge=1)
    metrics: dict[str, object] | None
    normalized_metrics: dict[str, object] | None
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    recommendation_rank: StrictInt | None = Field(default=None, ge=1)
    failure_code: str | None
    attempt: StrictInt = Field(ge=0)
    external_provider_calls: StrictInt | None = Field(default=None, ge=0)
    created_at: str | None
    finished_at: str | None


class TrialCatalogSchema(StrictSchema):
    items: list[TrialSummarySchema]


class ParetoItemSchema(StrictSchema):
    trial_id: str
    ordinal: StrictInt = Field(ge=1)
    score_millis: StrictInt | None = Field(default=None, ge=0, le=1000)
    eligible: bool
    config_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    metrics: dict[str, object] | None


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
    improved_metrics: list[str]
    unchanged_metrics: list[str]
    regressed_metrics: list[str]
    rationale: str
    algorithm_version: str


class RecommendationBundleSchema(StrictSchema):
    study_id: str
    algorithm_version: str
    candidates: list[RecommendationCandidateSchema]


class StudyMutationReceiptSchema(StrictSchema):
    study_id: str
    status: str
    created: StrictInt | None = Field(default=None, ge=0)
    cancelled: bool | None = None
    replayed: bool = False


class TrialReceiptSchema(TrialSummarySchema):
    pass


class RecoverReceiptSchema(StrictSchema):
    recovered_trials: StrictInt = Field(ge=0)


class CancelReceiptSchema(StrictSchema):
    study_id: str
    status: str
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
    status: str
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
    status: str


class FailStudySchema(StrictSchema):
    schema_version: Literal[1] = 1
    reason: StrictStr | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def _reason_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else _reject_prompt_shell_code(value)


class FailReceiptSchema(StrictSchema):
    study_id: str
    status: str
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
    category: str
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


