from __future__ import annotations

from hashlib import sha256

from sqlalchemy.orm import Session

from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.modules.evidence_index import (
    ChunkDraft,
    GetRevision,
    PointEmbedding,
    ReconcileIndex,
    RecordingVectorAdapter,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    UpsertRevisionVectors,
    VectorPointWrite,
)


COLLECTION = "test-v5-reconciler"


def _source(db: Session, space: KnowledgeSpace) -> Source:
    source = Source(
        space_id=space.id,
        source_type="document",
        title="Reconciler source",
        file_size=256,
        status="uploaded",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _stored_revision(
    db: Session,
    space: KnowledgeSpace,
    vectors: RecordingVectorAdapter,
) -> tuple[SqlEvidenceIndex, object]:
    source = _source(db, space)
    evidence_index = SqlEvidenceIndex(db, vector_adapter=vectors)
    contents = ("missing point", "mismatched payload", "healthy point")
    staged = evidence_index.command(
        StageRevision(
            command_id="reconcile-stage",
            draft=RevisionDraft(
                source_id=source.id,
                content_hash=sha256("|".join(contents).encode()).hexdigest(),
                index_version="v5-reconcile-test",
                collection_name=COLLECTION,
                embedding_provider="recording",
                embedding_model="recording-2d",
                embedding_dimensions=2,
                embedding_fingerprint="recording::2d::v1",
                chunks=tuple(
                    ChunkDraft(
                        chunk_index=index,
                        modality="text",
                        content=content,
                        locator={"kind": "pdf_page", "page": index + 1},
                    )
                    for index, content in enumerate(contents)
                ),
            ),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    evidence_index.command(
        UpsertRevisionVectors(
            command_id="reconcile-upsert",
            revision_id=staged.revision_id,
            points=tuple(
                PointEmbedding(point_id=point.point_id, vector=(0.5, 0.6))
                for point in revision.points
            ),
        )
    )
    return evidence_index, revision


def test_reconcile_dry_run_reports_orphan_missing_and_payload_mismatch_without_mutating(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    vectors = RecordingVectorAdapter()
    evidence_index, revision = _stored_revision(db_session, knowledge_space, vectors)
    missing_id, mismatch_id, _healthy_id = (point.point_id for point in revision.points)
    vectors.delete_points(COLLECTION, (missing_id,))
    mismatch = {point.point_id: point for point in vectors.list_points(COLLECTION)}[mismatch_id]
    vectors.upsert_points(
        COLLECTION,
        (
            VectorPointWrite(
                point_id=mismatch.point_id,
                vector=mismatch.vector,
                payload={**mismatch.payload, "revision_id": 999_999},
            ),
            VectorPointWrite(
                point_id="orphan-point",
                vector=(0.7, 0.8),
                payload={"space_id": knowledge_space.id, "source_id": 999_999},
            ),
        ),
    )

    report = evidence_index.command(
        ReconcileIndex(command_id="reconcile-dry-run", collection_name=COLLECTION)
    )
    actual_after = {point.point_id: point for point in vectors.list_points(COLLECTION)}

    assert report.applied is False
    assert {(issue.kind, issue.point_id) for issue in report.issues} == {
        ("missing", missing_id),
        ("payload_mismatch", mismatch_id),
        ("orphan", "orphan-point"),
    }
    assert "orphan-point" in actual_after
    assert actual_after[mismatch_id].payload["revision_id"] == 999_999
    assert missing_id not in actual_after


def test_reconcile_apply_repairs_safe_issues_and_marks_missing_for_reindex(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    vectors = RecordingVectorAdapter()
    evidence_index, revision = _stored_revision(db_session, knowledge_space, vectors)
    missing_id, mismatch_id, _healthy_id = (point.point_id for point in revision.points)
    vectors.delete_points(COLLECTION, (missing_id,))
    mismatch = {point.point_id: point for point in vectors.list_points(COLLECTION)}[mismatch_id]
    vectors.upsert_points(
        COLLECTION,
        (
            VectorPointWrite(
                point_id=mismatch.point_id,
                vector=mismatch.vector,
                payload={**mismatch.payload, "index_revision_id": 999_999},
            ),
            VectorPointWrite(
                point_id="orphan-to-delete",
                vector=(0.8, 0.9),
                payload={"space_id": knowledge_space.id, "source_id": 999_999},
            ),
        ),
    )

    report = evidence_index.command(
        ReconcileIndex(
            command_id="reconcile-apply",
            collection_name=COLLECTION,
            apply=True,
        )
    )
    actual_after = {point.point_id: point for point in vectors.list_points(COLLECTION)}
    revision_after = evidence_index.query(GetRevision(revision.revision_id))
    point_statuses = {point.point_id: point.status for point in revision_after.points}

    assert report.applied is True
    assert report.repair_count == 3
    assert {(repair.action, repair.point_id) for repair in report.repairs} == {
        ("deleted_orphan", "orphan-to-delete"),
        ("rewrote_payload", mismatch_id),
        ("marked_missing", missing_id),
    }
    assert "orphan-to-delete" not in actual_after
    assert actual_after[mismatch_id].payload["index_revision_id"] == revision.index_revision_id
    assert actual_after[mismatch_id].vector == mismatch.vector
    assert missing_id not in actual_after
    assert point_statuses[missing_id] == "missing"
