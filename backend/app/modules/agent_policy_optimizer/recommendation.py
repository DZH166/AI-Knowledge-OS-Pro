"""Recommendation ranking and rationale for V5.4A optimization studies.

Pure module: database, queue, and web framework imports are forbidden here. This module produces recommendation candidates only; it contains no
policy activation path of any kind.
"""

from __future__ import annotations

from app.modules.agent_policy_optimizer.contracts import (
    OPTIMIZER_ALGORITHM_VERSION,
    OptimizerInputError,
    RecommendationBundle,
    RecommendationCandidate,
    RecommendationInput,
    ScoreWeights,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.objectives import METRIC_DIRECTIONS, TrialMetrics
from app.modules.agent_policy_optimizer.pareto import dominates

_DISPLAY_ALIASES: dict[str, str] = {
    "latency_ms": "latency",
    "retrieval_window": "retrieval window",
}

_THRESHOLD = 1e-9


def _compare(baseline: TrialMetrics, candidate: TrialMetrics) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    improved: list[str] = []
    unchanged: list[str] = []
    regressed: list[str] = []
    for name in METRIC_DIRECTIONS:
        direction = METRIC_DIRECTIONS[name]
        delta = float(getattr(candidate, name)) - float(getattr(baseline, name))
        better = delta > _THRESHOLD if direction == "higher" else delta < -_THRESHOLD
        worse = delta < -_THRESHOLD if direction == "higher" else delta > _THRESHOLD
        if better:
            improved.append(name)
        elif worse:
            regressed.append(name)
        else:
            unchanged.append(name)
    return tuple(improved), tuple(unchanged), tuple(regressed)


def _rationale(
    *,
    objective: StudyObjective,
    weights: ScoreWeights,
    improved: tuple[str, ...],
    unchanged: tuple[str, ...],
    regressed: tuple[str, ...],
    dominates_baseline: bool,
    score_millis: int,
    baseline_score_millis: int,
) -> str:
    def render(names: tuple[str, ...]) -> str:
        return ", ".join(_DISPLAY_ALIASES.get(name, name) for name in names) if names else "none"

    objective_note = {
        StudyObjective.QUALITY_FIRST: "quality-first weighting",
        StudyObjective.BALANCED: "balanced weighting",
        StudyObjective.COST_FIRST: "cost-first weighting",
    }[objective]
    dominance = (
        "It dominates the baseline on every metric."
        if dominates_baseline
        else "It does not fully dominate the baseline, so review the regressions before adoption."
    )
    return (
        f"Recommended under {objective_note} (quality {weights.quality_weight_permille} permille, "
        f"cost {weights.cost_weight_permille} permille). Compared with the baseline trial: "
        f"improved [{render(improved)}], unchanged [{render(unchanged)}], "
        f"regressed [{render(regressed)}]. Weighted score {score_millis} millis versus "
        f"baseline {baseline_score_millis} millis. {dominance} "
        "This is a review candidate only; activation still requires the human-gated "
        "policy activation flow with its own passed fixed evaluation."
    )


def build_recommendations(
    *,
    study_id: str,
    objective: StudyObjective,
    weights: ScoreWeights,
    baseline: RecommendationInput,
    candidates: tuple[RecommendationInput, ...] | list[RecommendationInput],
    frontier_trial_ids: frozenset[str] | set[str],
) -> RecommendationBundle:
    """Rank frontier-eligible candidates against the baseline trial.

    Every candidate must already be in the computed Pareto frontier and must
    carry an evaluation fingerprint identical to its policy fingerprint.
    Output is deterministic: ties fall back to the candidate ordinal.
    """

    if baseline.evaluation_fingerprint != baseline.policy_fingerprint:
        raise OptimizerInputError(
            "OPTIMIZER_RECOMMENDATION_FINGERPRINT_MISMATCH",
            "The baseline trial evaluation fingerprint does not match its policy fingerprint.",
        )
    ordered: list[RecommendationInput] = sorted(
        candidates,
        key=lambda item: (-item.score_millis, item.ordinal, item.trial_id),
    )
    recommendations: list[RecommendationCandidate] = []
    for candidate in ordered:
        if candidate.trial_id not in frontier_trial_ids:
            raise OptimizerInputError(
                "OPTIMIZER_RECOMMENDATION_NOT_FRONTIER",
                f"Trial {candidate.trial_id} is not on the Pareto frontier.",
            )
        if candidate.evaluation_fingerprint != candidate.policy_fingerprint:
            raise OptimizerInputError(
                "OPTIMIZER_RECOMMENDATION_FINGERPRINT_MISMATCH",
                f"Trial {candidate.trial_id} evaluation fingerprint does not match its policy fingerprint.",
            )
        if candidate.study_id != study_id:
            raise OptimizerInputError(
                "OPTIMIZER_RECOMMENDATION_STUDY_MISMATCH",
                f"Trial {candidate.trial_id} belongs to a different study.",
            )
        improved, unchanged, regressed = _compare(baseline.metrics, candidate.metrics)
        dominates_baseline = dominates(candidate.metrics, baseline.metrics)
        rationale = _rationale(
            objective=objective,
            weights=weights,
            improved=improved,
            unchanged=unchanged,
            regressed=regressed,
            dominates_baseline=dominates_baseline,
            score_millis=candidate.score_millis,
            baseline_score_millis=baseline.score_millis,
        )
        recommendations.append(
            RecommendationCandidate(
                rank=len(recommendations) + 1,
                study_id=study_id,
                trial_id=candidate.trial_id,
                policy_fingerprint=candidate.policy_fingerprint,
                policy_snapshot_json=candidate.policy_snapshot_json,
                evaluation_id=candidate.evaluation_id,
                evaluation_fingerprint=candidate.evaluation_fingerprint,
                evaluation_report_sha256=candidate.evaluation_report_sha256,
                score_millis=candidate.score_millis,
                dominates_baseline=dominates_baseline,
                improved_metrics=improved,
                unchanged_metrics=unchanged,
                regressed_metrics=regressed,
                rationale=rationale,
                algorithm_version=OPTIMIZER_ALGORITHM_VERSION,
            )
        )
    return RecommendationBundle(
        study_id=study_id,
        objective=objective,
        weights=weights,
        algorithm_version=OPTIMIZER_ALGORITHM_VERSION,
        candidates=tuple(recommendations),
    )


__all__ = ["build_recommendations"]
