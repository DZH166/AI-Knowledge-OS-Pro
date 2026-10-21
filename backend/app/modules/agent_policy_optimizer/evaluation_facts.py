"""Read exact category facts from immutable reports, including legacy aggregate rows."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.agent_evaluation import AgentEvaluation
from app.models.optimizer import OptimizationTrial
from app.modules.agent_control.report import validate_evaluation_report
from app.modules.agent_policy_optimizer.category_analysis import CaseResult, serialize_case_results
from app.modules.agent_policy_optimizer.contracts import CategoryStatsView


def category_facts(session: Session, trial: OptimizationTrial) -> CategoryStatsView | None:
    if trial.status != "completed" or not trial.evaluation_id:
        return None
    evaluation = session.get(AgentEvaluation, trial.evaluation_id)
    if evaluation is None or not evaluation.report_json:
        return None
    try:
        report = validate_evaluation_report(json.loads(evaluation.report_json))
        if report.report_sha256 != evaluation.report_sha256 or report.policy_fingerprint != trial.config_sha256:
            return None
        return serialize_case_results(CaseResult(
            case_id=item.case_id, category=item.category, passed=item.passed,
            source_recall=item.source_recall, latency_ms=item.latency_ms,
        ) for item in report.cases)
    except (ValueError, TypeError, KeyError):
        return None
