from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.evidence_index import IndexOperation, VectorPointManifest
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.modules.evidence_index.contracts import (
    ActiveEvidenceRef,
    ActiveScope,
    ActivateRevision,
    ActivationInvariantError,
    CancelRevision,
    CommandReceipt,
    EvidenceCommand,
    EvidenceCommandResult,
    EvidenceIndexError,
    EvidenceHit,
    EvidenceNotFoundError,
    EvidenceQuery,
    EvidenceQueryResult,
    EvidenceSearchResult,
    EvidenceWindow,
    GetEvidenceChunk,
    GetEvidenceNeighbors,
    GetRevision,
    GetSourceState,
    IdempotencyConflictError,
    InvalidRevisionDraftError,
    InvalidEvidenceWindowError,
    PinnedEvidenceRef,
    PinnedScope,
    PointExpectation,
    ReconcileIndex,
    RevisionView,
    RevisionLifecycleConflictError,
    SearchEvidence,
    SourceState,
    StageRevision,
    UpsertRevisionVectors,
    VectorAdapterRequiredError,
    VectorManifestMismatchError,
    VectorWriteError,
)
from app.modules.evidence_index.reconciler import IndexReconciler
from app.modules.evidence_index.vector_adapter import VectorIndexPort, VectorPointWrite
from app.services.lexical_retrieval import LexicalQuery


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode()).hexdigest()


