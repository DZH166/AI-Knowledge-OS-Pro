from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy_optimizer.contracts import (
    OPTIMIZER_ALGORITHM_VERSION,
    OptimizerInputError,
    ScoreWeights,
    SearchSpace,
    SearchSpaceBound,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.candidate_generation import (
    TUNABLE_FIELDS,
    generate_candidates,
)
from app.modules.agent_policy_optimizer.objectives import (
    TrialMetrics,
    normalize_metrics,
    weighted_score_millis,
)
from app.modules.agent_policy_optimizer.pareto import (
    dominates,
    pareto_frontier,
    qualify_trial,
)
from app.modules.agent_policy_optimizer.recommendation import (
    RecommendationInput,
    build_recommendations,
)


FULL_SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(2, 24),
    comparative_top_k=SearchSpaceBound(4, 30),
    temporal_top_k=SearchSpaceBound(2, 24),
    minimum_score_millis=SearchSpaceBound(0, 400),
    max_hits_per_source=SearchSpaceBound(1, 8),
    neighbor_before=SearchSpaceBound(0, 3),
    neighbor_after=SearchSpaceBound(0, 3),
)
BASE = RetrievalPolicyConfig()
HARD_GATES = {
    "60_case_matrix": True,
    "active_revision_precision": True,
    "all_cases_pass": True,
    "citation_complete": True,
    "immutable_identity_complete": True,
    "locator_validity": True,
    "multi_hop_lift_at_least_10pp": True,
    "quick_has_no_plan": True,
    "recovery_matrix_pass": True,
    "unauthorized_action_rate_zero": True,
}


def _metrics(**overrides: float) -> TrialMetrics:
    values: dict[str, float] = {
        "case_pass_rate": 1.0,
        "mean_source_recall": 0.9,
        "citation_completeness": 1.0,
        "latency_ms": 200.0,
        "retrieval_window": 34,
        "external_provider_calls": 0,
    }
    values.update(overrides)
    return TrialMetrics(**values)


def _outcome(
    trial_id: str,
    ordinal: int,
    *,
    metrics: TrialMetrics | None = None,
    eligible: bool = True,
    score_millis: int = 500,
    fingerprint: str = "a" * 64,
):
    return qualify_trial(
        trial_id=trial_id,
        study_id="study-1",
        ordinal=ordinal,
        status="completed" if eligible else "failed",
        evaluation_status="passed" if eligible else "failed",
        hard_gates=HARD_GATES if eligible else {**HARD_GATES, "all_cases_pass": False},
        external_provider_calls=0,
        failure_case_count=0,
        policy_fingerprint=fingerprint,
        evaluation_fingerprint=fingerprint if eligible else "b" * 64,
        metrics=metrics if metrics is not None else _metrics(),
        score_millis=score_millis,
    )


def test_candidate_generation_is_deterministic_unique_and_baseline_anchored() -> None:
    first = generate_candidates(BASE, FULL_SPACE, max_candidates=12, seed=20260831)
    second = generate_candidates(BASE, FULL_SPACE, max_candidates=12, seed=20260831)
    assert first == second
    assert len(first) == 12
    assert [item.ordinal for item in first] == list(range(1, 13))
    assert first[0].is_baseline is True
    assert first[0].config == BASE
    fingerprints = {item.fingerprint for item in first}
    assert len(fingerprints) == 12
    assert all(len(item.fingerprint) == 64 for item in first)
    assert all(len({getattr(item.config, field) for item in first}) >= 1 for field in TUNABLE_FIELDS)


def test_candidate_generation_honors_search_space_and_rejects_out_of_range() -> None:
    candidates = generate_candidates(BASE, FULL_SPACE, max_candidates=20, seed=7)
    for candidate in candidates[1:]:
        assert 2 <= candidate.config.factual_top_k <= 24
        assert 4 <= candidate.config.comparative_top_k <= 30
        assert 2 <= candidate.config.temporal_top_k <= 24
        assert 0 <= candidate.config.minimum_score_millis <= 400
        assert 1 <= candidate.config.max_hits_per_source <= 8
        assert 0 <= candidate.config.neighbor_before <= 3
        assert 0 <= candidate.config.neighbor_after <= 3

    with pytest.raises(OptimizerInputError) as global_bound:
        generate_candidates(
            BASE,
            SearchSpace(factual_top_k=SearchSpaceBound(2, 80), comparative_top_k=SearchSpaceBound(4, 30),
                        temporal_top_k=SearchSpaceBound(2, 24), minimum_score_millis=SearchSpaceBound(0, 400),
                        max_hits_per_source=SearchSpaceBound(1, 8), neighbor_before=SearchSpaceBound(0, 3),
                        neighbor_after=SearchSpaceBound(0, 3)),
            max_candidates=4,
            seed=1,
        )

    assert global_bound.value.code == "OPTIMIZER_SEARCH_SPACE_INVALID"

    with pytest.raises(OptimizerInputError) as inverted:
        generate_candidates(
            BASE,
            SearchSpace(factual_top_k=SearchSpaceBound(20, 2), comparative_top_k=SearchSpaceBound(4, 30),
                        temporal_top_k=SearchSpaceBound(2, 24), minimum_score_millis=SearchSpaceBound(0, 400),
                        max_hits_per_source=SearchSpaceBound(1, 8), neighbor_before=SearchSpaceBound(0, 3),
                        neighbor_after=SearchSpaceBound(0, 3)),
            max_candidates=4,
            seed=1,
        )
    assert inverted.value.code == "OPTIMIZER_SEARCH_SPACE_INVALID"


