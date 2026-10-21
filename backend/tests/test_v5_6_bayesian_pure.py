from __future__ import annotations

import pytest

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy.config import policy_fingerprint
from app.modules.agent_policy_optimizer.bayesian_generation import (
    Observation,
    generate_bayesian_candidates,
)
from app.modules.agent_policy_optimizer.category_analysis import (
    CaseResult,
    summarize_categories,
    compare_categories,
)
from app.modules.agent_policy_optimizer.contracts import (
    OptimizerInputError,
    SearchSpace,
    SearchSpaceBound,
)
from app.modules.agent_policy_optimizer.candidate_generation import generate_candidates
from app.modules.agent_control.report import EXPECTED_CATEGORY_COUNTS


SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(2, 24),
    comparative_top_k=SearchSpaceBound(4, 30),
    temporal_top_k=SearchSpaceBound(2, 24),
    minimum_score_millis=SearchSpaceBound(0, 400),
    max_hits_per_source=SearchSpaceBound(1, 8),
    neighbor_before=SearchSpaceBound(0, 3),
    neighbor_after=SearchSpaceBound(0, 3),
)
BASE = RetrievalPolicyConfig()
FIELDS = (
    "factual_top_k",
    "comparative_top_k",
    "temporal_top_k",
    "minimum_score_millis",
    "max_hits_per_source",
    "neighbor_before",
    "neighbor_after",
)


def _observation(config: RetrievalPolicyConfig, score: float) -> Observation:
    return Observation(config=config, score=score)


def test_first_round_matches_random_generation() -> None:
    bayesian = generate_bayesian_candidates(
        BASE, SPACE, round_no=1, observations=(), max_candidates=8, seed=99
    )
    random_candidates = generate_candidates(BASE, SPACE, max_candidates=8, seed=99)
    assert [item.config.as_dict() for item in bayesian] == [
        item.config.as_dict() for item in random_candidates
    ]
    assert [item.ordinal for item in bayesian] == [item.ordinal for item in random_candidates]


def test_bayesian_generation_is_deterministic_with_observations() -> None:
    observations = (
        _observation(RetrievalPolicyConfig(factual_top_k=6), 420),
        _observation(RetrievalPolicyConfig(factual_top_k=10), 610),
        _observation(RetrievalPolicyConfig(factual_top_k=18), 830),
        _observation(RetrievalPolicyConfig(factual_top_k=22), 900),
    )
    first = generate_bayesian_candidates(
        BASE, SPACE, round_no=2, observations=observations, max_candidates=6, seed=5
    )
    second = generate_bayesian_candidates(
        BASE, SPACE, round_no=2, observations=observations, max_candidates=6, seed=5
    )
    assert [item.config.as_dict() for item in first] == [item.config.as_dict() for item in second]
    assert len(first) == 6
    assert len({item.fingerprint for item in first}) == 6


def test_later_round_excludes_base_and_every_observed_fingerprint() -> None:
    observations = (
        _observation(BASE, 500),
        _observation(RetrievalPolicyConfig(factual_top_k=10), 610),
        _observation(RetrievalPolicyConfig(factual_top_k=18), 830),
    )

    candidates = generate_bayesian_candidates(
        BASE, SPACE, round_no=2, observations=observations, max_candidates=4, seed=5
    )

    forbidden = {policy_fingerprint(item.config) for item in observations}
    assert len(candidates) == 4
    assert all(item.fingerprint not in forbidden for item in candidates)
    assert all(item.is_baseline is False for item in candidates)


def test_observations_pull_candidates_toward_improving_direction() -> None:
    # Score strongly increases with factual_top_k: most round-2 candidates should
    # sit above the search-space midpoint for that dimension.
    observations = tuple(
        _observation(RetrievalPolicyConfig(factual_top_k=value), float(value) * 40.0)
        for value in (2, 6, 10, 14, 18, 22)
    )
    candidates = generate_bayesian_candidates(
        BASE, SPACE, round_no=2, observations=observations, max_candidates=12, seed=13
    )
    mid = (2 + 24) / 2
    above = sum(1 for item in candidates[1:] if item.config.factual_top_k >= mid)
    assert above >= (len(candidates) - 1) * 2 / 3


def test_exploration_tightens_in_later_rounds() -> None:
    observations = tuple(
        _observation(RetrievalPolicyConfig(factual_top_k=value), float(value) * 40.0)
        for value in (2, 8, 16, 22)
    )
    def spread(items) -> float:
        values = [item.config.factual_top_k for item in items[1:]]
        return float(max(values) - min(values))

    late_wins = 0
    for seed in (21, 22, 23, 24, 25):
        early = generate_bayesian_candidates(
            BASE, SPACE, round_no=2, observations=observations, max_candidates=12, seed=seed
        )
        late = generate_bayesian_candidates(
            BASE, SPACE, round_no=6, observations=observations, max_candidates=12, seed=seed
        )
        if spread(late) <= spread(early):
            late_wins += 1
    assert late_wins >= 3  # majority of seeds shows tightened exploration


