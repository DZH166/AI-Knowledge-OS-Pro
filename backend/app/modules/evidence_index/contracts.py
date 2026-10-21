from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, TypeAlias


JsonObject: TypeAlias = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    chunk_index: int
    modality: str
    content: str
    locator: JsonObject
    search_text: str | None = None


@dataclass(frozen=True, slots=True)
class RevisionDraft:
    source_id: int
    content_hash: str
    index_version: str
    collection_name: str
    chunks: tuple[ChunkDraft, ...]
    parser_name: str | None = None
    parser_version: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    embedding_fingerprint: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StageRevision:
    command_id: str
    draft: RevisionDraft


@dataclass(frozen=True, slots=True)
class VerifiedPoint:
    point_id: str
    payload_digest: str


@dataclass(frozen=True, slots=True)
class ActivateRevision:
    command_id: str
    revision_id: int
    verified_points: tuple[VerifiedPoint, ...]


@dataclass(frozen=True, slots=True)
class PointEmbedding:
    point_id: str
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class UpsertRevisionVectors:
    command_id: str
    revision_id: int
    points: tuple[PointEmbedding, ...]


@dataclass(frozen=True, slots=True)
class CancelRevision:
    command_id: str
    revision_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class ReconcileIndex:
    command_id: str
    collection_name: str
    apply: bool = False


EvidenceCommand: TypeAlias = (
    StageRevision
    | ActivateRevision
    | UpsertRevisionVectors
    | CancelRevision
    | ReconcileIndex
)


@dataclass(frozen=True, slots=True)
class GetRevision:
    revision_id: int


@dataclass(frozen=True, slots=True)
class GetSourceState:
    source_id: int


@dataclass(frozen=True, slots=True)
class GetEvidenceChunk:
    revision_id: int
    chunk_id: int


@dataclass(frozen=True, slots=True)
class GetEvidenceNeighbors:
    revision_id: int
    chunk_id: int
    before: int = 1
    after: int = 1


EvidenceQuery: TypeAlias = (
    GetRevision | GetSourceState | GetEvidenceChunk | GetEvidenceNeighbors
)


@dataclass(frozen=True, slots=True)
class PointExpectation:
    point_id: str
    payload_digest: str
    status: str


@dataclass(frozen=True, slots=True)
class RevisionView:
    revision_id: int
    revision_number: int
    source_id: int
    status: str
    content_hash: str
    chunk_count: int
    index_revision_id: int
    index_status: str
    manifest_digest: str
    points: tuple[PointExpectation, ...]
    supersedes_revision_id: int | None


@dataclass(frozen=True, slots=True)
class SourceState:
    source_id: int
    active_revision_id: int | None
    active_index_revision_id: int | None
    revision_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EvidenceWindow:
    center_chunk_id: int
    items: tuple["PinnedEvidenceRef", ...]


@dataclass(frozen=True, slots=True)
class ActiveScope:
    space_id: int
    source_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PinnedScope:
    space_id: int
    revision_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SearchEvidence:
    text: str
    scope: ActiveScope | PinnedScope
    limit: int = 10


@dataclass(frozen=True, slots=True)
class ActiveEvidenceRef:
    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    source_type: str
    modality: str
    content_hash: str
    locator: JsonObject
    excerpt: str
    scope: Literal["active"] = "active"


@dataclass(frozen=True, slots=True)
class PinnedEvidenceRef:
    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    source_type: str
    modality: str
    content_hash: str
    locator: JsonObject
    excerpt: str
    currently_active: bool
    scope: Literal["pinned"] = "pinned"


EvidenceQueryResult: TypeAlias = RevisionView | SourceState | PinnedEvidenceRef | EvidenceWindow


@dataclass(frozen=True, slots=True)
class EvidenceHit:
    evidence: ActiveEvidenceRef | PinnedEvidenceRef
    score: float


@dataclass(frozen=True, slots=True)
class EvidenceSearchResult:
    hits: tuple[EvidenceHit, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    kind: Literal["orphan", "missing", "payload_mismatch"]
    collection_name: str
    point_id: str
    manifest_id: int | None
    source_id: int | None
    revision_id: int | None
    index_revision_id: int | None
    expected_payload_digest: str | None = None
    actual_payload_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationRepair:
    action: Literal["deleted_orphan", "rewrote_payload", "marked_missing"]
    point_id: str


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    command_id: str
    collection_name: str
    applied: bool
    issues: tuple[ReconciliationIssue, ...]
    repairs: tuple[ReconciliationRepair, ...] = ()
    repair_count: int = 0


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    command_id: str
    operation_id: str
    operation: str
    status: str
    source_id: int
    revision_id: int
    index_revision_id: int
    replayed: bool = False


EvidenceCommandResult: TypeAlias = CommandReceipt | ReconciliationReport


class EvidenceIndexError(Exception):
    code = "EVIDENCE_INDEX_ERROR"


class EvidenceNotFoundError(EvidenceIndexError):
    code = "EVIDENCE_NOT_FOUND"


class IdempotencyConflictError(EvidenceIndexError):
    code = "IDEMPOTENCY_CONFLICT"


class ActivationInvariantError(EvidenceIndexError):
    code = "ACTIVATION_INVARIANT_FAILED"


class InvalidRevisionDraftError(EvidenceIndexError):
    code = "INVALID_REVISION_DRAFT"


class InvalidEvidenceWindowError(EvidenceIndexError):
    code = "INVALID_EVIDENCE_WINDOW"


class VectorAdapterRequiredError(EvidenceIndexError):
    code = "VECTOR_ADAPTER_REQUIRED"


class VectorManifestMismatchError(EvidenceIndexError):
    code = "VECTOR_MANIFEST_MISMATCH"


class RevisionLifecycleConflictError(EvidenceIndexError):
    code = "REVISION_LIFECYCLE_CONFLICT"

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class VectorWriteError(EvidenceIndexError):
    code = "VECTOR_WRITE_FAILED"
