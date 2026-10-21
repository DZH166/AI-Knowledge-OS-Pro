from __future__ import annotations

from itertools import product

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy_optimizer.bayesian_generation import Observation, generate_bayesian_candidates
from app.modules.agent_policy_optimizer.candidate_generation import generate_candidates
from app.modules.agent_policy_optimizer.contracts import SearchSpace, SearchSpaceBound


BASE = RetrievalPolicyConfig()
SMALL_SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(8, 9),
    comparative_top_k=SearchSpaceBound(14, 15),
    temporal_top_k=SearchSpaceBound(12, 12),
    minimum_score_millis=SearchSpaceBound(0, 0),
    max_hits_per_source=SearchSpaceBound(3, 3),
    neighbor_before=SearchSpaceBound(1, 1),
    neighbor_after=SearchSpaceBound(1, 1),
)


def test_random_generator_reaches_every_legal_small_space_candidate() -> None:
    generated = generate_candidates(BASE, SMALL_SPACE, max_candidates=4, seed=8)
    assert len(generated) == 4
    assert {(item.config.factual_top_k, item.config.comparative_top_k) for item in generated} == {
        (8, 14), (8, 15), (9, 14), (9, 15)
    }


def test_guided_generator_can_keep_one_baseline_dimension() -> None:
    observed = RetrievalPolicyConfig(factual_top_k=9, comparative_top_k=15)
    generated = generate_bayesian_candidates(
        BASE,
        SMALL_SPACE,
        round_no=2,
        observations=(Observation(config=BASE, score=0.4), Observation(config=observed, score=0.6)),
        max_candidates=2,
        seed=8,
    )
    assert {(item.config.factual_top_k, item.config.comparative_top_k) for item in generated} == {
        (8, 15), (9, 14)
    }


def test_guided_small_space_finds_rare_remaining_legal_candidate() -> None:
    bounds = {
        "factual_top_k": (7, 8),
        "comparative_top_k": (13, 14),
        "temporal_top_k": (11, 12),
        "minimum_score_millis": (0, 1),
        "max_hits_per_source": (2, 3),
        "neighbor_before": (0, 1),
        "neighbor_after": (0, 1),
    }
    space = SearchSpace(**{name: SearchSpaceBound(*range_) for name, range_ in bounds.items()})
    target = RetrievalPolicyConfig(
        factual_top_k=7, comparative_top_k=13, temporal_top_k=11,
        minimum_score_millis=1, max_hits_per_source=2, neighbor_before=0, neighbor_after=0,
    )
    names = tuple(bounds)
    observations = []
    for values in product(*(bounds[name] for name in names)):
        config = RetrievalPolicyConfig(**dict(zip(names, values, strict=True)))
        if config == target:
            continue
        score = float(sum(value == bounds[name][1] for name, value in zip(names, values, strict=True)))
        observations.append(Observation(config=config, score=score))

    generated = generate_bayesian_candidates(
        BASE, space, round_no=5, observations=tuple(observations), max_candidates=1, seed=8
    )

    assert generated[0].config == target