class SqlEvidenceIndex:
    """SQLAlchemy implementation hidden behind the EvidenceIndex seam."""

    _STAGE_MAX_ATTEMPTS = 3

    def __init__(self, session: Session, vector_adapter: VectorIndexPort | None = None) -> None:
        self._session = session
        self._vector_adapter = vector_adapter

    def command(self, command: EvidenceCommand) -> EvidenceCommandResult:
        if isinstance(command, StageRevision):
            return self._stage(command)
        if isinstance(command, ActivateRevision):
            return self._activate(command)
        if isinstance(command, UpsertRevisionVectors):
            return self._upsert_vectors(command)
        if isinstance(command, CancelRevision):
            return self._cancel_revision(command)
        if isinstance(command, ReconcileIndex):
            if self._vector_adapter is None:
                raise VectorAdapterRequiredError("Reconciliation requires a configured vector adapter.")
            return IndexReconciler(self._session, self._vector_adapter).run(command)
        raise TypeError(f"Unsupported evidence command: {type(command).__name__}")

    def query(self, query: EvidenceQuery) -> EvidenceQueryResult:
        if isinstance(query, GetRevision):
            return self._revision_view(query.revision_id)
        if isinstance(query, GetSourceState):
            return self._source_state(query.source_id)
        if isinstance(query, GetEvidenceChunk):
            return self._evidence_chunk(query.revision_id, query.chunk_id)
        if isinstance(query, GetEvidenceNeighbors):
            return self._evidence_neighbors(query)
        raise TypeError(f"Unsupported evidence query: {type(query).__name__}")

    def search(self, request: SearchEvidence) -> EvidenceSearchResult:
        if isinstance(request.scope, ActiveScope):
            return self._search_active(request)
        if isinstance(request.scope, PinnedScope):
            return self._search_pinned(request)
        raise TypeError(f"Unsupported evidence scope: {type(request.scope).__name__}")

    def _stage(self, command: StageRevision) -> CommandReceipt:
        self._validate_stage(command)
        command_hash = _digest(asdict(command.draft))
        for attempt in range(self._STAGE_MAX_ATTEMPTS):
            try:
                return self._stage_once(command, command_hash)
            except IntegrityError as error:
                self._session.rollback()
                if not self._is_stage_unique_conflict(error):
                    raise
                replay = self._stage_replay(command, command_hash)
                if replay is not None:
                    return replay
                if attempt + 1 < self._STAGE_MAX_ATTEMPTS:
                    self._session.rollback()
                    continue
                self._session.rollback()
                raise RevisionLifecycleConflictError(
                    "Concurrent staging exhausted revision allocation retries; retry the command.",
                    retryable=True,
                ) from error
            except OperationalError as error:
                self._session.rollback()
                if not self._is_transient_write_conflict(error):
                    raise
                if attempt + 1 < self._STAGE_MAX_ATTEMPTS:
                    continue
                raise RevisionLifecycleConflictError(
                    "Concurrent staging could not acquire the source write lock; retry the command.",
                    retryable=True,
                ) from error
        raise AssertionError("Stage retry loop exited without a result.")

    def _stage_once(self, command: StageRevision, command_hash: str) -> CommandReceipt:
        replay = self._stage_replay(command, command_hash)
        if replay is not None:
            return replay

        source = self._lock_source_for_stage(command.draft.source_id)
        try:
            replay = self._stage_replay(command, command_hash)
        except IdempotencyConflictError:
            self._session.rollback()
            raise
        if replay is not None:
            self._session.rollback()
            return replay

        revision_number = int(
            self._session.scalar(
                select(func.coalesce(func.max(SourceRevision.revision_number), 0)).where(
                    SourceRevision.source_id == source.id
                )
            )
            or 0
        ) + 1
        revision = SourceRevision(
            source_id=source.id,
            revision_number=revision_number,
            status="staging",
            parser_name=command.draft.parser_name,
            parser_version=command.draft.parser_version,
            content_hash=command.draft.content_hash,
            chunk_count=len(command.draft.chunks),
            vector_count=len(command.draft.chunks),
            validation_status="pending",
            metadata_json=_canonical_json(command.draft.metadata),
            supersedes_revision_id=source.active_revision_id,
        )
        self._session.add(revision)
        self._session.flush()

        index_revision = IndexRevision(
            source_id=source.id,
            revision_id=revision.id,
            status="staging",
            index_version=command.draft.index_version,
            embedding_provider=command.draft.embedding_provider,
            embedding_model=command.draft.embedding_model,
            embedding_dimensions=command.draft.embedding_dimensions,
            embedding_fingerprint=command.draft.embedding_fingerprint,
            qdrant_collection=command.draft.collection_name,
            point_count=len(command.draft.chunks),
            validation_status="pending",
        )
        self._session.add(index_revision)
        self._session.flush()

        operation = IndexOperation(
            id=str(uuid4()),
            command_id=command.command_id,
            source_id=source.id,
            revision_id=revision.id,
            index_revision_id=index_revision.id,
            operation_type="stage_revision",
            status="staged",
            draft_hash=command_hash,
            parser_name=command.draft.parser_name,
            parser_version=command.draft.parser_version,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(operation)
        self._session.flush()

        manifest_parts: list[tuple[str, str]] = []
        for chunk_draft in command.draft.chunks:
            content_hash = sha256(chunk_draft.content.encode()).hexdigest()
            chunk = MultimodalChunk(
                source_id=source.id,
                revision_id=revision.id,
                chunk_index=chunk_draft.chunk_index,
                modality=chunk_draft.modality,
                source_type=source.source_type,
                content_text=chunk_draft.content,
                content_hash=content_hash,
                search_text=chunk_draft.search_text or chunk_draft.content,
                raw_payload_json="{}",
                locator_json=_canonical_json(chunk_draft.locator),
                status="staging",
            )
            self._session.add(chunk)
            self._session.flush()

            point_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"evidence:{source.id}:{revision.id}:{chunk.id}:{content_hash}",
                )
            )
            payload_digest = _digest(self._vector_payload(source, revision, index_revision, chunk))
            chunk.qdrant_point_id = point_id
            self._session.add(
                VectorPointManifest(
                    operation_id=operation.id,
                    source_id=source.id,
                    revision_id=revision.id,
                    index_revision_id=index_revision.id,
                    chunk_id=chunk.id,
                    collection_name=command.draft.collection_name,
                    point_id=point_id,
                    payload_digest=payload_digest,
                    status="expected",
                )
            )
            manifest_parts.append((point_id, payload_digest))

        index_revision.manifest_digest = _digest(sorted(manifest_parts))
        source.latest_revision_id = revision.id
        operation.finished_at = datetime.now(timezone.utc)
        self._session.commit()
        return self._receipt(operation, replayed=False)

    @staticmethod
    def _is_stage_unique_conflict(error: IntegrityError) -> bool:
        message = str(error.orig).casefold()
        diagnostic = getattr(error.orig, "diag", None)
        constraint_name = str(getattr(diagnostic, "constraint_name", "") or "").casefold()
        markers = (
            "uq_source_revision_number",
            "source_revisions.source_id, source_revisions.revision_number",
            "index_operations.command_id",
            "index_operations_command_id",
        )
        return any(marker in message or marker in constraint_name for marker in markers)

    @staticmethod
    def _is_transient_write_conflict(error: OperationalError) -> bool:
        message = str(error.orig).casefold()
        sqlstate = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
        return sqlstate in {"40001", "40P01", "55P03"} or any(
            marker in message
            for marker in ("database is locked", "database table is locked", "database is busy")
        )

    def _stage_replay(
        self,
        command: StageRevision,
        command_hash: str,
    ) -> CommandReceipt | None:
        existing = self._session.scalar(
            select(IndexOperation).where(IndexOperation.command_id == command.command_id)
        )
        if existing is None:
            return None
        if existing.draft_hash != command_hash or existing.operation_type != "stage_revision":
            raise IdempotencyConflictError(
                f"Command id {command.command_id!r} was already used with a different payload."
            )
        return self._receipt(existing, replayed=True)

    def _lock_source_for_stage(self, source_id: int) -> Source:
        dialect_name = self._session.get_bind().dialect.name
        if dialect_name == "sqlite":
            # SQLite has no row locks. A no-op write acquires its single writer lock,
            # making revision allocation safe at the cost of database-wide staging
            # serialization. PostgreSQL uses the source row lock below instead.
            result = self._session.execute(
                update(Source)
                .where(Source.id == source_id)
                .values(
                    latest_revision_id=Source.latest_revision_id,
                    updated_at=Source.updated_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 0:
                raise EvidenceNotFoundError(f"Source {source_id} does not exist.")
            source = self._session.get(Source, source_id)
        else:
            source = self._session.scalar(
                select(Source).where(Source.id == source_id).with_for_update()
            )
        if source is None:
            raise EvidenceNotFoundError(f"Source {source_id} does not exist.")
        return source

    def _cancel_revision(self, command: CancelRevision) -> CommandReceipt:
        command_hash = _digest({"revision_id": command.revision_id, "reason": command.reason})
        existing = self._session.scalar(
            select(IndexOperation).where(IndexOperation.command_id == command.command_id)
        )
        if existing is not None:
            if existing.draft_hash != command_hash or existing.operation_type != "cancel_revision":
                raise IdempotencyConflictError(
                    f"Command id {command.command_id!r} was already used with a different payload."
                )
            return self._receipt(existing, replayed=True)

        revision = self._session.get(SourceRevision, command.revision_id)
        if revision is None:
            raise EvidenceNotFoundError(f"Revision {command.revision_id} does not exist.")
        source = self._session.get(Source, revision.source_id)
        if source is None:
            raise EvidenceNotFoundError(f"Source {revision.source_id} does not exist.")
        index_revision = self._session.scalar(
            select(IndexRevision).where(IndexRevision.revision_id == revision.id)
        )
        if index_revision is None:
            raise EvidenceNotFoundError(f"Revision {revision.id} has no index revision.")
        if source.active_revision_id == revision.id or revision.status == "active":
            raise RevisionLifecycleConflictError(
                "An active revision must be replaced, not cancelled as a staging operation."
            )
        if revision.status == "cancelled" or index_revision.status == "cancelled":
            raise RevisionLifecycleConflictError(
                "A cancelled revision requires replaying its original command id."
            )

        manifests = list(
            self._session.scalars(
                select(VectorPointManifest).where(
                    VectorPointManifest.index_revision_id == index_revision.id
                )
            )
        )
        now = datetime.now(timezone.utc)
        operation = IndexOperation(
            id=str(uuid4()),
            command_id=command.command_id,
            source_id=source.id,
            revision_id=revision.id,
            index_revision_id=index_revision.id,
            operation_type="cancel_revision",
            status="cancelling",
            draft_hash=command_hash,
            parser_name=revision.parser_name,
            parser_version=revision.parser_version,
            started_at=now,
        )
        self._session.add(operation)
        self._session.commit()

        cleanup_error: Exception | None = None
        if self._vector_adapter is not None:
            try:
                self._vector_adapter.delete_points(
                    index_revision.qdrant_collection or "",
                    tuple(manifest.point_id for manifest in manifests),
                )
            except Exception as exc:
                cleanup_error = exc

        now = datetime.now(timezone.utc)
        revision.status = "cancelled"
        revision.validation_status = "failed"
        revision.error_message = command.reason
        revision.retired_at = now
        index_revision.status = "cancelled"
        index_revision.validation_status = "failed"
        index_revision.retired_at = now
        for chunk in self._session.scalars(
            select(MultimodalChunk).where(MultimodalChunk.revision_id == revision.id)
        ):
            chunk.status = "cancelled"
            chunk.retired_at = now
        for manifest in manifests:
            manifest.status = "cleanup_pending" if cleanup_error is not None else "deleted"
            manifest.last_verified_at = now
        operation.status = "cleanup_pending" if cleanup_error is not None else "cancelled"
        if cleanup_error is not None:
            operation.error_code = "VECTOR_DELETE_FAILED"
            operation.error_message = str(cleanup_error)
        operation.finished_at = now
        self._session.commit()
        if cleanup_error is not None:
            raise VectorWriteError(
                "Revision was cancelled, but vector cleanup is pending reconciliation."
            ) from cleanup_error
        return self._receipt(operation, replayed=False)

    def _upsert_vectors(self, command: UpsertRevisionVectors) -> CommandReceipt:
        if self._vector_adapter is None:
            raise VectorAdapterRequiredError("Vector upsert requires a configured vector adapter.")
        command_hash = _digest(
            {
                "revision_id": command.revision_id,
                "points": [
                    {"point_id": point.point_id, "vector": point.vector}
                    for point in sorted(command.points, key=lambda item: item.point_id)
                ],
            }
        )
        existing = self._session.scalar(
            select(IndexOperation).where(IndexOperation.command_id == command.command_id)
        )
        if existing is not None:
            if existing.draft_hash != command_hash or existing.operation_type != "upsert_revision_vectors":
                raise IdempotencyConflictError(
                    f"Command id {command.command_id!r} was already used with a different payload."
                )
            if existing.status != "upserting":
                return self._receipt(existing, replayed=True)

        revision = self._session.get(SourceRevision, command.revision_id)
        if revision is None:
            raise EvidenceNotFoundError(f"Revision {command.revision_id} does not exist.")
        source = self._session.get(Source, revision.source_id)
        if source is None:
            raise EvidenceNotFoundError(f"Source {revision.source_id} does not exist.")
        index_revision = self._session.scalar(
            select(IndexRevision).where(IndexRevision.revision_id == revision.id)
        )
        if index_revision is None:
            raise EvidenceNotFoundError(f"Revision {revision.id} has no index revision.")
        if revision.status != "staging" or index_revision.status != "staging":
            raise VectorManifestMismatchError("Vectors can only be stored for a staging revision and index.")

        rows = list(
            self._session.execute(
                select(VectorPointManifest, MultimodalChunk)
                .join(MultimodalChunk, MultimodalChunk.id == VectorPointManifest.chunk_id)
                .where(VectorPointManifest.index_revision_id == index_revision.id)
                .order_by(VectorPointManifest.point_id)
            )
        )
        requested = {point.point_id: point for point in command.points}
        expected_ids = {manifest.point_id for manifest, _chunk in rows}
        if (
            not rows
            or len(requested) != len(command.points)
            or set(requested) != expected_ids
        ):
            raise VectorManifestMismatchError(
                "Vector batch must match the persisted point manifest exactly."
            )
        expected_dimensions = index_revision.embedding_dimensions
        if any(
            not point.vector
            or (expected_dimensions is not None and len(point.vector) != expected_dimensions)
            or any(not math.isfinite(value) for value in point.vector)
            for point in command.points
        ):
            raise VectorManifestMismatchError("Vector dimensions and values must match the staged index.")

        writes: list[VectorPointWrite] = []
        for manifest, chunk in rows:
            payload = self._vector_payload(source, revision, index_revision, chunk)
            if manifest.payload_digest != _digest(payload):
                raise VectorManifestMismatchError(
                    f"Manifest payload digest for point {manifest.point_id} is inconsistent."
                )
            writes.append(
                VectorPointWrite(
                    point_id=manifest.point_id,
                    vector=requested[manifest.point_id].vector,
                    payload=payload,
                )
            )

        if existing is not None:
            return self._recover_upserting_vectors(
                existing,
                revision,
                index_revision,
                rows,
                writes,
            )

        now = datetime.now(timezone.utc)
        operation = IndexOperation(
            id=str(uuid4()),
            command_id=command.command_id,
            source_id=source.id,
            revision_id=revision.id,
            index_revision_id=index_revision.id,
            operation_type="upsert_revision_vectors",
            status="upserting",
            draft_hash=command_hash,
            parser_name=revision.parser_name,
            parser_version=revision.parser_version,
            started_at=now,
        )
        self._session.add(operation)
        self._session.commit()

        collection = index_revision.qdrant_collection or ""
        try:
            self._vector_adapter.upsert_points(collection, writes)
        except Exception as exc:
            cleanup_error: Exception | None = None
            try:
                self._vector_adapter.delete_points(
                    collection,
                    tuple(manifest.point_id for manifest, _chunk in rows),
                )
            except Exception as delete_exc:
                cleanup_error = delete_exc

            now = datetime.now(timezone.utc)
            operation.status = "cleanup_pending" if cleanup_error is not None else "failed"
            operation.error_code = "VECTOR_UPSERT_FAILED"
            operation.error_message = str(exc)
            operation.finished_at = now
            index_revision.validation_status = "failed"
            revision.validation_status = "failed"
            for manifest, _chunk in rows:
                manifest.status = "cleanup_pending" if cleanup_error is not None else "expected"
                manifest.last_verified_at = now
            self._session.commit()
            message = "Vector upsert failed after the manifest was committed."
            if cleanup_error is not None:
                message += " Compensation is pending reconciliation."
            raise VectorWriteError(message) from exc

        now = datetime.now(timezone.utc)
        operation.status = "stored"
        operation.finished_at = now
        index_revision.validation_status = "passed"
        revision.validation_status = "passed"
        for manifest, _chunk in rows:
            manifest.status = "stored"
            manifest.last_verified_at = now
        self._session.commit()
        return self._receipt(operation, replayed=False)

    def _recover_upserting_vectors(
        self,
        operation: IndexOperation,
        revision: SourceRevision,
        index_revision: IndexRevision,
        rows: list[tuple[VectorPointManifest, MultimodalChunk]],
        writes: list[VectorPointWrite],
    ) -> CommandReceipt:
        if self._vector_adapter is None:
            raise VectorAdapterRequiredError("Vector upsert recovery requires a configured vector adapter.")
        collection = index_revision.qdrant_collection or ""

        try:
            actual = {
                point.point_id: point
                for point in self._vector_adapter.list_points(collection)
            }
        except Exception as exc:
            raise VectorWriteError(
                "The interrupted vector upsert could not be verified and remains retryable."
            ) from exc

        expected_writes = {write.point_id: write for write in writes}

        def matches_manifest() -> bool:
            return all(
                manifest.point_id in actual
                and len(actual[manifest.point_id].vector)
                == len(expected_writes[manifest.point_id].vector)
                and all(
                    math.isclose(actual_value, expected_value, rel_tol=1e-6, abs_tol=1e-7)
                    for actual_value, expected_value in zip(
                        actual[manifest.point_id].vector,
                        expected_writes[manifest.point_id].vector,
                        strict=True,
                    )
                )
                and _digest(dict(actual[manifest.point_id].payload))
                == manifest.payload_digest
                for manifest, _chunk in rows
            )

        if not matches_manifest():
            try:
                self._vector_adapter.upsert_points(collection, writes)
                actual = {
                    point.point_id: point
                    for point in self._vector_adapter.list_points(collection)
                }
            except Exception as exc:
                raise VectorWriteError(
                    "The interrupted vector upsert could not be resumed and remains retryable."
                ) from exc
        if not matches_manifest():
            raise VectorWriteError(
                "The interrupted vector upsert does not match its persisted manifest."
            )

        now = datetime.now(timezone.utc)
        operation.status = "stored"
        operation.finished_at = now
        index_revision.validation_status = "passed"
        revision.validation_status = "passed"
        for manifest, _chunk in rows:
            manifest.status = "stored"
            manifest.last_verified_at = now
        self._session.commit()
        return self._receipt(operation, replayed=True)

    def _activate(self, command: ActivateRevision) -> CommandReceipt:
        command_hash = _digest(
            {
                "revision_id": command.revision_id,
                "verified_points": [asdict(point) for point in command.verified_points],
            }
        )
        existing = self._session.scalar(
            select(IndexOperation).where(IndexOperation.command_id == command.command_id)
        )
        if existing is not None:
            if existing.draft_hash != command_hash or existing.operation_type != "activate_revision":
                raise IdempotencyConflictError(
                    f"Command id {command.command_id!r} was already used with a different payload."
                )
            return self._receipt(existing, replayed=True)

        revision = self._session.get(SourceRevision, command.revision_id)
        if revision is None:
            raise EvidenceNotFoundError(f"Revision {command.revision_id} does not exist.")
        index_revision = self._session.scalar(
            select(IndexRevision).where(IndexRevision.revision_id == revision.id)
        )
        if index_revision is None:
            raise EvidenceNotFoundError(f"Revision {revision.id} has no index revision.")
        manifests = list(
            self._session.scalars(
                select(VectorPointManifest).where(
                    VectorPointManifest.index_revision_id == index_revision.id
                )
            )
        )
        expected = {(point.point_id, point.payload_digest) for point in manifests}
        verified = {(point.point_id, point.payload_digest) for point in command.verified_points}
        if (
            not expected
            or len(command.verified_points) != len(expected)
            or verified != expected
        ):
            raise ActivationInvariantError(
                "Activation requires the complete expected point manifest with matching payload digests."
            )

        source = self._session.get(Source, revision.source_id)
        if source is None:
            raise EvidenceNotFoundError(f"Source {revision.source_id} does not exist.")
        if source.retired_at is not None:
            raise ActivationInvariantError("A retired source cannot activate a new revision.")
        if revision.status != "staging" or index_revision.status != "staging":
            raise ActivationInvariantError("Only a staging revision and staging index can be activated.")
        if source.active_revision_id != revision.supersedes_revision_id:
            raise ActivationInvariantError(
                "The source active revision changed after this draft was staged; activation is stale."
            )

        chunks = list(
            self._session.scalars(
                select(MultimodalChunk)
                .where(MultimodalChunk.revision_id == revision.id)
                .order_by(MultimodalChunk.chunk_index, MultimodalChunk.id)
            )
        )
        if (
            not revision.content_hash
            or len(chunks) != revision.chunk_count
            or len(chunks) != revision.vector_count
            or len(chunks) != index_revision.point_count
            or len(chunks) != len(expected)
        ):
            raise ActivationInvariantError(
                "Revision, chunk, vector, index, and manifest counts must agree before activation."
            )
        if any(
            not chunk.content_hash
            or not chunk.qdrant_point_id
            or not self._valid_locator(chunk.locator_json)
            for chunk in chunks
        ):
            raise ActivationInvariantError(
                "Every active evidence chunk requires a content hash, point id, and valid locator."
            )
        if index_revision.manifest_digest != _digest(sorted(expected)):
            raise ActivationInvariantError("The persisted manifest digest does not match its points.")
        if self._vector_adapter is not None:
            if any(manifest.status not in {"stored", "active"} for manifest in manifests):
                raise ActivationInvariantError(
                    "Every manifest point must be stored before activation."
                )
            try:
                actual_points = {
                    point.point_id: point
                    for point in self._vector_adapter.list_points(
                        index_revision.qdrant_collection or ""
                    )
                }
            except Exception as exc:
                raise ActivationInvariantError(
                    "The vector index could not be verified before activation."
                ) from exc
            if any(
                manifest.point_id not in actual_points
                or _digest(dict(actual_points[manifest.point_id].payload))
                != manifest.payload_digest
                for manifest in manifests
            ):
                raise ActivationInvariantError(
                    "Stored vector points do not match the persisted manifest."
                )

        now = datetime.now(timezone.utc)
        previous_revision = (
            self._session.get(SourceRevision, source.active_revision_id)
            if source.active_revision_id is not None and source.active_revision_id != revision.id
            else None
        )
        previous_index = (
            self._session.get(IndexRevision, source.active_index_revision_id)
            if source.active_index_revision_id is not None and source.active_index_revision_id != index_revision.id
            else None
        )
        if previous_revision is not None:
            previous_revision.status = "retired"
            previous_revision.retired_at = now
            for old_chunk in self._session.scalars(
                select(MultimodalChunk).where(
                    MultimodalChunk.revision_id == previous_revision.id
                )
            ):
                old_chunk.status = "retired"
                old_chunk.retired_at = now
        if previous_index is not None:
            previous_index.status = "retired"
            previous_index.retired_at = now
            for old_point in self._session.scalars(
                select(VectorPointManifest).where(
                    VectorPointManifest.index_revision_id == previous_index.id
                )
            ):
                old_point.status = "retired"
        if previous_revision is not None or previous_index is not None:
            self._session.flush()

        operation = IndexOperation(
            id=str(uuid4()),
            command_id=command.command_id,
            source_id=source.id,
            revision_id=revision.id,
            index_revision_id=index_revision.id,
            operation_type="activate_revision",
            status="active",
            draft_hash=command_hash,
            parser_name=revision.parser_name,
            parser_version=revision.parser_version,
            started_at=now,
            finished_at=now,
        )
        self._session.add(operation)
        revision.status = "active"
        revision.validation_status = "passed"
        revision.activated_at = now
        index_revision.status = "active"
        index_revision.validation_status = "passed"
        index_revision.activated_at = now
        for chunk in chunks:
            chunk.status = "active"
        for point in self._session.scalars(
            select(VectorPointManifest).where(
                VectorPointManifest.index_revision_id == index_revision.id
            )
        ):
            point.status = "active"
            point.last_verified_at = now
        source.active_revision_id = revision.id
        source.active_index_revision_id = index_revision.id
        source.content_hash = revision.content_hash
        source.status = "ready"
        self._session.commit()
        return self._receipt(operation, replayed=False)

    def _search_active(self, request: SearchEvidence) -> EvidenceSearchResult:
        if not request.text.strip():
            return EvidenceSearchResult(hits=())
        lexical = LexicalQuery(request.text)
        limit = max(1, min(request.limit, 100))
        statement = (
            select(MultimodalChunk, Source, IndexRevision)
            .join(Source, Source.id == MultimodalChunk.source_id)
            .join(
                SourceRevision,
                and_(
                    SourceRevision.id == MultimodalChunk.revision_id,
                    SourceRevision.source_id == Source.id,
                ),
            )
            .join(
                IndexRevision,
                and_(
                    IndexRevision.id == Source.active_index_revision_id,
                    IndexRevision.revision_id == MultimodalChunk.revision_id,
                    IndexRevision.source_id == Source.id,
                ),
            )
            .where(
                Source.space_id == request.scope.space_id,
                Source.active_revision_id == MultimodalChunk.revision_id,
                Source.retired_at.is_(None),
                SourceRevision.status == "active",
                IndexRevision.status == "active",
                MultimodalChunk.status == "active",
            )
        )
        if request.scope.source_ids:
            statement = statement.where(Source.id.in_(request.scope.source_ids))

        scored: list[tuple[float, MultimodalChunk, Source, IndexRevision]] = []
        for chunk, source, index_revision in self._session.execute(statement):
            score = lexical.score(chunk.search_text or chunk.content_text)
            if score > 0:
                scored.append((score, chunk, source, index_revision))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_index, item[1].id))

        hits: list[EvidenceHit] = []
        for score, chunk, source, index_revision in scored[:limit]:
            if not chunk.content_hash:
                raise EvidenceIndexError(f"Active chunk {chunk.id} has no immutable content hash.")
            locator = self._locator(chunk.locator_json, chunk.id)
            hits.append(
                EvidenceHit(
                    evidence=ActiveEvidenceRef(
                        source_id=source.id,
                        revision_id=chunk.revision_id,
                        index_revision_id=index_revision.id,
                        chunk_id=chunk.id,
                        source_type=chunk.source_type,
                        modality=chunk.modality,
                        content_hash=chunk.content_hash,
                        locator=locator,
                        excerpt=chunk.content_text,
                    ),
                    score=score,
                )
            )
        return EvidenceSearchResult(hits=tuple(hits))

    def _search_pinned(self, request: SearchEvidence) -> EvidenceSearchResult:
        if not request.text.strip() or not request.scope.revision_ids:
            return EvidenceSearchResult(hits=())
        lexical = LexicalQuery(request.text)
        limit = max(1, min(request.limit, 100))
        statement = (
            select(MultimodalChunk, Source, IndexRevision)
            .join(Source, Source.id == MultimodalChunk.source_id)
            .join(
                SourceRevision,
                and_(
                    SourceRevision.id == MultimodalChunk.revision_id,
                    SourceRevision.source_id == Source.id,
                ),
            )
            .join(
                IndexRevision,
                and_(
                    IndexRevision.revision_id == MultimodalChunk.revision_id,
                    IndexRevision.source_id == Source.id,
                ),
            )
            .where(
                Source.space_id == request.scope.space_id,
                MultimodalChunk.revision_id.in_(request.scope.revision_ids),
                SourceRevision.status.in_(("active", "retired")),
                SourceRevision.validation_status == "passed",
                IndexRevision.status.in_(("active", "retired")),
                IndexRevision.validation_status == "passed",
                MultimodalChunk.status.in_(("active", "retired")),
            )
        )
        scored: list[tuple[float, MultimodalChunk, Source, IndexRevision]] = []
        for chunk, source, index_revision in self._session.execute(statement):
            score = lexical.score(chunk.search_text or chunk.content_text)
            if score > 0:
                scored.append((score, chunk, source, index_revision))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_index, item[1].id))

        hits: list[EvidenceHit] = []
        for score, chunk, source, index_revision in scored[:limit]:
            if not chunk.content_hash:
                raise EvidenceIndexError(f"Pinned chunk {chunk.id} has no immutable content hash.")
            hits.append(
                EvidenceHit(
                    evidence=PinnedEvidenceRef(
                        source_id=source.id,
                        revision_id=chunk.revision_id,
                        index_revision_id=index_revision.id,
                        chunk_id=chunk.id,
                        source_type=chunk.source_type,
                        modality=chunk.modality,
                        content_hash=chunk.content_hash,
                        locator=self._locator(chunk.locator_json, chunk.id),
                        excerpt=chunk.content_text,
                        currently_active=source.active_revision_id == chunk.revision_id,
                    ),
                    score=score,
                )
            )
        return EvidenceSearchResult(hits=tuple(hits))

    def _revision_view(self, revision_id: int) -> RevisionView:
        revision = self._session.get(SourceRevision, revision_id)
        if revision is None:
            raise EvidenceNotFoundError(f"Revision {revision_id} does not exist.")
        index_revision = self._session.scalar(
            select(IndexRevision).where(IndexRevision.revision_id == revision.id)
        )
        if index_revision is None:
            raise EvidenceNotFoundError(f"Revision {revision_id} has no index revision.")
        points = tuple(
            PointExpectation(
                point_id=point.point_id,
                payload_digest=point.payload_digest,
                status=point.status,
            )
            for point in self._session.scalars(
                select(VectorPointManifest)
                .where(VectorPointManifest.index_revision_id == index_revision.id)
                .order_by(VectorPointManifest.id)
            )
        )
        return RevisionView(
            revision_id=revision.id,
            revision_number=revision.revision_number,
            source_id=revision.source_id,
            status=revision.status,
            content_hash=revision.content_hash or "",
            chunk_count=revision.chunk_count,
            index_revision_id=index_revision.id,
            index_status=index_revision.status,
            manifest_digest=index_revision.manifest_digest or "",
            points=points,
            supersedes_revision_id=revision.supersedes_revision_id,
        )

    def _source_state(self, source_id: int) -> SourceState:
        source = self._session.get(Source, source_id)
        if source is None:
            raise EvidenceNotFoundError(f"Source {source_id} does not exist.")
        revision_ids = tuple(
            self._session.scalars(
                select(SourceRevision.id)
                .where(SourceRevision.source_id == source.id)
                .order_by(SourceRevision.revision_number)
            )
        )
        return SourceState(
            source_id=source.id,
            active_revision_id=source.active_revision_id,
            active_index_revision_id=source.active_index_revision_id,
            revision_ids=revision_ids,
        )

    def _evidence_chunk(self, revision_id: int, chunk_id: int) -> PinnedEvidenceRef:
        row = self._session.execute(
            select(MultimodalChunk, Source, SourceRevision, IndexRevision)
            .join(Source, Source.id == MultimodalChunk.source_id)
            .join(SourceRevision, SourceRevision.id == MultimodalChunk.revision_id)
            .join(
                IndexRevision,
                and_(
                    IndexRevision.revision_id == SourceRevision.id,
                    IndexRevision.source_id == Source.id,
                ),
            )
            .where(
                MultimodalChunk.id == chunk_id,
                MultimodalChunk.revision_id == revision_id,
                SourceRevision.status.in_(("active", "retired")),
                SourceRevision.validation_status == "passed",
                IndexRevision.status.in_(("active", "retired")),
                IndexRevision.validation_status == "passed",
                MultimodalChunk.status.in_(("active", "retired")),
            )
        ).one_or_none()
        if row is None:
            raise EvidenceNotFoundError(
                f"Chunk {chunk_id} is not readable evidence in revision {revision_id}."
            )
        chunk, source, _revision, index_revision = row
        return self._pinned_ref(chunk, source, index_revision)

    def _evidence_neighbors(self, query: GetEvidenceNeighbors) -> EvidenceWindow:
        if query.before < 0 or query.after < 0 or query.before > 3 or query.after > 3:
            raise InvalidEvidenceWindowError(
                "Evidence neighbor windows must use before/after values between 0 and 3."
            )
        center = self._evidence_chunk(query.revision_id, query.chunk_id)
        center_chunk = self._session.get(MultimodalChunk, center.chunk_id)
        if center_chunk is None:
            raise EvidenceNotFoundError(f"Chunk {center.chunk_id} does not exist.")
        source = self._session.get(Source, center.source_id)
        index_revision = self._session.get(IndexRevision, center.index_revision_id)
        if source is None or index_revision is None:
            raise EvidenceNotFoundError("Pinned evidence identity is incomplete.")
        lower = center_chunk.chunk_index - query.before
        upper = center_chunk.chunk_index + query.after
        chunks = self._session.scalars(
            select(MultimodalChunk)
            .where(
                MultimodalChunk.revision_id == query.revision_id,
                MultimodalChunk.chunk_index >= lower,
                MultimodalChunk.chunk_index <= upper,
                MultimodalChunk.status.in_(("active", "retired")),
            )
            .order_by(MultimodalChunk.chunk_index, MultimodalChunk.id)
        ).all()
        return EvidenceWindow(
            center_chunk_id=center.chunk_id,
            items=tuple(self._pinned_ref(chunk, source, index_revision) for chunk in chunks),
        )

    @staticmethod
    def _pinned_ref(
        chunk: MultimodalChunk,
        source: Source,
        index_revision: IndexRevision,
    ) -> PinnedEvidenceRef:
        if not chunk.content_hash:
            raise EvidenceIndexError(f"Pinned chunk {chunk.id} has no immutable content hash.")
        return PinnedEvidenceRef(
            source_id=source.id,
            revision_id=chunk.revision_id,
            index_revision_id=index_revision.id,
            chunk_id=chunk.id,
            source_type=chunk.source_type,
            modality=chunk.modality,
            content_hash=chunk.content_hash,
            locator=SqlEvidenceIndex._locator(chunk.locator_json, chunk.id),
            excerpt=chunk.content_text,
            currently_active=source.active_revision_id == chunk.revision_id,
        )

    @staticmethod
    def _vector_payload(
        source: Source,
        revision: SourceRevision,
        index_revision: IndexRevision,
        chunk: MultimodalChunk,
    ) -> dict[str, Any]:
        return {
            "space_id": source.space_id,
            "source_id": source.id,
            "revision_id": revision.id,
            "index_revision_id": index_revision.id,
            "chunk_id": chunk.id,
            "content_hash": chunk.content_hash,
            "source_type": chunk.source_type,
            "modality": chunk.modality,
            "chunk_index": chunk.chunk_index,
            "locator": json.loads(chunk.locator_json),
            "content": chunk.content_text,
        }

    @staticmethod
    def _valid_locator(raw_locator: str) -> bool:
        try:
            locator = json.loads(raw_locator)
        except (TypeError, json.JSONDecodeError):
            return False
        return isinstance(locator, dict) and bool(locator.get("kind"))

    @staticmethod
    def _validate_stage(command: StageRevision) -> None:
        draft = command.draft
        if not command.command_id.strip():
            raise InvalidRevisionDraftError("A stage command requires a stable command id.")
        if (
            len(draft.content_hash) != 64
            or draft.content_hash != draft.content_hash.lower()
            or any(character not in "0123456789abcdef" for character in draft.content_hash)
        ):
            raise InvalidRevisionDraftError("Revision content_hash must be a lowercase SHA-256 digest.")
        if not draft.index_version.strip() or not draft.collection_name.strip():
            raise InvalidRevisionDraftError("Revision index_version and collection_name are required.")
        if draft.embedding_dimensions is not None and draft.embedding_dimensions <= 0:
            raise InvalidRevisionDraftError("Embedding dimensions must be positive when supplied.")
        if not draft.chunks:
            raise InvalidRevisionDraftError("A revision requires at least one evidence chunk.")
        chunk_indices = [chunk.chunk_index for chunk in draft.chunks]
        if any(index < 0 for index in chunk_indices) or len(set(chunk_indices)) != len(chunk_indices):
            raise InvalidRevisionDraftError("Chunk indices must be unique non-negative integers.")
        for chunk in draft.chunks:
            if not chunk.modality.strip() or not chunk.content.strip():
                raise InvalidRevisionDraftError("Every chunk requires a modality and non-empty content.")
            if not isinstance(chunk.locator, dict) or not chunk.locator.get("kind"):
                raise InvalidRevisionDraftError("Every chunk requires a typed locator with a kind.")
        try:
            _canonical_json(draft.metadata)
            for chunk in draft.chunks:
                _canonical_json(chunk.locator)
        except (TypeError, ValueError) as exc:
            raise InvalidRevisionDraftError("Revision metadata and locators must be JSON serializable.") from exc

    @staticmethod
    def _locator(raw_locator: str, chunk_id: int) -> dict[str, Any]:
        try:
            locator = json.loads(raw_locator)
        except (TypeError, json.JSONDecodeError) as exc:
            raise EvidenceIndexError(f"Chunk {chunk_id} has an invalid locator.") from exc
        if not isinstance(locator, dict) or not locator.get("kind"):
            raise EvidenceIndexError(f"Chunk {chunk_id} has an invalid locator.")
        return locator

    @staticmethod
    def _receipt(operation: IndexOperation, *, replayed: bool) -> CommandReceipt:
        if operation.revision_id is None or operation.index_revision_id is None:
            raise EvidenceIndexError("A persisted lifecycle operation is missing its revision identity.")
        return CommandReceipt(
            command_id=operation.command_id,
            operation_id=operation.id,
            operation=operation.operation_type,
            status=operation.status,
            source_id=operation.source_id,
            revision_id=operation.revision_id,
            index_revision_id=operation.index_revision_id,
            replayed=replayed,
        )
