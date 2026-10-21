"""Pareto dominance and frontier computation for V5.4A optimization studies.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from app.modules.agent_policy_optimizer.contracts import QualifiedTrial
from app.modules.agent_policy_optimizer.objectives import METRIC_DIRECTIONS, TrialMetrics


def dominates(left: TrialMetrics, right: TrialMetrics) -> bool:
    """Return True when left is at least as good on every metric and strictly
    better on at least one, honoring each metric's direction."""

    at_least_one_better = False
    for name, direction in METRIC_DIRECTIONS.items():
        left_value = float(getattr(left, name))
        right_value = float(getattr(right, name))
        if direction == "higher":
            if left_value < right_value:
                return False
            if left_value > right_value:
                at_least_one_better = True
        else:
            if left_value > right_value:
                return False
            if left_value < right_value:
                at_least_one_better = True
    return at_least_one_better


def qualify_trial(
    *,
    trial_id: str,
    study_id: str,
    ordinal: int,
    status: str,
    evaluation_status: str | None,
    hard_gates: Mapping[str, bool] | None,
    external_provider_calls: int | None,
    failure_case_count: int | None,
    policy_fingerprint: str,
    evaluation_fingerprint: str | None,
    metrics: TrialMetrics | None,
    score_millis: int | None,
) -> QualifiedTrial:
    """Bundle raw trial facts with the computed eligibility flag.

    Eligibility requires: trial completed, evaluation passed, zero external
    provider calls, every hard gate true, zero failure cases, matching policy
    and evaluation fingerprints, and complete metrics data. Ineligible trials
    never enter the frontier.
    """

    gates_complete = hard_gates is not None and len(hard_gates) > 0 and all(
        type(value) is bool and value for value in hard_gates.values()
    )
    eligible = (
        status == "completed"
        and evaluation_status == "passed"
        and gates_complete
        and external_provider_calls == 0
        and failure_case_count == 0
        and evaluation_fingerprint is not None
        and evaluation_fingerprint == policy_fingerprint
        and metrics is not None
        and score_millis is not None
    )
    return QualifiedTrial(
        trial_id=trial_id,
        study_id=study_id,
        ordinal=ordinal,
        status=status,
        evaluation_status=evaluation_status,
        hard_gates=dict(hard_gates) if hard_gates is not None else None,
        external_provider_calls=external_provider_calls,
        failure_case_count=failure_case_count,
        policy_fingerprint=policy_fingerprint,
        evaluation_fingerprint=evaluation_fingerprint,
        metrics=metrics,
        score_millis=score_millis,
        eligible=eligible,
    )


def pareto_frontier(trials: Iterable[QualifiedTrial]) -> tuple[QualifiedTrial, ...]:
    """Compute the Pareto frontier over eligible trials with a stable order.

    The result is sorted by (score_millis descending, ordinal ascending,
    trial_id ascending) so identical inputs always yield identical output.
    """

    eligible = [item for item in trials if item.eligible and item.metrics is not None]
    frontier: list[QualifiedTrial] = []
    for candidate in eligible:
        if candidate.metrics is None:
            continue
        dominated = False
        for other in eligible:
            if other.trial_id == candidate.trial_id or other.metrics is None:
                continue
            if dominates(other.metrics, candidate.metrics):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    frontier.sort(
        key=lambda item: (
            -(item.score_millis if item.score_millis is not None else 0),
            item.ordinal,
            item.trial_id,
        )
    )
    return tuple(frontier)


__all__ = ["dominates", "pareto_frontier", "qualify_trial"]
