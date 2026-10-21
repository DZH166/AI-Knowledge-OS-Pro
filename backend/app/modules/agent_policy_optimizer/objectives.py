"""Metric catalog, normalization, and weighted scoring for V5.4A optimization.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

from typing import Iterable, Literal

from app.modules.agent_policy_optimizer.contracts import (
    OPTIMIZER_ALGORITHM_VERSION,
    OptimizerInputError,
    ScoreWeights,
    TrialMetrics,
)

MetricDirection = Literal["higher", "lower"]

METRIC_DIRECTIONS: dict[str, MetricDirection] = {
    "case_pass_rate": "higher",
    "mean_source_recall": "higher",
    "citation_completeness": "higher",
    "latency_ms": "lower",
    "retrieval_window": "lower",
    "external_provider_calls": "lower",
}

_SCORE_SCALE_MILLIS = 1_000


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", f"{label} must be a number.")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", f"{label} must be finite.")
    return number


def _validated_metrics(metrics: TrialMetrics) -> TrialMetrics:
    # TrialMetrics.__post_init__ is the single validation point; constructing a
    # new instance re-runs it and rejects booleans, NaN/Infinity, and ranges.
    return TrialMetrics(**metrics.as_dict())


def normalize_metrics(metrics: Iterable[TrialMetrics]) -> list[dict[str, float]]:
    """Min-max normalize every metric to [0, 1] honoring its direction.

    A degenerate dimension (all values equal) maps to 0.5 so the metric
    contributes neither advantage nor penalty instead of collapsing to zero.
    """

    rows = [_validated_metrics(item) for item in metrics]
    if not rows:
        return []
    normalized: list[dict[str, float]] = [dict() for _ in rows]
    for name, direction in METRIC_DIRECTIONS.items():
        values = [float(getattr(row, name)) for row in rows]
        span = max(values) - min(values)
        for index, value in enumerate(values):
            if span == 0:
                normalized[index][name] = 0.5
            elif direction == "higher":
                normalized[index][name] = (value - min(values)) / span
            else:
                normalized[index][name] = (max(values) - value) / span
    return normalized


def weighted_score_millis(normalized: dict[str, float], weights: ScoreWeights) -> int:
    """Blend normalized metrics into one explainable integer score in millis.

    Quality metrics (case_pass_rate, mean_source_recall, citation_completeness)
    share the quality weight; cost metrics (latency_ms, retrieval_window) share
    the cost weight. Provider calls stay at 0 for every eligible trial, so they
    normalize to the degenerate 0.5 and add no advantage.
    """

    if type(weights.quality_weight_permille) is not int or type(weights.cost_weight_permille) is not int:
        raise OptimizerInputError("OPTIMIZER_WEIGHTS_INVALID", "Weights must be integers.")
    unknown = set(normalized) - set(METRIC_DIRECTIONS)
    if unknown:
        raise OptimizerInputError("OPTIMIZER_METRIC_INVALID", f"Unknown normalized metrics: {sorted(unknown)}.")
    quality_names = ("case_pass_rate", "mean_source_recall", "citation_completeness")
    cost_names = ("latency_ms", "retrieval_window")
    quality_total = sum(float(normalized.get(name, 0.5)) for name in quality_names) / len(quality_names)
    cost_total = sum(float(normalized.get(name, 0.5)) for name in cost_names) / len(cost_names)
    denominator = weights.quality_weight_permille + weights.cost_weight_permille
    blended = (quality_total * weights.quality_weight_permille + cost_total * weights.cost_weight_permille) / denominator
    return max(0, min(_SCORE_SCALE_MILLIS, round(blended * _SCORE_SCALE_MILLIS)))


__all__ = [
    "METRIC_DIRECTIONS",
    "OPTIMIZER_ALGORITHM_VERSION",
    "normalize_metrics",
    "weighted_score_millis",
]
