from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_policy import AgentPolicyVersion
from app.modules.agent_control.report import REQUIRED_HARD_GATES


def require_matching_fixed_evaluation(
    session: Session,
    policy: AgentPolicyVersion,
    evaluation_id: str,
) -> None:
    evaluation = session.get(AgentEvaluation, evaluation_id)
    try:
        hard_gates_payload = json.loads(evaluation.hard_gates_json) if evaluation is not None else None
    except json.JSONDecodeError:
        hard_gates_payload = None
    hard_gates_match = (
        isinstance(hard_gates_payload, dict)
        and set(hard_gates_payload) == REQUIRED_HARD_GATES
        and all(type(value) is bool and value for value in hard_gates_payload.values())
    )
    if (
        evaluation is None
        or evaluation.status != "passed"
        or evaluation.schema_version != 2
        or evaluation.policy_version_id != policy.id
        or evaluation.policy_fingerprint != policy.config_sha256
        or evaluation.policy_snapshot_json != policy.config_json
        or evaluation.dataset_name != "v5_fixed_evidence_cases"
        or evaluation.dataset_path != "evaluation/v5/cases.jsonl"
        or not _is_sha256(evaluation.dataset_sha256)
        or not _is_sha256(evaluation.evaluator_sha256)
        or not _is_sha256(evaluation.report_sha256)
        or evaluation.case_count != 60
        or evaluation.case_pass_rate_millis != 1_000
        or evaluation.external_provider_calls != 0
        or evaluation.failure_case_count != 0
        or not hard_gates_match
        or evaluation.failure_case_ids_json != "[]"
        or "not a real-model quality benchmark" not in evaluation.provider_boundary
    ):
        raise ServiceError(
            code="POLICY_EVALUATION_REQUIRED",
            message="Activation requires a matching passed fixed evaluation.",
            status_code=409,
        )


def _is_sha256(value: str | None) -> bool:
    return bool(
        value
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )
