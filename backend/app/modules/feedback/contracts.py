from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator


Identifier = Annotated[str, StringConstraints(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")]
RequestId = Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Issue = Literal["missing_evidence", "incorrect_answer", "unsupported_citation", "incomplete_answer"]
ProviderMode = Literal["real", "demo", "recording"]
FeedbackStatus = Literal["pending", "accepted", "rejected"]
SampleSplit = Literal["tuning", "holdout"]
ReferenceAnswer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SubmitFeedback(Contract):
    request_id: RequestId
    artifact_id: Identifier
    claim_id: Identifier | None = None
    issue: Issue
    comment: Comment


class ClaimSnapshot(Contract):
    id: str
    text: str
    verification_status: str


class EvidenceSnapshot(Contract):
    id: str
    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    source_type: str
    locator: dict[str, JsonValue]
    revision_content_hash: Digest
    content_hash: Digest
    excerpt: str


class FeedbackSnapshot(Contract):
    run_id: str
    run_version: int
    space_id: int
    goal: str
    provider_mode: ProviderMode
    scope: dict[str, JsonValue]
    scope_digest: Digest
    policy_id: str | None
    policy_version: int | None
    policy_fingerprint: str | None
    artifact_id: str
    artifact_title: str
    artifact_body: str
    claim: ClaimSnapshot | None
    evidence: list[EvidenceSnapshot]


class ReviewFeedback(Contract):
    request_id: RequestId
    expected_version: int = Field(ge=1, strict=True)
    decision: Literal["accepted", "rejected"]
    reason: Comment
    expected_answer: ReferenceAnswer | None = None
    acceptance_criteria: Comment | None = None
    split: SampleSplit | None = None
    reference_evidence_ids: list[Identifier] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def check_decision(self):
        if len(set(self.reference_evidence_ids)) != len(self.reference_evidence_ids):
            raise ValueError("参考证据不能重复。")
        if self.decision == "accepted":
            if not self.expected_answer or not self.acceptance_criteria or not self.split:
                raise ValueError("接受反馈需要参考答案、验收要求和样例用途。")
        elif self.expected_answer is not None or self.acceptance_criteria is not None or self.split is not None or self.reference_evidence_ids:
            raise ValueError("驳回不能包含评测样例字段。")
        return self


class ReviewRecord(Contract):
    decision: Literal["accepted", "rejected"]
    reason: str
    reviewer: Literal["local_user"]
    reviewed_at: datetime


class SampleDetail(Contract):
    id: int
    split: SampleSplit
    expected_answer: str
    acceptance_criteria: str
    reference_evidence_ids: list[str]
    snapshot_sha256: Digest
    expectation_kind: Literal["human_reviewed_not_automatically_verified"] = "human_reviewed_not_automatically_verified"


class FeedbackDetail(Contract):
    id: int
    artifact_id: str
    claim_id: str | None
    issue: Issue
    comment: str
    status: FeedbackStatus
    version: int
    provider_mode: ProviderMode
    snapshot: FeedbackSnapshot
    snapshot_sha256: Digest
    created_at: datetime
    review: ReviewRecord | None = None
    sample: SampleDetail | None = None


class FeedbackReceipt(Contract):
    feedback: FeedbackDetail
    replayed: bool


class FeedbackPage(Contract):
    items: list[FeedbackDetail]
    next_after: int | None


class ListFeedback(Contract):
    status: FeedbackStatus | None = None
    provider_mode: ProviderMode | None = None
    after: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ExportSamples(Contract):
    feedback_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_selection(self):
        if len(set(self.feedback_ids)) != len(self.feedback_ids):
            raise ValueError("导出选择不能重复。")
        return self


class SampleExport(Contract):
    filename: str
    content: str
    sha256: Digest
    count: int
    split: SampleSplit
    provider_mode: ProviderMode
