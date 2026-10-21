"""Observation-guided candidate generation for V5.6 optimization studies.

Pure module: database, queue, and web framework imports are forbidden here.

The "Bayesian" model is deliberately simple and deterministic: a per-dimension
linear surrogate over normalized dimension values predicts the score, and the
generator samples candidates along the predicted improving direction with an
exploration rate that decays over rounds (floored at 0.2 so diversity never
collapses). Every random draw comes from `random.Random(seed)`; no global RNG
state and no clock are used, so identical inputs yield identical outputs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.modules.agent_policy.config import RetrievalPolicyConfig, policy_fingerprint
from app.modules.agent_policy_optimizer.candidate_generation import (
    TUNABLE_FIELDS,
    validate_search_space,
)
from app.modules.agent_policy_optimizer.contracts import (
    CandidatePolicy,
    OptimizerInputError,
    SearchSpace,
)

_MAX_CANDIDATES = 64
_MIN_EXPLORATION = 0.2
_DECAY_PER_ROUND = 0.15
_GENERATION_RANDOM = GENERATION_RANDOM = "random.Random(seed) # deterministic draws only"


@dataclass(frozen=True, slots=True)
class Observation:
    config: RetrievalPolicyConfig
    score: float

    def __post_init__(self) -> None:
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise OptimizerInputError("OPTIMIZER_OBSERVATION_INVALID", "Observation score must be a number.")
        value = float(self.score)
        if value != value or value in (float("inf"), float("-inf")):
            raise OptimizerInputError("OPTIMIZER_OBSERVATION_INVALID", "Observation score must be finite.")
        if value < 0:
            raise OptimizerInputError("OPTIMIZER_OBSERVATION_INVALID", "Observation score cannot be negative.")


def _in_space(config: RetrievalPolicyConfig, space: SearchSpace) -> bool:
    for name in TUNABLE_FIELDS:
        bound = getattr(space, name)
        value = getattr(config, name)
        if not bound.minimum <= value <= bound.maximum:
            return False
    return True


def _validate_observations(observations: tuple[Observation, ...], space: SearchSpace) -> None:
    for item in observations:
        if not isinstance(item.config, RetrievalPolicyConfig):
            raise OptimizerInputError("OPTIMIZER_OBSERVATION_INVALID", "Observation config type is invalid.")
        if not _in_space(item.config, space):
            raise OptimizerInputError(
                "OPTIMIZER_OBSERVATION_INVALID",
                "Observation config falls outside the study search space.",
            )


def _normalized(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.5
    return (value - minimum) / (maximum - minimum)


def _dimension_slope(observations: tuple[Observation, ...], field: str, space: SearchSpace) -> float:
    """Least-squares slope of score against the normalized dimension value."""

    bound = getattr(space, field)
    xs: list[float] = []
    ys: list[float] = []
    for item in observations:
        xs.append(_normalized(float(getattr(item.config, field)), float(bound.minimum), float(bound.maximum)))
        ys.append(float(item.score))
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    variance = sum((x - mean_x) ** 2 for x in xs)
    if variance <= 1e-12:
        return 0.0
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    return covariance / variance


def _exploration_rate(round_no: int) -> float:
    # Round 1 is fully random (delegates to the V5.4A generator). The first
    # guided round starts at 0.6 exploration and decays 0.15/round to 0.2 so
    # diversity never collapses.
    rate = 0.6 - _DECAY_PER_ROUND * max(0, round_no - 2)
    return max(_MIN_EXPLORATION, rate)


def _sample_guided(
    rng: random.Random,
    base_config: RetrievalPolicyConfig,
    space: SearchSpace,
    observations: tuple[Observation, ...],
    round_no: int,
) -> RetrievalPolicyConfig:
    """Sample one candidate along predicted improving directions with exploration."""

    slopes = {field: _dimension_slope(observations, field, space) for field in TUNABLE_FIELDS}
    exploration = _exploration_rate(round_no)
    config = base_config
    for field in TUNABLE_FIELDS:
        bound = getattr(space, field)
        choices = tuple(range(bound.minimum, bound.maximum + 1))
        if len(choices) <= 1:
            continue
        slope = slopes[field]
        current = getattr(config, field)
        if rng.random() < exploration:
            value = rng.choice(choices)
            if value == current:
                remaining = [item for item in choices if item != current]
                value = rng.choice(remaining)
        else:
            # Follow the predicted improving direction: pick a value shifted
            # from the current best observation in the slope's sign, magnitude
            # proportional to |slope| but bounded within the space.
            best_observation = max(observations, key=lambda item: item.score)
            anchor = getattr(best_observation.config, field)
            span = bound.maximum - bound.minimum
            step = int(round(min(1.0, abs(slope) / 50.0) * span * 0.25)) + 1
            direction = 1 if slope > 0 else -1
            value = anchor + direction * step
            if value == anchor:
                value = anchor + direction
            value = max(bound.minimum, min(bound.maximum, value))
            if value == current and len(choices) > 1:
                remaining = [item for item in choices if item != current]
                value = rng.choice(remaining)
        config = _replace(config, field, value)
    return config


def _replace(config: RetrievalPolicyConfig, name: str, value: int) -> RetrievalPolicyConfig:
    values = config.as_dict()
    values[name] = value
    return RetrievalPolicyConfig(**values)


def generate_bayesian_candidates(
    base_config: RetrievalPolicyConfig,
    space: SearchSpace,
    *,
    round_no: int,
    observations: tuple[Observation, ...],
    max_candidates: int,
    seed: int,
) -> tuple[CandidatePolicy, ...]:
    """Return a deterministic candidate sequence for one optimization round.

    Round 1 (no observations) is exactly the V5.4A random generation. Later
    rounds use the linear surrogate over completed trials to bias sampling
    toward predicted improvements, with decaying exploration.
    """

    validate_search_space(space)
    if type(max_candidates) is not int or not 1 <= max_candidates <= _MAX_CANDIDATES:
        raise OptimizerInputError("OPTIMIZER_BUDGET_INVALID", "max_candidates must be between 1 and 64.")
    if type(seed) is not int or isinstance(seed, bool) or not 0 <= seed <= 2_147_483_647:
        raise OptimizerInputError("OPTIMIZER_SEED_INVALID", "seed must be an integer between 0 and 2^31-1.")
    if type(round_no) is not int or isinstance(round_no, bool) or round_no < 1:
        raise OptimizerInputError("OPTIMIZER_ROUND_INVALID", "round_no must be a positive integer.")
    if not isinstance(observations, tuple):
        raise OptimizerInputError("OPTIMIZER_OBSERVATION_INVALID", "observations must be a tuple.")
    _validate_observations(observations, space)

    if round_no == 1 or not observations:
        from app.modules.agent_policy_optimizer.candidate_generation import generate_candidates

        return generate_candidates(base_config, space, max_candidates=max_candidates, seed=seed)

    rng = random.Random(seed)
    seen: dict[str, CandidatePolicy] = {}
    candidates: list[CandidatePolicy] = []
    attempts = 0
    observed_scores = {policy_fingerprint(item.config) for item in observations}
    while len(candidates) < max_candidates:
        attempts += 1
        if attempts > _MAX_CANDIDATES * 200:
            raise OptimizerInputError(
                "OPTIMIZER_SEARCH_SPACE_EXHAUSTED",
                "Search space cannot yield enough distinct candidates.",
            )
        config = _sample_guided(rng, base_config, space, observations, round_no)
        fingerprint = policy_fingerprint(config)
        if fingerprint in seen or fingerprint in observed_scores:
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


__all__ = ["Observation", "generate_bayesian_candidates"]
