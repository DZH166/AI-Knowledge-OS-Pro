"""Deterministic comparison report collaborator for optimizer Trials."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
from itertools import combinations

from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evaluation import AgentEvaluation
from app.modules.agent_control.report import EvaluationReportError, validate_evaluation_report
from app.modules.agent_control.sanitization import contains_sensitive_text
from app.modules.agent_policy.config import policy_config_from_snapshot
from app.modules.agent_policy_optimizer.category_analysis import compare_categories
from app.modules.agent_policy_optimizer.contracts import ExportComparison, ExportComparisonReceipt
from app.modules.agent_policy_optimizer.objectives import METRIC_DIRECTIONS
from app.modules.agent_policy_optimizer.internal import required_study, required_trial


SessionFactory = Callable[[], Session]


class OptimizerComparisonExporter:
    """Builds a stable report without changing Study or Trial state."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def export(self, command: ExportComparison) -> ExportComparisonReceipt:
        """Render a deterministic Markdown comparison report for 2-3 trials."""

        from app.modules.agent_policy_optimizer.category_analysis import CaseResult
        from app.modules.agent_policy_optimizer.report_export import render_comparison_markdown

        if len(command.trial_ids) < 2 or len(command.trial_ids) > 3:
            raise ServiceError(
                code="OPTIMIZER_EXPORT_TRIALS_INVALID",
                message="Comparison export requires between 2 and 3 trials.",
                status_code=422,
            )
        if len(set(command.trial_ids)) != len(command.trial_ids):
            raise ServiceError(
                code="OPTIMIZER_EXPORT_TRIALS_DUPLICATED",
                message="Comparison export requires distinct Trial identifiers.",
                status_code=422,
            )
        with self._sessions() as session:
            study = required_study(session, command.study_id)
            trials = []
            for trial_id in command.trial_ids:
                trial = required_trial(session, trial_id)
                if trial.study_id != study.id:
                    raise ServiceError(
                        code="OPTIMIZER_TRIAL_NOT_FOUND",
                        message="Trial does not belong to this study.",
                        status_code=404,
                    )
                if trial.status != "completed" or trial.evaluation_id is None:
                    raise ServiceError(
                        code="OPTIMIZER_EXPORT_TRIALS_INVALID",
                        message="Only completed trials can be exported.",
                        status_code=409,
                    )
                evaluation = session.get(AgentEvaluation, trial.evaluation_id)
                if evaluation is None or evaluation.report_json is None:
                    raise ServiceError(
                        code="OPTIMIZER_EXPORT_TRIALS_INVALID",
                        message="Trial evaluation report is unavailable.",
                        status_code=409,
                    )
                try:
                    report = validate_evaluation_report(json.loads(evaluation.report_json))
                except (EvaluationReportError, TypeError, json.JSONDecodeError) as exc:
                    raise ServiceError(
                        code="OPTIMIZER_EXPORT_REPORT_INVALID",
                        message="Trial evaluation report is invalid or unreadable.",
                        status_code=409,
                    ) from exc
                if (
                    report.policy_fingerprint != trial.config_sha256
                    or evaluation.policy_fingerprint != trial.config_sha256
                    or evaluation.report_sha256 != report.report_sha256
                ):
                    raise ServiceError(
                        code="OPTIMIZER_EXPORT_IDENTITY_MISMATCH",
                        message="Trial, policy snapshot, and evaluation report identities do not match.",
                        status_code=409,
                    )
                trials.append((trial, report))

            columns = [f"trial {index + 1} (ordinal {trial.ordinal})" for index, (trial, _) in enumerate(trials)]
            metric_rows = []
            for name, direction in METRIC_DIRECTIONS.items():
                if name == "retrieval_window":
                    continue
                if name == "latency_ms":
                    values = [float(report.latency_ms["agent_p95"]) for _, report in trials]
                elif name == "external_provider_calls":
                    values = [float(report.external_provider_calls) for _, report in trials]
                else:
                    values = [float(report.metrics[name]) for _, report in trials]
                best_index = values.index(max(values)) if direction == "higher" else values.index(min(values))
                metric_rows.append(
                    {
                        "metric": name,
                        "direction": direction,
                        "values": tuple(values),
                        "deltas": tuple(round(values[right] - values[left], 6) for left, right in combinations(range(len(values)), 2)),
                        "best": columns[best_index],
                    }
                )
            window_values = []
            for trial, _ in trials:
                config = policy_config_from_snapshot(trial.config_json, trial.config_sha256)
                window_values.append(
                    float(config.factual_top_k + config.comparative_top_k + config.temporal_top_k)
                )
            best_window = window_values.index(min(window_values))
            metric_rows.append(
                {
                    "metric": "retrieval_window",
                    "direction": "lower",
                    "values": tuple(window_values),
                    "deltas": tuple(round(window_values[right] - window_values[left], 6) for left, right in combinations(range(len(window_values)), 2)),
                    "best": columns[best_window],
                }
            )

            gate_names = sorted(trials[0][1].hard_gates)
            gate_rows = [
                {
                    "gate": gate,
                    "values": tuple(report.hard_gates.get(gate) for _, report in trials),
                    "changed": len({report.hard_gates.get(gate) for _, report in trials}) > 1,
                }
                for gate in gate_names
            ]

            category_rows = None
            if command.include_categories:
                category_rows = []
                def cases(report):
                    return [CaseResult(
                        case_id=item.case_id, category=item.category, passed=item.passed,
                        source_recall=float(item.source_recall), latency_ms=float(item.latency_ms),
                    ) for item in report.cases]
                for left, right in combinations(range(len(trials)), 2):
                    comparison = compare_categories(cases(trials[left][1]), cases(trials[right][1]))
                    category_rows.extend({
                        "comparison": f"trial {left + 1} vs trial {right + 1}",
                        "category": row.category,
                        "pass_rates": (row.pass_rate_left, row.pass_rate_right),
                        "wins": row.wins, "ties": row.ties, "losses": row.losses,
                        "verdict": row.verdict,
                    } for row in comparison)
            failure_rows = [
                {"trial": columns[index], "failed_case_ids": tuple(report.failure_case_ids)}
                for index, (_, report) in enumerate(trials)
            ]

            markdown = render_comparison_markdown(
                title=f"Retrieval optimizer comparison report - study {study.id}",
                columns=columns,
                metric_rows=metric_rows,
                gate_rows=gate_rows,
                category_rows=category_rows,
                failure_rows=failure_rows,
            )
            if contains_sensitive_text(markdown):
                raise ServiceError(
                    code="OPTIMIZER_EXPORT_DISHONEST",
                    message="Report content contains secret-looking data.",
                    status_code=422,
                )
            return {
                "study_id": study.id,
                "markdown": markdown,
                "sha256": sha256(markdown.encode("utf-8")).hexdigest(),
                "generated_trial_ids": list(command.trial_ids),
            }
