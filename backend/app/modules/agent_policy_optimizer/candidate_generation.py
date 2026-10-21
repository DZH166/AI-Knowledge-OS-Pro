"""Deterministic candidate policy generation for V5.4A optimization studies.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

import random
from typing import Any

from app.modules.agent_policy.config import RetrievalPolicyConfig, policy_fingerprint
from app.modules.agent_policy_optimizer.contracts import (
    CandidatePolicy,
    OptimizerInputError,
    SearchSpace,
)

TUNABLE_FIELDS: tuple[str, ...] = (
    "factual_top_k",
    "comparative_top_k",
    "temporal_top_k",
    "minimum_score_millis",
    "max_hits_per_source",
    "neighbor_before",
    "neighbor_after",
)

_HARD_BOUNDS: dict[str, tuple[int, int]] = {
    "factual_top_k": (1, 50),
    "comparative_top_k": (1, 50),
    "temporal_top_k": (1, 50),
    "minimum_score_millis": (0, 1_000),
    "max_hits_per_source": (1, 20),
    "neighbor_before": (0, 3),
    "neighbor_after": (0, 3),
}

_MAX_CANDIDATES = 64


def validate_search_space(space: SearchSpace) -> None:
    for name in TUNABLE_FIELDS:
        bound = getattr(space, name)
        hard_minimum, hard_maximum = _HARD_BOUNDS[name]
        if type(bound.minimum) is not int or type(bound.maximum) is not int:
            raise OptimizerInputError("OPTIMIZER_SEARCH_SPACE_INVALID", f"{name} bounds must be integers.")
        if bound.minimum > bound.maximum:
            raise OptimizerInputError("OPTIMIZER_SEARCH_SPACE_INVALID", f"{name} bound minimum exceeds maximum.")
        if bound.minimum < hard_minimum or bound.maximum > hard_maximum:
            raise OptimizerInputError(
                "OPTIMIZER_SEARCH_SPACE_INVALID",
                f"{name} bounds must stay within the safe retrieval policy range {hard_minimum}..{hard_maximum}.",
            )


def generate_candidates(
    base_config: RetrievalPolicyConfig,
    space: SearchSpace,
    *,
    max_candidates: int,
    seed: int,
) -> tuple[CandidatePolicy, ...]:
    """Return a deterministic, duplicate-free candidate sequence.

    Ordinal 1 is always the untouched baseline configuration as the anchor for
    comparison; every later ordinal is sampled from the seeded RNG. Identical
    configurations are discarded and resampled, so all fingerprints are unique.
    """

    validate_search_space(space)
    if type(max_candidates) is not int or not 1 <= max_candidates <= _MAX_CANDIDATES:
        raise OptimizerInputError("OPTIMIZER_BUDGET_INVALID", "max_candidates must be between 1 and 64.")
    if type(seed) is not int or isinstance(seed, bool) or not 0 <= seed <= 2_147_483_647:
        raise OptimizerInputError("OPTIMIZER_SEED_INVALID", "seed must be an integer between 0 and 2^31-1.")

    rng = random.Random(seed)
    seen: dict[str, CandidatePolicy] = {}
    candidates: list[CandidatePolicy] = [
        CandidatePolicy(ordinal=1, config=base_config, fingerprint=policy_fingerprint(base_config), is_baseline=True)
    ]
    seen[candidates[0].fingerprint] = candidates[0]
    attempts = 0
    while len(candidates) < max_candidates:
        attempts += 1
        if attempts > _MAX_CANDIDATES * 200:
            raise OptimizerInputError(
                "OPTIMIZER_SEARCH_SPACE_EXHAUSTED",
                "Search space cannot yield enough distinct candidates.",
            )
        config = base_config
        for name in TUNABLE_FIELDS:
            bound = getattr(space, name)
            choices = tuple(range(bound.minimum, bound.maximum + 1))
            value = choices[0] if len(choices) == 1 else rng.choice(choices)
            if value == getattr(config, name) and len(choices) > 1:
                remaining = [item for item in choices if item != getattr(config, name)]
                value = rng.choice(tuple(remaining))
            config = _replace(config, name, value)
        fingerprint = policy_fingerprint(config)
        if fingerprint in seen:
            continue
        candidate = CandidatePolicy(
            ordinal=len(candidates) + 1,
            config=config,
            fingerprint=fingerprint,
            is_baseline=False,
        )
        seen[fingerprint] = candidate
        candidates.append(candidate)
    return tuple(candidates)


def _replace(config: RetrievalPolicyConfig, name: str, value: int) -> RetrievalPolicyConfig:
    values: dict[str, Any] = config.as_dict()
    values[name] = value
    return RetrievalPolicyConfig(**values)


__all__ = ["TUNABLE_FIELDS", "generate_candidates", "validate_search_space"]
