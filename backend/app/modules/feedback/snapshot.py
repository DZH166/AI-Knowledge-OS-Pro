"""Capture persisted facts, never caller-authored evidence or live provider output."""
from __future__ import annotations

from hashlib import sha256
import json

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evidence import AgentArtifact, AgentClaim, AgentEvidence, ClaimEvidence
from app.models.agent_run import AgentRun
from app.modules.feedback.contracts import FeedbackSnapshot, SubmitFeedback


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def failure(code: str, message: str, status: int = 409) -> None:
    raise ServiceError(code=code, message=message, status_code=status)


def capture(session: Session, command: SubmitFeedback) -> FeedbackSnapshot:
    artifact = session.get(AgentArtifact, command.artifact_id)
    if artifact is None:
        failure("FEEDBACK_TARGET_NOT_FOUND", "成果不存在。", 404)
    run = session.get(AgentRun, artifact.producing_run_id)
    if (run is None or run.status not in {"completed", "insufficient_evidence"}
            or run.final_artifact_id != artifact.id or artifact.status not in {"final", "published"}):
        failure("FEEDBACK_TARGET_NOT_FINAL", "只能反馈已终结任务的最终成果。")
    claim = session.get(AgentClaim, command.claim_id) if command.claim_id else None
    if command.claim_id and (claim is None or claim.artifact_id != artifact.id):
        failure("FEEDBACK_CLAIM_MISMATCH", "结论不属于该成果。", 422)
    query = select(AgentEvidence).join(ClaimEvidence, ClaimEvidence.evidence_id == AgentEvidence.id).join(
        AgentClaim, AgentClaim.id == ClaimEvidence.claim_id,
    ).where(AgentClaim.artifact_id == artifact.id)
    if claim is not None:
        query = query.where(AgentClaim.id == claim.id)
    rows = session.scalars(query.order_by(AgentEvidence.id).distinct().limit(201)).all()
    if len(rows) > 200 or any(row.run_id != run.id for row in rows):
        failure("FEEDBACK_SNAPSHOT_INVALID", "成果证据范围无效或超过 200 条。")
    try:
        result = FeedbackSnapshot(
            run_id=run.id, run_version=run.version, space_id=run.space_id, goal=run.goal,
            provider_mode=run.provider_mode, scope=json.loads(run.scope_snapshot_json), scope_digest=run.scope_digest,
            policy_id=run.decision_policy_id, policy_version=run.decision_policy_version,
            policy_fingerprint=run.decision_policy_fingerprint,
            artifact_id=artifact.id, artifact_title=artifact.title, artifact_body=artifact.body_markdown,
            claim={"id": claim.id, "text": claim.text, "verification_status": claim.verification_status} if claim else None,
            evidence=[{
                "id": row.id, "source_id": row.source_id, "revision_id": row.revision_id,
                "index_revision_id": row.index_revision_id, "chunk_id": row.chunk_id,
                "source_type": row.source_type, "locator": json.loads(row.locator_json),
                "revision_content_hash": row.revision_content_hash, "content_hash": row.evidence_content_hash,
                "excerpt": row.excerpt_preview,
            } for row in rows],
        )
        if len(canonical(result.model_dump(mode="json")).encode("utf-8")) > 262144:
            failure("FEEDBACK_SNAPSHOT_TOO_LARGE", "成果快照超过 256 KiB，无法完整保存。", 422)
        return result
    except (ValidationError, ValueError, TypeError):
        failure("FEEDBACK_SNAPSHOT_INVALID", "历史成果数据无法验证，未保存反馈。")
        raise AssertionError("unreachable")
