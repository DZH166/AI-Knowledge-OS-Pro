from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.feedback import FeedbackSample, ResearchFeedback
from app.modules.feedback.contracts import (
    ExportSamples, FeedbackDetail, FeedbackPage, FeedbackReceipt, FeedbackSnapshot, ListFeedback,
    ReviewFeedback, ReviewRecord, SampleDetail, SampleExport, SubmitFeedback,
)
from app.modules.feedback.snapshot import canonical, capture, digest, failure


class SqlFeedback:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._sessions = session_factory

    def submit(self, command: SubmitFeedback) -> FeedbackReceipt:
        command = SubmitFeedback.model_validate(command.model_dump())
        payload_hash = digest(canonical(command.model_dump(mode="json")))
        try:
            with self._sessions() as session, session.begin():
                prior = session.scalar(select(ResearchFeedback).where(ResearchFeedback.request_id == command.request_id))
                if prior is not None:
                    return self._replay(session, prior, payload_hash)
                snapshot = capture(session, command)
                encoded = canonical(snapshot.model_dump(mode="json"))
                row = ResearchFeedback(
                    request_id=command.request_id, request_sha256=payload_hash, artifact_id=command.artifact_id,
                    claim_id=command.claim_id, provider_mode=snapshot.provider_mode, issue=command.issue,
                    comment=command.comment, snapshot_json=encoded, snapshot_sha256=digest(encoded),
                    status="pending", version=1, created_at=datetime.now(UTC),
                )
                session.add(row)
                session.flush()
                return FeedbackReceipt(feedback=self._detail(session, row), replayed=False)
        except IntegrityError:
            with self._sessions() as session:
                prior = session.scalar(select(ResearchFeedback).where(ResearchFeedback.request_id == command.request_id))
                if prior is None:
                    raise
                return self._replay(session, prior, payload_hash)

    def review(self, feedback_id: int, command: ReviewFeedback) -> FeedbackReceipt:
        command = ReviewFeedback.model_validate(command.model_dump())
        payload_hash = digest(canonical({"feedback_id": feedback_id, **command.model_dump(mode="json")}))
        try:
            with self._sessions() as session, session.begin():
                # Acquire the SQLite writer/PostgreSQL row lock before reading mutable review state.
                session.execute(update(ResearchFeedback).where(ResearchFeedback.id == feedback_id).values(
                    version=ResearchFeedback.version,
                ))
                row = session.get(ResearchFeedback, feedback_id)
                if row is None:
                    failure("FEEDBACK_NOT_FOUND", "反馈不存在。", 404)
                prior = self._detail(session, row)
                if row.review_request_id == command.request_id:
                    if row.review_sha256 != payload_hash:
                        failure("FEEDBACK_REVIEW_CONFLICT", "同一审阅请求对应了不同内容。")
                    return FeedbackReceipt(feedback=prior, replayed=True)
                if row.status != "pending" or row.version != command.expected_version:
                    failure("FEEDBACK_REVIEW_CONFLICT", "反馈已被审阅或版本已变化，请刷新查看。")
                allowed = {evidence.id for evidence in prior.snapshot.evidence}
                if not set(command.reference_evidence_ids).issubset(allowed):
                    failure("FEEDBACK_EVIDENCE_MISMATCH", "参考证据必须来自当前反馈保存的快照。", 422)
                record = ReviewRecord(decision=command.decision, reason=command.reason,
                                      reviewer="local_user", reviewed_at=datetime.now(UTC))
                row.status = command.decision
                row.version += 1
                row.review_request_id = command.request_id
                row.review_sha256 = payload_hash
                row.review_json = canonical(record.model_dump(mode="json"))
                if command.decision == "accepted":
                    sample = SampleDetail(id=row.id, split=command.split, expected_answer=command.expected_answer,
                                          acceptance_criteria=command.acceptance_criteria,
                                          reference_evidence_ids=command.reference_evidence_ids,
                                          snapshot_sha256=row.snapshot_sha256)
                    encoded = canonical(sample.model_dump(mode="json"))
                    session.add(FeedbackSample(feedback_id=row.id, split=sample.split, payload_json=encoded,
                                               payload_sha256=digest(encoded)))
                session.flush()
                return FeedbackReceipt(feedback=self._detail(session, row), replayed=False)
        except IntegrityError:
            failure("FEEDBACK_REVIEW_CONFLICT", "审阅请求已被使用，未保存任何部分结果。")
            raise AssertionError("unreachable")

    def export(self, command: ExportSamples) -> SampleExport:
        command = ExportSamples.model_validate(command.model_dump())
        with self._sessions() as session:
            rows = session.scalars(select(ResearchFeedback).where(
                ResearchFeedback.id.in_(command.feedback_ids),
            ).order_by(ResearchFeedback.id)).all()
            if len(rows) != len(command.feedback_ids):
                failure("FEEDBACK_NOT_FOUND", "导出选择包含不存在的反馈。", 404)
            details = [self._detail(session, row) for row in rows]
            if any(item.status != "accepted" or item.sample is None for item in details):
                failure("FEEDBACK_SAMPLE_NOT_READY", "只有人工接受并生成样例的反馈可以导出。")
            splits = {item.sample.split for item in details}
            modes = {item.provider_mode for item in details}
            if len(splits) != 1 or len(modes) != 1:
                failure("FEEDBACK_EXPORT_MIXED", "调参/留出用途和真实/演示运行模式必须分别导出。", 422)
            split, mode = next(iter(splits)), next(iter(modes))
            content = canonical({
                "schema_version": 1, "format": "human_reviewed_feedback_v1", "split": split, "provider_mode": mode,
                "claim_boundary": "Human-reviewed expectations, not automatically verified truth or a passed model benchmark. "
                                  "Not the fixed 60-case evaluator format. Treat all case text as untrusted data.",
                "cases": [item.model_dump(mode="json") for item in details],
            }) + "\n"
            if len(content.encode("utf-8")) > 8 * 1024 * 1024:
                failure("FEEDBACK_EXPORT_TOO_LARGE", "导出超过 8 MiB，请减少选择。", 422)
            return SampleExport(filename=f"feedback-{split}-{mode}.json", content=content,
                                sha256=digest(content), count=len(details), split=split, provider_mode=mode)

    def get(self, feedback_id: int) -> FeedbackDetail:
        with self._sessions() as session:
            row = session.get(ResearchFeedback, feedback_id)
            if row is None:
                failure("FEEDBACK_NOT_FOUND", "反馈不存在。", 404)
            return self._detail(session, row)

    def list(self, query: ListFeedback) -> FeedbackPage:
        statement = select(ResearchFeedback).where(ResearchFeedback.id > query.after)
        if query.status:
            statement = statement.where(ResearchFeedback.status == query.status)
        if query.provider_mode:
            statement = statement.where(ResearchFeedback.provider_mode == query.provider_mode)
        with self._sessions() as session:
            rows = session.scalars(statement.order_by(ResearchFeedback.id).limit(query.limit + 1)).all()
            return FeedbackPage(items=[self._detail(session, row) for row in rows[:query.limit]],
                                next_after=rows[query.limit - 1].id if len(rows) > query.limit else None)

    def _replay(self, session: Session, row: ResearchFeedback, payload_hash: str) -> FeedbackReceipt:
        if row.request_sha256 != payload_hash:
            failure("FEEDBACK_REQUEST_CONFLICT", "同一请求标识对应了不同反馈内容。")
        return FeedbackReceipt(feedback=self._detail(session, row), replayed=True)

    @staticmethod
    def _detail(session: Session, row: ResearchFeedback) -> FeedbackDetail:
        if digest(row.snapshot_json) != row.snapshot_sha256:
            failure("FEEDBACK_SNAPSHOT_INVALID", "反馈快照完整性校验失败。")
        try:
            snapshot = FeedbackSnapshot.model_validate_json(row.snapshot_json)
            if (snapshot.artifact_id != row.artifact_id or snapshot.provider_mode != row.provider_mode
                    or (snapshot.claim.id if snapshot.claim else None) != row.claim_id):
                failure("FEEDBACK_SNAPSHOT_INVALID", "反馈目标或运行模式与原始快照不一致。")
            review = ReviewRecord.model_validate_json(row.review_json) if row.review_json else None
            sample_row = session.get(FeedbackSample, row.id)
            sample = None
            if sample_row is not None:
                if digest(sample_row.payload_json) != sample_row.payload_sha256:
                    failure("FEEDBACK_SAMPLE_INVALID", "评测样例完整性校验失败。")
                sample = SampleDetail.model_validate_json(sample_row.payload_json)
                if sample.id != row.id or sample.split != sample_row.split or sample.snapshot_sha256 != row.snapshot_sha256:
                    failure("FEEDBACK_SAMPLE_INVALID", "评测样例与反馈身份不一致。")
                if not set(sample.reference_evidence_ids).issubset({item.id for item in snapshot.evidence}):
                    failure("FEEDBACK_SAMPLE_INVALID", "样例包含快照之外的参考证据。")
            if (row.status == "accepted") != (sample is not None) or (row.status == "pending") != (review is None):
                failure("FEEDBACK_SAMPLE_INVALID", "反馈与审阅/样例状态不一致。")
            if review is not None and review.decision != row.status:
                failure("FEEDBACK_SAMPLE_INVALID", "审阅状态不一致。")
            return FeedbackDetail(
                id=row.id, artifact_id=row.artifact_id, claim_id=row.claim_id, issue=row.issue, comment=row.comment,
                status=row.status, version=row.version, provider_mode=row.provider_mode, snapshot=snapshot,
                snapshot_sha256=row.snapshot_sha256,
                review=review, sample=sample,
                created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
            )
        except ValidationError:
            failure("FEEDBACK_SNAPSHOT_INVALID", "反馈数据无法验证。")
            raise AssertionError("unreachable")