def test_metrics_reject_booleans_nan_infinity_and_out_of_range() -> None:
    with pytest.raises(OptimizerInputError):
        _metrics(case_pass_rate=True)  # type: ignore[arg-type]
    with pytest.raises(OptimizerInputError):
        _metrics(case_pass_rate=float("nan"))
    with pytest.raises(OptimizerInputError):
        _metrics(latency_ms=float("inf"))
    with pytest.raises(OptimizerInputError):
        _metrics(case_pass_rate=1.5)
    with pytest.raises(OptimizerInputError):
        _metrics(latency_ms=-1.0)
    with pytest.raises(OptimizerInputError):
        _metrics(retrieval_window=True)  # type: ignore[arg-type]
    with pytest.raises(OptimizerInputError):
        _metrics(external_provider_calls=1)


def test_normalization_is_bounded_directional_and_degenerates_to_half() -> None:
    lower = _metrics(case_pass_rate=0.8, latency_ms=100.0, retrieval_window=20)
    higher = _metrics(case_pass_rate=1.0, latency_ms=300.0, retrieval_window=40)
    normalized = normalize_metrics([lower, higher])
    assert normalized[0]["case_pass_rate"] == 0.0
    assert normalized[1]["case_pass_rate"] == pytest.approx(1.0)
    assert normalized[0]["latency_ms"] == pytest.approx(1.0)
    assert normalized[1]["latency_ms"] == pytest.approx(0.0)
    assert normalized[0]["citation_completeness"] == 0.5

    same = normalize_metrics([_metrics(), _metrics()])
    assert all(value == 0.5 for value in same[0].values())
    assert all(value == 0.5 for value in same[1].values())

    weights = ScoreWeights(quality_weight_permille=700, cost_weight_permille=300)
    score = weighted_score_millis(normalized[1], weights)
    assert 0 <= score <= 1000
    assert isinstance(score, int)
    with pytest.raises(OptimizerInputError):
        ScoreWeights(quality_weight_permille=True, cost_weight_permille=300)  # type: ignore[arg-type]
    with pytest.raises(OptimizerInputError):
        ScoreWeights(quality_weight_permille=-1, cost_weight_permille=300)
    with pytest.raises(OptimizerInputError):
        ScoreWeights(quality_weight_permille=0, cost_weight_permille=0)


def test_dominates_respects_metric_directions() -> None:
    better_quality = _metrics(case_pass_rate=1.0)
    baseline = _metrics(case_pass_rate=0.9)
    assert dominates(better_quality, baseline) is True
    assert dominates(baseline, better_quality) is False

    faster = _metrics(latency_ms=100.0)
    slower = _metrics(latency_ms=400.0)
    assert dominates(faster, slower) is True
    assert dominates(slower, faster) is False

    trade_off = _metrics(case_pass_rate=1.0, latency_ms=900.0)
    assert dominates(trade_off, baseline) is False
    assert dominates(baseline, trade_off) is False
    assert dominates(_metrics(), _metrics()) is False


