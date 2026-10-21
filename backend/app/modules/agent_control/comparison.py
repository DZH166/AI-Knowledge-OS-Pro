from __future__ import annotations

from app.modules.agent_control.contracts import (
    ComparisonVerdict,
    EvaluationComparison,
    EvaluationDetail,
    GateChange,
    MetricDelta,
)
from app.modules.agent_control.metric_catalog import EVALUATION_METRICS


_EPSILON = 0.0001


def compare_evaluations(left: EvaluationDetail, right: EvaluationDetail) -> EvaluationComparison:
    reasons: list[str] = []
    if left.schema_version != right.schema_version:
        reasons.append("schema_version_mismatch")
    if not left.summary.dataset_sha256 or left.summary.dataset_sha256 != right.summary.dataset_sha256:
        reasons.append("dataset_digest_mismatch")
    if left.summary.status.value not in {"passed", "failed"} or right.summary.status.value not in {"passed", "failed"}:
        reasons.append("non_terminal_snapshot")
    for metric in EVALUATION_METRICS:
        if metric not in left.metrics or metric not in right.metrics:
            reasons.append(f"missing_metric:{metric}")
    if set(left.hard_gates) != set(right.hard_gates):
        reasons.append("hard_gate_set_mismatch")
    if reasons:
        return EvaluationComparison(
            left_id=left.summary.id,
            right_id=right.summary.id,
            compatible=False,
            incompatibility_reasons=tuple(reasons),
            verdict=ComparisonVerdict.INCOMPARABLE,
            policy_changed=left.summary.policy_fingerprint != right.summary.policy_fingerprint,
            left_policy_fingerprint=left.summary.policy_fingerprint,
            right_policy_fingerprint=right.summary.policy_fingerprint,
            metric_deltas=(),
            gate_changes=(),
            new_failure_case_ids=(),
            resolved_failure_case_ids=(),
        )

    deltas: list[MetricDelta] = []
    for metric, spec in EVALUATION_METRICS.items():
        direction = spec.direction
        left_value = float(left.metrics[metric])
        right_value = float(right.metrics[metric])
        delta = right_value - left_value
        improved = delta > _EPSILON if direction == "higher" else delta < -_EPSILON
        regressed = delta < -_EPSILON if direction == "higher" else delta > _EPSILON
        deltas.append(
            MetricDelta(
                metric=metric,
                left=left_value,
                right=right_value,
                delta=round(delta, 6),
                preferred_direction=direction,
                improved=improved,
                regressed=regressed,
            )
        )

    gate_names = sorted(set(left.hard_gates) | set(right.hard_gates))
    gate_changes = tuple(
        GateChange(gate=name, left=bool(left.hard_gates.get(name)), right=bool(right.hard_gates.get(name)))
        for name in gate_names
        if bool(left.hard_gates.get(name)) != bool(right.hard_gates.get(name))
    )
    left_failures = set(left.failure_case_ids)
    right_failures = set(right.failure_case_ids)
    new_failures = tuple(sorted(right_failures - left_failures))
    resolved_failures = tuple(sorted(left_failures - right_failures))
    regressed = any(item.regressed for item in deltas) or any(
        change.left and not change.right for change in gate_changes
    ) or bool(new_failures)
    improved = any(item.improved for item in deltas) or any(
        not change.left and change.right for change in gate_changes
    ) or bool(resolved_failures)
    verdict = (
        ComparisonVerdict.REGRESSED
        if regressed
        else ComparisonVerdict.IMPROVED
        if improved
        else ComparisonVerdict.STABLE
    )
    return EvaluationComparison(
        left_id=left.summary.id,
        right_id=right.summary.id,
        compatible=True,
        incompatibility_reasons=(),
        verdict=verdict,
        policy_changed=left.summary.policy_fingerprint != right.summary.policy_fingerprint,
        left_policy_fingerprint=left.summary.policy_fingerprint,
        right_policy_fingerprint=right.summary.policy_fingerprint,
        metric_deltas=tuple(deltas),
        gate_changes=gate_changes,
        new_failure_case_ids=new_failures,
        resolved_failure_case_ids=resolved_failures,
    )
