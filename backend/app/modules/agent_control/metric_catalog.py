from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MetricDirection = Literal["higher", "lower"]
MetricReportSource = Literal["metrics", "fusion"]


@dataclass(frozen=True, slots=True)
class EvaluationMetricSpec:
    direction: MetricDirection
    report_source: MetricReportSource


EVALUATION_METRICS: dict[str, EvaluationMetricSpec] = {
    "case_pass_rate": EvaluationMetricSpec("higher", "metrics"),
    "mean_source_recall": EvaluationMetricSpec("higher", "metrics"),
    "citation_completeness": EvaluationMetricSpec("higher", "metrics"),
    "immutable_evidence_identity_rate": EvaluationMetricSpec("higher", "metrics"),
    "unauthorized_action_rate": EvaluationMetricSpec("lower", "metrics"),
    "recovery_scenario_pass_rate": EvaluationMetricSpec("higher", "metrics"),
    "multi_hop_agent_lift_pp": EvaluationMetricSpec("higher", "metrics"),
    "fusion_recall_at_10": EvaluationMetricSpec("higher", "fusion"),
    "fusion_ndcg_at_10": EvaluationMetricSpec("higher", "fusion"),
}


def report_metric_names(source: MetricReportSource) -> tuple[str, ...]:
    return tuple(name for name, spec in EVALUATION_METRICS.items() if spec.report_source == source)