def test_pareto_frontier_excludes_ineligible_and_orders_stably() -> None:
    anchor = _outcome("trial-anchor", 1, metrics=_metrics(latency_ms=300.0, mean_source_recall=0.95), score_millis=600)
    fast = _outcome("trial-fast", 2, metrics=_metrics(latency_ms=80.0), score_millis=900)
    dominated = _outcome("trial-dominated", 3, metrics=_metrics(latency_ms=500.0), score_millis=400)
    broken = _outcome("trial-broken", 4, metrics=_metrics(latency_ms=10.0), score_millis=990, eligible=False)

    frontier = pareto_frontier([dominated, broken, anchor, fast])
    assert [item.trial_id for item in frontier] == ["trial-fast", "trial-anchor"]
    assert [item.ordinal for item in frontier] == [2, 1]
    again = pareto_frontier([fast, anchor, broken, dominated])
    assert [item.trial_id for item in again] == ["trial-fast", "trial-anchor"]

    shadowed_trial = _outcome("trial-shadow", 7, metrics=_metrics(latency_ms=90.0, mean_source_recall=0.9), score_millis=890)
    shadowed = pareto_frontier([fast, shadowed_trial])
    assert [item.trial_id for item in shadowed] == ["trial-fast"]

    tie_left = _outcome("trial-tie-a", 5, metrics=_metrics(), score_millis=700)
    tie_right = _outcome("trial-tie-b", 6, metrics=_metrics(), score_millis=700)
    tied = pareto_frontier([tie_right, tie_left])
    assert [item.trial_id for item in tied] == ["trial-tie-a", "trial-tie-b"]


def test_qualify_trial_rejects_provider_calls_fingerprint_mismatch_and_gates() -> None:
    assert qualify_trial(
        trial_id="t1", study_id="s1", ordinal=1, status="completed", evaluation_status="passed",
        hard_gates=HARD_GATES, external_provider_calls=2, failure_case_count=0,
        policy_fingerprint="a" * 64, evaluation_fingerprint="a" * 64, metrics=_metrics(), score_millis=500,
    ).eligible is False
    assert qualify_trial(
        trial_id="t2", study_id="s1", ordinal=2, status="completed", evaluation_status="passed",
        hard_gates=HARD_GATES, external_provider_calls=0, failure_case_count=0,
        policy_fingerprint="a" * 64, evaluation_fingerprint="b" * 64, metrics=_metrics(), score_millis=500,
    ).eligible is False
    assert qualify_trial(
        trial_id="t3", study_id="s1", ordinal=3, status="completed", evaluation_status="passed",
        hard_gates={**HARD_GATES, "locator_validity": False}, external_provider_calls=0,
        failure_case_count=0, policy_fingerprint="a" * 64, evaluation_fingerprint="a" * 64,
        metrics=_metrics(), score_millis=500,
    ).eligible is False
    assert qualify_trial(
        trial_id="t4", study_id="s1", ordinal=4, status="completed", evaluation_status="passed",
        hard_gates=HARD_GATES, external_provider_calls=0, failure_case_count=3,
        policy_fingerprint="a" * 64, evaluation_fingerprint="a" * 64, metrics=_metrics(), score_millis=500,
    ).eligible is False
    assert qualify_trial(
        trial_id="t5", study_id="s1", ordinal=5, status="running", evaluation_status=None,
        hard_gates=None, external_provider_calls=None, failure_case_count=None,
        policy_fingerprint="a" * 64, evaluation_fingerprint=None, metrics=None, score_millis=None,
    ).eligible is False


