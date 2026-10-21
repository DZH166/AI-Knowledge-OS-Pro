from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence_index import IndexOperation, VectorPointManifest
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.modules.evidence_index.contracts import (
    ReconcileIndex,
    ReconciliationIssue,
    ReconciliationRepair,
    ReconciliationReport,
)
from app.modules.evidence_index.vector_adapter import (
    VectorIndexPort,
    VectorPointState,
    VectorPointWrite,
)


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class _ExpectedPoint:
    manifest: VectorPointManifest
    index_revision: IndexRevision
    payload: dict[str, Any]


class IndexReconciler:
    """Internal implementation behind EvidenceIndex.command(ReconcileIndex)."""

    def __init__(self, session: Session, vector_adapter: VectorIndexPort) -> None:
        self._session = session
        self._vector_adapter = vector_adapter

    def run(self, command: ReconcileIndex) -> ReconciliationReport:
        expected = self._expected_points(command.collection_name)
        actual = {
            point.point_id: point
            for point in self._vector_adapter.list_points(command.collection_name)
        }
        issues: list[ReconciliationIssue] = []

        for point_id, point in actual.items():
            if point_id not in expected:
                issues.append(self._orphan_issue(command.collection_name, point))

        for point_id, expected_point in expected.items():
            actual_point = actual.get(point_id)
            if actual_point is None:
                issues.append(self._missing_issue(command.collection_name, expected_point))
                continue
            expected_digest = _digest(expected_point.payload)
            actual_digest = _digest(dict(actual_point.payload))
            if (
                expected_point.manifest.payload_digest != expected_digest
                or actual_digest != expected_digest
            ):
                issues.append(
                    self._mismatch_issue(
                        command.collection_name,
                        expected_point,
                        actual_digest=actual_digest,
                        expected_digest=expected_digest,
                    )
                )

        issues.sort(key=lambda issue: (issue.kind, issue.point_id))
        repairs = self._apply(command, issues, expected, actual) if command.apply else ()
        return ReconciliationReport(
            command_id=command.command_id,
            collection_name=command.collection_name,
            applied=command.apply,
            issues=tuple(issues),
            repairs=repairs,
            repair_count=len(repairs),
        )

    def _expected_points(self, collection_name: str) -> dict[str, _ExpectedPoint]:
        interrupted_upserts = {
            (revision_id, index_revision_id)
            for revision_id, index_revision_id in self._session.execute(
                select(IndexOperation.revision_id, IndexOperation.index_revision_id).where(
                    IndexOperation.operation_type == "upsert_revision_vectors",
                    IndexOperation.status == "upserting",
                )
            )
            if revision_id is not None and index_revision_id is not None
        }
        rows = self._session.execute(
            select(
                VectorPointManifest,
                MultimodalChunk,
                Source,
                SourceRevision,
                IndexRevision,
            )
            .join(MultimodalChunk, MultimodalChunk.id == VectorPointManifest.chunk_id)
            .join(Source, Source.id == VectorPointManifest.source_id)
            .join(SourceRevision, SourceRevision.id == VectorPointManifest.revision_id)
            .join(IndexRevision, IndexRevision.id == VectorPointManifest.index_revision_id)
            .where(
                VectorPointManifest.collection_name == collection_name,
                VectorPointManifest.status.in_(("expected", "stored", "active", "missing")),
            )
        )
        expected: dict[str, _ExpectedPoint] = {}
        for manifest, chunk, source, revision, index_revision in rows:
            if (
                manifest.status == "expected"
                and (manifest.revision_id, manifest.index_revision_id) not in interrupted_upserts
            ):
                continue
            expected[manifest.point_id] = _ExpectedPoint(
                manifest=manifest,
                index_revision=index_revision,
                payload={
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
                },
            )
        return expected

    def _apply(
        self,
        command: ReconcileIndex,
        issues: list[ReconciliationIssue],
        expected: dict[str, _ExpectedPoint],
        actual: dict[str, VectorPointState],
    ) -> tuple[ReconciliationRepair, ...]:
        orphan_ids = tuple(issue.point_id for issue in issues if issue.kind == "orphan")
        if orphan_ids:
            self._vector_adapter.delete_points(command.collection_name, orphan_ids)

        mismatch_writes: list[VectorPointWrite] = []
        for issue in issues:
            if issue.kind != "payload_mismatch":
                continue
            actual_point = actual[issue.point_id]
            mismatch_writes.append(
                VectorPointWrite(
                    point_id=issue.point_id,
                    vector=actual_point.vector,
                    payload=expected[issue.point_id].payload,
                )
            )
        if mismatch_writes:
            self._vector_adapter.upsert_points(command.collection_name, mismatch_writes)

        now = datetime.now(timezone.utc)
        repairs: list[ReconciliationRepair] = []
        for issue in issues:
            if issue.kind == "orphan":
                if issue.manifest_id is not None:
                    manifest = self._session.get(VectorPointManifest, issue.manifest_id)
                    if manifest is not None:
                        revision = self._session.get(SourceRevision, manifest.revision_id)
                        manifest.status = (
                            "deleted"
                            if revision is not None and revision.status == "cancelled"
                            else "expected"
                        )
                        manifest.last_verified_at = now
                repairs.append(ReconciliationRepair(action="deleted_orphan", point_id=issue.point_id))
                continue
            expected_point = expected[issue.point_id]
            if issue.kind == "payload_mismatch":
                expected_point.manifest.payload_digest = _digest(expected_point.payload)
                expected_point.manifest.status = (
                    "active" if expected_point.index_revision.status == "active" else "stored"
                )
                expected_point.manifest.last_verified_at = now
                repairs.append(ReconciliationRepair(action="rewrote_payload", point_id=issue.point_id))
                continue
            expected_point.manifest.status = "missing"
            expected_point.manifest.last_verified_at = now
            expected_point.index_revision.validation_status = "failed"
            repairs.append(ReconciliationRepair(action="marked_missing", point_id=issue.point_id))

        self._session.commit()
        return tuple(repairs)

    def _orphan_issue(self, collection_name: str, point: VectorPointState) -> ReconciliationIssue:
        payload = dict(point.payload)
        manifest = self._session.scalar(
            select(VectorPointManifest).where(
                VectorPointManifest.collection_name == collection_name,
                VectorPointManifest.point_id == point.point_id,
            )
        )
        return ReconciliationIssue(
            kind="orphan",
            collection_name=collection_name,
            point_id=point.point_id,
            manifest_id=manifest.id if manifest is not None else None,
            source_id=manifest.source_id if manifest is not None else payload.get("source_id"),
            revision_id=manifest.revision_id if manifest is not None else payload.get("revision_id"),
            index_revision_id=(
                manifest.index_revision_id
                if manifest is not None
                else payload.get("index_revision_id")
            ),
            actual_payload_digest=_digest(payload),
        )

    @staticmethod
    def _missing_issue(
        collection_name: str,
        expected: _ExpectedPoint,
    ) -> ReconciliationIssue:
        manifest = expected.manifest
        return ReconciliationIssue(
            kind="missing",
            collection_name=collection_name,
            point_id=manifest.point_id,
            manifest_id=manifest.id,
            source_id=manifest.source_id,
            revision_id=manifest.revision_id,
            index_revision_id=manifest.index_revision_id,
            expected_payload_digest=_digest(expected.payload),
        )

    @staticmethod
    def _mismatch_issue(
        collection_name: str,
        expected: _ExpectedPoint,
        *,
        actual_digest: str,
        expected_digest: str,
    ) -> ReconciliationIssue:
        manifest = expected.manifest
        return ReconciliationIssue(
            kind="payload_mismatch",
            collection_name=collection_name,
            point_id=manifest.point_id,
            manifest_id=manifest.id,
            source_id=manifest.source_id,
            revision_id=manifest.revision_id,
            index_revision_id=manifest.index_revision_id,
            expected_payload_digest=expected_digest,
            actual_payload_digest=actual_digest,
        )
