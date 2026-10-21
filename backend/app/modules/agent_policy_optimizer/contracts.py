from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal, NotRequired, TypedDict


OPTIMIZER_ALGORITHM_VERSION = "v5_6_bayesian_1"

TrialStatus = Literal["pending", "running", "completing", "completed", "failed", "cancelled"]
StudyStatus = Literal["pending", "running", "completed", "cancelled", "failed"]


class StudyObjective(StrEnum):
    QUALITY_FIRST = "quality_first"
    BALANCED = "balanced"
    COST_FIRST = "cost_first"


class OptimizerInputError(ValueError):
    """Raised for optimizer inputs that violate the frozen V5.4A contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SearchSpaceBound:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if type(self.minimum) is not int or type(self.maximum) is not int:
            raise OptimizerInputError("OPTIMIZER_SEARCH_SPACE_INVALID", "Bounds must be integers.")
        if self.minimum > self.maximum:
            raise OptimizerInputError("OPTIMIZER_SEARCH_SPACE_INVALID", "Bound minimum exceeds maximum.")


@dataclass(frozen=True, slots=True)
class SearchSpace:
    factual_top_k: SearchSpaceBound
    comparative_top_k: SearchSpaceBound
    temporal_top_k: SearchSpaceBound
    minimum_score_millis: SearchSpaceBound
    max_hits_per_source: SearchSpaceBound
    neighbor_before: SearchSpaceBound
    neighbor_after: SearchSpaceBound


@dataclass(frozen=True, slots=True)
class StudyBudget:
    max_candidates: int
    max_evaluations: int

    def __post_init__(self) -> None:
        if type(self.max_candidates) is not int or type(self.max_evaluations) is not int:
            raise OptimizerInputError("OPTIMIZER_BUDGET_INVALID", "Budget values must be integers.")
        if not 1 <= self.max_candidates <= 64:
            raise OptimizerInputError("OPTIMIZER_BUDGET_INVALID", "max_candidates must be between 1 and 64.")
        if not 1 <= self.max_evaluations <= 128:
            raise OptimizerInputError("OPTIMIZER_BUDGET_INVALID", "max_evaluations must be between 1 and 128.")


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    created_trials: int = 0
    started_evaluations: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"created_trials": self.created_trials, "started_evaluations": self.started_evaluations}


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    quality_weight_permille: int
    cost_weight_permille: int

    def __post_init__(self) -> None:
        if type(self.quality_weight_permille) is not int or type(self.cost_weight_permille) is not int:
            raise OptimizerInputError("OPTIMIZER_WEIGHTS_INVALID", "Weights must be integers.")
        if self.quality_weight_permille < 0 or self.cost_weight_permille < 0:
            raise OptimizerInputError("OPTIMIZER_WEIGHTS_INVALID", "Weights cannot be negative.")
        if self.quality_weight_permille + self.cost_weight_permille <= 0:
            raise OptimizerInputError("OPTIMIZER_WEIGHTS_INVALID", "At least one weight must be positive.")


@dataclass(frozen=True, slots=True)
class StudyCommand:
    request_id: str
    label: str
    base_policy_id: str
    objective: StudyObjective
    max_candidates: int
    max_evaluations: int
    search_space: SearchSpace
    weights: ScoreWeights
    seed: int
    deadline_at: datetime | None = None
    warm_start_study_id: str | None = None


@dataclass(frozen=True, slots=True)
class CandidatePolicy:
    ordinal: int
    config: object
    fingerprint: str
    is_baseline: bool


@dataclass(frozen=True, slots=True)
class TrialMetrics:
    case_pass_rate: float
    mean_source_recall: float
    citation_completeness: float
    latency_ms: float
    retrieval_window: int
    external_provider_calls: int

    def __post_init__(self) -> None:
        for name in ("case_pass_rate", "mean_source_recall", "citation_completeness", "latency_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", f"{name} must be a number.")
            number = float(value)
            if number != number or number in (float("inf"), float("-inf")):
                raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", f"{name} must be finite.")
        for name in ("case_pass_rate", "mean_source_recall", "citation_completeness"):
            if not 0.0 <= float(getattr(self, name)) <= 1.0:
                raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", f"{name} must be within 0 and 1.")
        if float(self.latency_ms) < 0:
            raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", "latency_ms cannot be negative.")
        if type(self.retrieval_window) is not int or self.retrieval_window < 1:
            raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", "retrieval_window must be a positive integer.")
        if type(self.external_provider_calls) is not int:
            raise OptimizerInputError(
                "OPTIMIZER_METRIC_INVALID",
                "external_provider_calls must be an integer.",
            )
        if self.external_provider_calls != 0:
            raise OptimizerInputError(
                "OPTIMIZER_METRIC_INVALID",
                "Deterministic optimizer metrics must report zero external provider calls.",
            )

    def as_dict(self) -> dict[str, float | int]:
        return {
            "case_pass_rate": self.case_pass_rate,
            "mean_source_recall": self.mean_source_recall,
            "citation_completeness": self.citation_completeness,
            "latency_ms": self.latency_ms,
            "retrieval_window": self.retrieval_window,
            "external_provider_calls": self.external_provider_calls,
        }


@dataclass(frozen=True, slots=True)
class QualifiedTrial:
    trial_id: str
    study_id: str
    ordinal: int
    status: str
    evaluation_status: str | None
    hard_gates: dict[str, bool] | None
    external_provider_calls: int | None
    failure_case_count: int | None
    policy_fingerprint: str
    evaluation_fingerprint: str | None
    metrics: TrialMetrics | None
    score_millis: int | None
    eligible: bool


@dataclass(frozen=True, slots=True)
class RecommendationInput:
    study_id: str
    trial_id: str
    ordinal: int
    policy_fingerprint: str
    policy_snapshot_json: str
    evaluation_id: str
    evaluation_fingerprint: str
    evaluation_report_sha256: str
    metrics: TrialMetrics
    score_millis: int


@dataclass(frozen=True, slots=True)
class RecommendationCandidate:
    rank: int
    study_id: str
    trial_id: str
    policy_fingerprint: str
    policy_snapshot_json: str
    evaluation_id: str
    evaluation_fingerprint: str
    evaluation_report_sha256: str
    score_millis: int
    dominates_baseline: bool
    improved_metrics: tuple[str, ...]
    unchanged_metrics: tuple[str, ...]
    regressed_metrics: tuple[str, ...]
    rationale: str
    algorithm_version: str


@dataclass(frozen=True, slots=True)
class RecommendationBundle:
    study_id: str
    objective: StudyObjective
    weights: ScoreWeights
    algorithm_version: str
    candidates: tuple[RecommendationCandidate, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StartStudy:
    study_id: str
    worker_id: str


@dataclass(frozen=True, slots=True)
class ExecuteTrial:
    trial_id: str
    worker_id: str


@dataclass(frozen=True, slots=True)
class CancelStudy:
    study_id: str


@dataclass(frozen=True, slots=True)
class RecoverOptimizations:
    now: datetime
    study_id: str | None = None


@dataclass(frozen=True, slots=True)
class ListOptimizationStudies:
    status: str | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class GetOptimizationStudy:
    study_id: str


@dataclass(frozen=True, slots=True)
class ListOptimizationTrials:
    study_id: str
    status: str | None = None
    limit: int = 200


@dataclass(frozen=True, slots=True)
class GetOptimizationTrial:
    trial_id: str


@dataclass(frozen=True, slots=True)
class GetOptimizationPareto:
    study_id: str


@dataclass(frozen=True, slots=True)
class GetOptimizationRecommendation:
    study_id: str
@dataclass(frozen=True, slots=True)
class ConvertRecommendation:
    study_id: str
    trial_id: str
    request_id: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class RetryTrial:
    trial_id: str


@dataclass(frozen=True, slots=True)
class FailStudy:
    study_id: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DiffTrialAgainstActive:
    study_id: str
    trial_id: str


OptimizerReadQuery = (
    ListOptimizationStudies
    | GetOptimizationStudy
    | ListOptimizationTrials
    | GetOptimizationTrial
    | GetOptimizationPareto
    | GetOptimizationRecommendation
    | DiffTrialAgainstActive
)


@dataclass(frozen=True, slots=True)
class NextRound:
    study_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class ExportComparison:
    study_id: str
    trial_ids: tuple[str, ...]
    include_categories: bool = False


class StudyMutationReceipt(TypedDict):
    study_id: str
    status: StudyStatus
    created: NotRequired[int]
    cancelled: NotRequired[bool]
    replayed: NotRequired[bool]


class SearchSpaceBoundView(TypedDict):
    minimum: int
    maximum: int


class SearchSpaceView(TypedDict):
    factual_top_k: SearchSpaceBoundView
    comparative_top_k: SearchSpaceBoundView
    temporal_top_k: SearchSpaceBoundView
    minimum_score_millis: SearchSpaceBoundView
    max_hits_per_source: SearchSpaceBoundView
    neighbor_before: SearchSpaceBoundView
    neighbor_after: SearchSpaceBoundView


class ScoreWeightsView(TypedDict):
    quality_weight_permille: int
    cost_weight_permille: int


class StudyBudgetView(TypedDict):
    max_candidates: int
    max_evaluations: int
    deadline_at: NotRequired[str]


class BudgetUsageView(TypedDict):
    created_trials: int
    started_evaluations: int


class StudyTemplateView(TypedDict):
    key: StudyObjective
    description: str
    objective: StudyObjective
    max_candidates: int
    max_evaluations: int
    seed: int
    search_space: SearchSpaceView
    weights: ScoreWeightsView


class StudyTemplateCatalogView(TypedDict):
    items: list[StudyTemplateView]


class TrialMetricsView(TypedDict):
    case_pass_rate: float
    mean_source_recall: float
    citation_completeness: float
    latency_ms: float
    retrieval_window: int
    external_provider_calls: int


class CaseFactView(TypedDict):
    case_id: str
    category: str
    passed: bool
    source_recall: float
    latency_ms: float


class CategoryAggregateView(TypedDict):
    passed: int
    total: int
    mean_source_recall: float


class CategoryStatsView(TypedDict):
    schema_version: int
    categories: dict[str, CategoryAggregateView]
    cases: list[CaseFactView]


class TrialView(TypedDict):
    id: str
    study_id: str
    ordinal: int
    status: TrialStatus
    config_sha256: str
    is_baseline: bool
    evaluation_id: str | None
    draft_policy_id: str | None
    category_stats: CategoryStatsView | None
    round_no: int
    metrics: TrialMetricsView | None
    normalized_metrics: dict[str, float] | None
    score_millis: int | None
    recommendation_rank: int | None
    failure_code: str | None
    attempt: int
    external_provider_calls: int | None
    created_at: str
    finished_at: str | None


class StudyCatalogView(TypedDict):
    items: list["StudySummaryView"]


class StudySummaryView(TypedDict):
    id: str
    label: str
    objective: StudyObjective
    status: StudyStatus
    base_policy_fingerprint: str
    budget_usage: BudgetUsageView
    created_at: str


class TrialCatalogView(TypedDict):
    items: list[TrialView]


class ParetoView(TypedDict):
    study_id: str
    items: list["ParetoItemView"]


class ParetoItemView(TypedDict):
    trial_id: str
    ordinal: int
    score_millis: int | None
    eligible: bool
    config_sha256: str
    metrics: TrialMetricsView | None


class RecommendationView(TypedDict):
    study_id: str
    algorithm_version: str
    candidates: list["RecommendationCandidateView"]


class RecommendationCandidateView(TypedDict):
    rank: int
    trial_id: str
    policy_fingerprint: str
    policy_snapshot_json: str
    evaluation_id: str
    evaluation_fingerprint: str
    evaluation_report_sha256: str
    score_millis: int
    dominates_baseline: bool
    improved_metrics: list[str]
    unchanged_metrics: list[str]
    regressed_metrics: list[str]
    rationale: str
    algorithm_version: str


class ConvertDraftReceipt(TypedDict):
    command_id: str
    policy_id: str
    policy_version: int
    status: str
    policy_config_sha256: str
    replayed: bool


class RetryReceipt(TypedDict):
    trial_id: str
    status: Literal["pending"]


class FailReceipt(TypedDict):
    study_id: str
    status: StudyStatus
    cancelled: bool


class NextRoundReceipt(TypedDict):
    study_id: str
    round_no: int
    created: int
    replayed: bool


class StudyDetailView(TypedDict):
    id: str
    request_id: str
    label: str
    objective: StudyObjective
    status: StudyStatus
    base_policy_id: str
    base_policy_fingerprint: str
    search_space: SearchSpaceView
    weights: ScoreWeightsView
    budget: StudyBudgetView
    budget_usage: BudgetUsageView
    seed: int
    algorithm_version: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    cancelled_at: str | None
    round_no: int
    warm_start_study_id: str | None
    next_round_request_id: str | None


class DiffView(TypedDict):
    study_id: str
    trial_id: str
    trial_config_sha256: str
    active_policy_id: str
    active_policy_version: int
    active_config_sha256: str
    compatible: bool
    incompatibility_reasons: list[str]
    changes: list["DiffChangeView"]
    trial_summary: "DiffTrialSummaryView"


class DiffChangeView(TypedDict):
    field: str
    left: int
    right: int


class DiffTrialSummaryView(TypedDict):
    eligible: bool
    score_millis: int | None
    case_pass_rate: float | None


class CategoryComparisonRowView(TypedDict):
    category: str
    case_count: int
    pass_rate_left: float
    pass_rate_right: float
    mean_source_recall_left: float
    mean_source_recall_right: float
    wins: int
    ties: int
    losses: int
    verdict: Literal["improved", "regressed", "tied"]


class CategoryComparisonView(TypedDict):
    study_id: str
    trial_id: str
    baseline_trial_id: str
    items: list[CategoryComparisonRowView]


class OverviewRoundView(TypedDict):
    round_no: int
    total: int
    completed: int
    failed: int
    cancelled: int
    best_score_millis: int | None


class OverviewTrialView(TypedDict):
    id: str
    ordinal: int
    round_no: int
    status: TrialStatus
    score_millis: int | None
    draft_policy_id: str | None
    recommendation_rank: int | None
    failure_code: str | None
    eligible: bool
    metrics: TrialMetricsView | None


class OverviewFrontierView(TypedDict):
    trial_id: str
    ordinal: int


class OverviewRecommendationView(TypedDict):
    rank: int
    trial_id: str
    score_millis: int | None
    converted: bool
    draft_policy_id: str | None
    rationale_first_line: str


class OverviewActionView(TypedDict):
    action: Literal[
        "start", "next-round", "cancel", "fail", "retry", "convert-draft", "recover"
    ]
    available: bool
    reason: str


class StudyOverviewView(TypedDict):
    study: StudyDetailView
    rounds: list[OverviewRoundView]
    trials: list[OverviewTrialView]
    frontier: list[OverviewFrontierView]
    recommendation: list[OverviewRecommendationView]
    actions: list[OverviewActionView]


class StudyTemplateReceipt(StudyMutationReceipt):
    template_key: str


EventFact = str | int | bool | list[str]


class StudyEventView(TypedDict):
    id: str
    event_type: Literal[
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
    round_no: int
    payload: dict[str, EventFact]
    created_at: str


class StudyEventCatalogView(TypedDict):
    study_id: str
    items: list[StudyEventView]


class ExportComparisonReceipt(TypedDict):
    study_id: str
    markdown: str
    sha256: str
    generated_trial_ids: list[str]


OptimizerReadResult = (
    StudyCatalogView
    | StudyDetailView
    | TrialCatalogView
    | TrialView
    | ParetoView
    | RecommendationView
    | DiffView
)