def test_recommendation_only_accepts_eligible_frontier_trials_and_explains_itself() -> None:
    baseline_fingerprint = "c" * 64
    anchor = RecommendationInput(
        study_id="study-1", trial_id="trial-anchor", ordinal=1,
        policy_fingerprint=baseline_fingerprint, policy_snapshot_json='{"schema_version":1}',
        evaluation_id="eval-anchor", evaluation_fingerprint=baseline_fingerprint,
        evaluation_report_sha256="d" * 64, metrics=_metrics(), score_millis=600,
    )
    winner = RecommendationInput(
        study_id="study-1", trial_id="trial-fast", ordinal=2,
        policy_fingerprint="e" * 64, policy_snapshot_json='{"schema_version":1}',
        evaluation_id="eval-fast", evaluation_fingerprint="e" * 64,
        evaluation_report_sha256="f" * 64, metrics=_metrics(latency_ms=90.0, mean_source_recall=0.95),
        score_millis=920,
    )
    frontier = pareto_frontier([
        qualify_trial(
            trial_id=winner.trial_id, study_id="study-1", ordinal=2, status="completed",
            evaluation_status="passed", hard_gates=HARD_GATES, external_provider_calls=0,
            failure_case_count=0, policy_fingerprint=winner.policy_fingerprint,
            evaluation_fingerprint=winner.evaluation_fingerprint, metrics=winner.metrics,
            score_millis=920,
        ),
        qualify_trial(
            trial_id=anchor.trial_id, study_id="study-1", ordinal=1, status="completed",
            evaluation_status="passed", hard_gates=HARD_GATES, external_provider_calls=0,
            failure_case_count=0, policy_fingerprint=anchor.policy_fingerprint,
            evaluation_fingerprint=anchor.evaluation_fingerprint, metrics=anchor.metrics,
            score_millis=600,
        ),
    ])

    bundle = build_recommendations(
        study_id="study-1",
        objective=StudyObjective.BALANCED,
        weights=ScoreWeights(quality_weight_permille=700, cost_weight_permille=300),
        baseline=anchor,
        candidates=[winner],
        frontier_trial_ids=frozenset(item.trial_id for item in frontier),
    )
    assert len(bundle.candidates) == 1
    recommendation = bundle.candidates[0]
    assert recommendation.rank == 1
    assert recommendation.trial_id == "trial-fast"
    assert recommendation.dominates_baseline is True
    assert recommendation.improved_metrics == ("mean_source_recall", "latency_ms")
    assert recommendation.regressed_metrics == ()
    assert "citation_completeness" in recommendation.unchanged_metrics
    assert OPTIMIZER_ALGORITHM_VERSION == "v5_6_bayesian_1"
    for reference in (
        recommendation.study_id,
        recommendation.trial_id,
        recommendation.policy_fingerprint,
        recommendation.evaluation_id,
        recommendation.evaluation_report_sha256,
    ):
        assert reference
    assert "case_pass_rate" not in recommendation.improved_metrics

    with pytest.raises(OptimizerInputError) as not_frontier:
        build_recommendations(
            study_id="study-1", objective=StudyObjective.BALANCED,
            weights=ScoreWeights(700, 300), baseline=anchor, candidates=[winner],
            frontier_trial_ids=frozenset({"trial-anchor"}),
        )
    assert not_frontier.value.code == "OPTIMIZER_RECOMMENDATION_NOT_FRONTIER"

    mismatched = dataclasses.replace(winner, evaluation_fingerprint="9" * 64)
    with pytest.raises(OptimizerInputError) as fingerprint:
        build_recommendations(
            study_id="study-1", objective=StudyObjective.BALANCED,
            weights=ScoreWeights(700, 300), baseline=anchor, candidates=[mismatched],
            frontier_trial_ids=frozenset({"trial-fast", "trial-anchor"}),
        )
    assert fingerprint.value.code == "OPTIMIZER_RECOMMENDATION_FINGERPRINT_MISMATCH"


def test_recommendations_rank_by_score_then_stable_identity() -> None:
    anchor = RecommendationInput(
        study_id="study-1",
        trial_id="trial-anchor",
        ordinal=1,
        policy_fingerprint="a" * 64,
        policy_snapshot_json='{"schema_version":1}',
        evaluation_id="eval-anchor",
        evaluation_fingerprint="a" * 64,
        evaluation_report_sha256="b" * 64,
        metrics=_metrics(),
        score_millis=500,
    )
    low = dataclasses.replace(
        anchor,
        trial_id="trial-low",
        ordinal=2,
        policy_fingerprint="c" * 64,
        evaluation_id="eval-low",
        evaluation_fingerprint="c" * 64,
        score_millis=100,
    )
    high = dataclasses.replace(
        anchor,
        trial_id="trial-high",
        ordinal=3,
        policy_fingerprint="d" * 64,
        evaluation_id="eval-high",
        evaluation_fingerprint="d" * 64,
        score_millis=900,
    )
    bundle = build_recommendations(
        study_id="study-1",
        objective=StudyObjective.BALANCED,
        weights=ScoreWeights(700, 300),
        baseline=anchor,
        candidates=[low, high],
        frontier_trial_ids={"trial-low", "trial-high"},
    )
    assert [(item.trial_id, item.rank) for item in bundle.candidates] == [
        ("trial-high", 1),
        ("trial-low", 2),
    ]


def test_optimizer_modules_never_import_infrastructure_or_activation() -> None:
    module_dir = Path(__file__).resolve().parents[1] / "app" / "modules" / "agent_policy_optimizer"
    pure_modules = ("contracts.py", "objectives.py", "candidate_generation.py", "pareto.py", "recommendation.py")
    banned = ("sqlalchemy", "redis", "rq.", "fastapi", "httpx", "activate_policy", "requests", "app.models")
    for name in pure_modules:
        source = module_dir / name
        text = source.read_text(encoding="utf-8").lower()
        for needle in banned:
            assert needle not in text, f"{source.name} must not reference {needle}"
    # The recommendation module must never reference the activation flow.
    recommendation_text = (module_dir / "recommendation.py").read_text(encoding="utf-8").lower()
    assert "activate" not in recommendation_text.replace("activation still requires the human-gated", "")
