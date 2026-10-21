"""Deterministic candidate policy generation for V5.4A optimization studies.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

import random
from itertools import product
from typing import Any, Collection

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
_ENUMERATION_LIMIT = 4_096


def enumerate_bounded_configs(
    base_config: RetrievalPolicyConfig, space: SearchSpace
) -> tuple[RetrievalPolicyConfig, ...] | None:
    """Enumerate a finite small space for an exact fallback after guided sampling."""
    ranges = [range(getattr(space, name).minimum, getattr(space, name).maximum + 1) for name in TUNABLE_FIELDS]
    size = 1
    for values in ranges:
        size *= len(values)
        if size > _ENUMERATION_LIMIT:
            return None
    base_values = base_config.as_dict()
    return tuple(
        RetrievalPolicyConfig(**{**base_values, **dict(zip(TUNABLE_FIELDS, values, strict=True))})
        for values in product(*ranges)
    )


def bounded_attempt_limit(small_space: tuple[RetrievalPolicyConfig, ...] | None) -> int:
    if small_space is None:
        return _MAX_CANDIDATES * 200
    return min(_MAX_CANDIDATES * 200, max(256, len(small_space) * 4))


def complete_from_small_space(
    candidates: list[CandidatePolicy],
    small_space: tuple[RetrievalPolicyConfig, ...] | None,
    *,
    excluded_fingerprints: Collection[str],
    max_candidates: int,
    rng: random.Random,
) -> tuple[CandidatePolicy, ...] | None:
    """Exactly fill a small legal space after bounded stochastic attempts."""
    if small_space is None:
        return None
    excluded = {item.fingerprint for item in candidates} | set(excluded_fingerprints)
    remaining = [config for config in small_space if policy_fingerprint(config) not in excluded]
    needed = max_candidates - len(candidates)
    if len(remaining) < needed:
        return None
    rng.shuffle(remaining)
    return tuple(candidates) + tuple(
        CandidatePolicy(
            ordinal=len(candidates) + index,
            config=config,
            fingerprint=policy_fingerprint(config),
            is_baseline=False,
        )
        for index, config in enumerate(remaining[:needed], start=1)
    )


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
    small_space = enumerate_bounded_configs(base_config, space)
    attempt_limit = bounded_attempt_limit(small_space)
    seen: dict[str, CandidatePolicy] = {}
    candidates: list[CandidatePolicy] = [
        CandidatePolicy(ordinal=1, config=base_config, fingerprint=policy_fingerprint(base_config), is_baseline=True)
    ]
    seen[candidates[0].fingerprint] = candidates[0]
    attempts = 0
    while len(candidates) < max_candidates:
        attempts += 1
        if attempts > attempt_limit:
            completed = complete_from_small_space(
                candidates, small_space,
                excluded_fingerprints=(), max_candidates=max_candidates, rng=rng,
            )
            if completed is not None:
                return completed
            raise OptimizerInputError(
                "OPTIMIZER_SEARCH_SPACE_EXHAUSTED",
                "Search space cannot yield enough distinct candidates.",
            )
        config = base_config
        for name in TUNABLE_FIELDS:
            bound = getattr(space, name)
            choices = tuple(range(bound.minimum, bound.maximum + 1))
            value = choices[0] if len(choices) == 1 else rng.choice(choices)
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


__all__ = [
    "TUNABLE_FIELDS",
    "bounded_attempt_limit",
    "complete_from_small_space",
    "enumerate_bounded_configs",
    "generate_candidates",
    "validate_search_space",
]