def test_bayesian_rejects_invalid_inputs() -> None:
    with pytest.raises(OptimizerInputError):
        generate_bayesian_candidates(
            BASE, SPACE, round_no=1, observations=(), max_candidates=0, seed=1
        )
    with pytest.raises(OptimizerInputError):
        generate_bayesian_candidates(
            BASE, SPACE, round_no=0, observations=(), max_candidates=4, seed=1
        )
    with pytest.raises(OptimizerInputError):
        generate_bayesian_candidates(
            BASE,
            SPACE,
            round_no=2,
            observations=(_observation(RetrievalPolicyConfig(), float("nan")),),
            max_candidates=4,
            seed=1,
        )
    # Warm-start observations may come from a wider parent search space, while
    # every newly generated candidate must still fit the current Study space.
    narrow_space = SearchSpace(
        factual_top_k=SearchSpaceBound(2, 8), comparative_top_k=SearchSpaceBound(4, 14),
        temporal_top_k=SearchSpaceBound(2, 12), minimum_score_millis=SearchSpaceBound(0, 400),
        max_hits_per_source=SearchSpaceBound(1, 8), neighbor_before=SearchSpaceBound(0, 3),
        neighbor_after=SearchSpaceBound(0, 3),
    )
    candidates = generate_bayesian_candidates(
        BASE,
        narrow_space,
        round_no=2,
        observations=(_observation(RetrievalPolicyConfig(factual_top_k=16), 500.0),),
        max_candidates=4,
        seed=1,
    )
    assert all(2 <= item.config.factual_top_k <= 8 for item in candidates)


def test_module_has_no_infrastructure_imports() -> None:
    from pathlib import Path

    for name in ("bayesian_generation.py", "category_analysis.py"):
        text = (Path(__file__).resolve().parents[1] / "app" / "modules" / "agent_policy_optimizer" / name).read_text(
            encoding="utf-8"
        ).lower()
        for needle in ("sqlalchemy", "redis", "fastapi", "httpx", "activate_policy"):
            assert needle not in text, f"{name} must not reference {needle}"


# --- category analysis ------------------------------------------------------


def _case(case_id: str, category: str, passed: bool, recall: float = 1.0, latency: float = 100.0) -> CaseResult:
    return CaseResult(case_id=case_id, category=category, passed=passed, source_recall=recall, latency_ms=latency)


def _all_cases(pass_flags: dict[str, bool], recall: float = 1.0) -> list[CaseResult]:
    cases: list[CaseResult] = []
    for category, count in EXPECTED_CATEGORY_COUNTS.items():
        for ordinal in range(1, count + 1):
            cases.append(
                _case(
                    f"{category}-{ordinal:02d}",
                    category,
                    pass_flags.get(category, True),
                    recall if pass_flags.get(category, True) else 0.0,
                )
            )
    return cases


def test_compare_categories_covers_all_categories_and_directions() -> None:
    baseline = _all_cases({})
    candidate = _all_cases({"multi_hop": False, "cross_modal": True}, recall=0.9)
    # Make cross_modal strictly better in the candidate: baseline fails one there.
    baseline = [item if item.category != "cross_modal" or item.case_id != "cross_modal-01" else _case(item.case_id, item.category, False) for item in baseline]
    rows = compare_categories(baseline, candidate)
    assert {row.category for row in rows} == set(EXPECTED_CATEGORY_COUNTS)
    by_category = {row.category: row for row in rows}
    assert by_category["multi_hop"].verdict == "regressed"
    assert by_category["cross_modal"].verdict == "improved"
    assert by_category["single_hop"].verdict == "tied"
    assert by_category["multi_hop"].pass_rate_right == 0.0
    assert by_category["multi_hop"].pass_rate_left == 1.0


def test_compare_categories_rejects_incomplete_case_sets() -> None:
    baseline = _all_cases({})
    candidate = _all_cases({})[:-1]  # drop one case
    with pytest.raises(OptimizerInputError):
        compare_categories(baseline, candidate)
    with pytest.raises(OptimizerInputError):
        compare_categories([baseline[0]] * 60, candidate)


def test_summarize_categories_renders_improved_and_regressed_lists() -> None:
    baseline = _all_cases({})
    candidate = _all_cases({"multi_hop": False, "cross_modal": True})
    baseline = [item if item.category != "cross_modal" or item.case_id != "cross_modal-01" else _case(item.case_id, item.category, False) for item in baseline]
    summary = summarize_categories(baseline, candidate)
    assert "multi_hop" in summary["regressed"]
    assert "cross_modal" in summary["improved"]
    assert isinstance(summary["sentence"], str) and summary["sentence"]
