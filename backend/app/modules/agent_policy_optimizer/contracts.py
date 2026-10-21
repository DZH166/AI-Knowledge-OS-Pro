from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal


OPTIMIZER_ALGORITHM_VERSION = "v5_4a_1"

TrialStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
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
