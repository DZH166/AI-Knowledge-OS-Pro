from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.modules.evidence_index import (
    ActivateRevision,
    ActivationInvariantError,
    CancelRevision,
    ChunkDraft,
    GetRevision,
    PointEmbedding,
    QdrantVectorAdapter,
    ReconcileIndex,
    RecordingVectorAdapter,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    UpsertRevisionVectors,
    VectorWriteError,
    VectorPointWrite,
    VerifiedPoint,
)


COLLECTION = "test-v5-saga"


def _source(db: Session, space: KnowledgeSpace) -> Source:
    source = Source(
        space_id=space.id,
        source_type="document",
        title="Saga source",
        file_size=128,
        status="uploaded",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _draft(source: Source, *contents: str) -> RevisionDraft:
    return RevisionDraft(
        source_id=source.id,
        content_hash=sha256("|".join(contents).encode()).hexdigest(),
        index_version="v5-saga-test",
        collection_name=COLLECTION,
        embedding_provider="recording",
        embedding_model="recording-3d",
        embedding_dimensions=3,
        embedding_fingerprint="recording::3d::v1",
        chunks=tuple(
            ChunkDraft(
                chunk_index=index,
                modality="text",
                content=content,
                locator={"kind": "pdf_page", "page": index + 1},
            )
            for index, content in enumerate(contents)
        ),
    )


class _InjectedProcessCrash(BaseException):
    pass


class _CrashAfterSuccessfulUpsert(RecordingVectorAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._crash_next_upsert = True

    def upsert_points(self, collection: str, points: Sequence[VectorPointWrite]) -> None:
        super().upsert_points(collection, points)
        if self._crash_next_upsert:
            self._crash_next_upsert = False
            raise _InjectedProcessCrash("process exited after Qdrant acknowledged the write")


class _CrashAfterQuantizedUpsert(_CrashAfterSuccessfulUpsert):
    def upsert_points(self, collection: str, points: Sequence[VectorPointWrite]) -> None:
        super().upsert_points(
            collection,
            tuple(
                VectorPointWrite(
                    point_id=point.point_id,
                    vector=tuple(round(value, 7) for value in point.vector),
                    payload=point.payload,
                )
                for point in points
            ),
        )


def test_stage_is_manifest_first_and_point_ids_are_deterministic(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    command = StageRevision(
        command_id="manifest-first-stage",
        draft=_draft(source, "manifest exists before vector write"),
    )

    staged = evidence_index.command(command)
    first_view = evidence_index.query(GetRevision(staged.revision_id))
    replay = evidence_index.command(command)
    replay_view = evidence_index.query(GetRevision(replay.revision_id))

    assert vectors.list_points(COLLECTION) == ()
    assert first_view.points == replay_view.points
    assert UUID(first_view.points[0].point_id).version == 5


def test_vector_upsert_builds_revision_scoped_payload_from_the_manifest(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-vector-upsert",
            draft=_draft(source, "payload must be revision scoped"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))

    stored = evidence_index.command(
        UpsertRevisionVectors(
            command_id="upsert-revision-vectors",
            revision_id=staged.revision_id,
            points=(PointEmbedding(point_id=revision.points[0].point_id, vector=(0.1, 0.2, 0.3)),),
        )
    )
    point = vectors.list_points(COLLECTION)[0]

    assert stored.status == "stored"
    assert {
        "space_id",
        "source_id",
        "revision_id",
        "index_revision_id",
        "chunk_id",
        "content_hash",
    }.issubset(point.payload)
    assert point.payload["space_id"] == knowledge_space.id
    assert point.payload["source_id"] == source.id
    assert point.payload["revision_id"] == staged.revision_id
    assert point.payload["index_revision_id"] == staged.index_revision_id
    assert point.payload["content_hash"] == sha256(b"payload must be revision scoped").hexdigest()


def test_replaying_an_upsert_after_a_post_write_crash_converges_to_stored(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = _CrashAfterSuccessfulUpsert()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-post-write-crash",
            draft=_draft(source, "the external write survives the process"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    command = UpsertRevisionVectors(
        command_id="replay-post-write-crash",
        revision_id=staged.revision_id,
        points=(
            PointEmbedding(
                point_id=revision.points[0].point_id,
                vector=(0.15, 0.25, 0.35),
            ),
        ),
    )

    with pytest.raises(_InjectedProcessCrash):
        evidence_index.command(command)

    db_session.rollback()
    restarted = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    replay = restarted.command(command)
    settled_replay = restarted.command(command)
    recovered = restarted.query(GetRevision(staged.revision_id))

    assert replay.operation_id != staged.operation_id
    assert replay.status == "stored"
    assert replay.replayed is True
    assert settled_replay.operation_id == replay.operation_id
    assert settled_replay.status == "stored"
    assert settled_replay.replayed is True
    assert recovered.points[0].status == "stored"
    assert len(vectors.list_points(COLLECTION)) == 1


def test_recovery_accepts_bounded_external_vector_quantization(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = _CrashAfterQuantizedUpsert()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-quantized-post-write-crash",
            draft=_draft(source, "Qdrant stores dense vectors as finite precision values"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    command = UpsertRevisionVectors(
        command_id="replay-quantized-post-write-crash",
        revision_id=staged.revision_id,
        points=(
            PointEmbedding(
                point_id=revision.points[0].point_id,
                vector=(0.123456789, 0.234567891, 0.345678912),
            ),
        ),
    )

    with pytest.raises(_InjectedProcessCrash):
        evidence_index.command(command)

    db_session.rollback()
    replay = SqlEvidenceIndex(db_session, vector_adapter=vectors).command(command)

    assert replay.status == "stored"
    assert replay.replayed is True


def test_replaying_an_interrupted_upsert_restores_a_missing_external_point(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = _CrashAfterSuccessfulUpsert()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-missing-recovery",
            draft=_draft(source, "the replay restores a missing point"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    point_id = revision.points[0].point_id
    command = UpsertRevisionVectors(
        command_id="replay-missing-post-crash-point",
        revision_id=staged.revision_id,
        points=(PointEmbedding(point_id=point_id, vector=(0.16, 0.26, 0.36)),),
    )

    with pytest.raises(_InjectedProcessCrash):
        evidence_index.command(command)

    db_session.rollback()
    vectors.delete_points(COLLECTION, (point_id,))
    restarted = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    replay = restarted.command(command)

    assert replay.status == "stored"
    assert replay.replayed is True
    assert [point.point_id for point in vectors.list_points(COLLECTION)] == [point_id]
    assert restarted.query(GetRevision(staged.revision_id)).points[0].status == "stored"


def test_replaying_an_interrupted_upsert_rewrites_a_mismatched_payload(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = _CrashAfterSuccessfulUpsert()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-payload-recovery",
            draft=_draft(source, "the replay restores the canonical payload"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    point_id = revision.points[0].point_id
    command = UpsertRevisionVectors(
        command_id="replay-mismatched-post-crash-payload",
        revision_id=staged.revision_id,
        points=(PointEmbedding(point_id=point_id, vector=(0.17, 0.27, 0.37)),),
    )

    with pytest.raises(_InjectedProcessCrash):
        evidence_index.command(command)

    db_session.rollback()
    poisoned = vectors.list_points(COLLECTION)[0]
    vectors.upsert_points(
        COLLECTION,
        (
            VectorPointWrite(
                point_id=poisoned.point_id,
                vector=poisoned.vector,
                payload={**poisoned.payload, "revision_id": 999_999},
            ),
        ),
    )
    restarted = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    replay = restarted.command(command)
    recovered = vectors.list_points(COLLECTION)[0]

    assert replay.status == "stored"
    assert replay.replayed is True
    assert recovered.payload["revision_id"] == staged.revision_id
    assert restarted.query(GetRevision(staged.revision_id)).points[0].status == "stored"


def test_reconciler_preserves_an_expected_point_owned_by_an_interrupted_upsert(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = _CrashAfterSuccessfulUpsert()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-reconciling-interrupted-upsert",
            draft=_draft(source, "reconciliation must preserve this acknowledged point"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    point_id = revision.points[0].point_id
    command = UpsertRevisionVectors(
        command_id="interrupted-upsert-before-reconciliation",
        revision_id=staged.revision_id,
        points=(PointEmbedding(point_id=point_id, vector=(0.18, 0.28, 0.38)),),
    )

    with pytest.raises(_InjectedProcessCrash):
        evidence_index.command(command)

    db_session.rollback()
    restarted = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    report = restarted.command(
        ReconcileIndex(
            command_id="protect-interrupted-upsert-point",
            collection_name=COLLECTION,
            apply=True,
        )
    )

    assert report.issues == ()
    assert report.repairs == ()
    assert [point.point_id for point in vectors.list_points(COLLECTION)] == [point_id]
    assert restarted.command(command).status == "stored"


def test_reconciler_classifies_interrupted_upsert_missing_and_mismatch_without_orphans(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = _CrashAfterSuccessfulUpsert()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-reconciling-interrupted-divergence",
            draft=_draft(source, "missing after crash", "mismatched after crash"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    missing_id, mismatch_id = (point.point_id for point in revision.points)
    command = UpsertRevisionVectors(
        command_id="interrupted-upsert-with-divergence",
        revision_id=staged.revision_id,
        points=tuple(
            PointEmbedding(point_id=point.point_id, vector=(0.19, 0.29, 0.39))
            for point in revision.points
        ),
    )

    with pytest.raises(_InjectedProcessCrash):
        evidence_index.command(command)

    db_session.rollback()
    vectors.delete_points(COLLECTION, (missing_id,))
    mismatch = {point.point_id: point for point in vectors.list_points(COLLECTION)}[mismatch_id]
    vectors.upsert_points(
        COLLECTION,
        (
            VectorPointWrite(
                point_id=mismatch.point_id,
                vector=mismatch.vector,
                payload={**mismatch.payload, "chunk_id": 999_999},
            ),
        ),
    )
    restarted = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    report = restarted.command(
        ReconcileIndex(
            command_id="reconcile-interrupted-divergence",
            collection_name=COLLECTION,
            apply=True,
        )
    )

    assert {(issue.kind, issue.point_id) for issue in report.issues} == {
        ("missing", missing_id),
        ("payload_mismatch", mismatch_id),
    }
    assert {(repair.action, repair.point_id) for repair in report.repairs} == {
        ("marked_missing", missing_id),
        ("rewrote_payload", mismatch_id),
    }
    assert restarted.command(command).status == "stored"
    assert {point.point_id for point in vectors.list_points(COLLECTION)} == {
        missing_id,
        mismatch_id,
    }
    assert {point.status for point in restarted.query(GetRevision(staged.revision_id)).points} == {
        "stored"
    }


def test_cancelling_after_upsert_compensates_every_manifest_point(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-cancel",
            draft=_draft(source, "cancelled point one", "cancelled point two"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    evidence_index.command(
        UpsertRevisionVectors(
            command_id="upsert-before-cancel",
            revision_id=staged.revision_id,
            points=tuple(
                PointEmbedding(point_id=point.point_id, vector=(0.2, 0.3, 0.4))
                for point in revision.points
            ),
        )
    )
    command = CancelRevision(
        command_id="cancel-after-upsert",
        revision_id=staged.revision_id,
        reason="user_cancelled",
    )

    cancelled = evidence_index.command(command)
    replay = evidence_index.command(command)
    cancelled_view = evidence_index.query(GetRevision(staged.revision_id))

    assert vectors.list_points(COLLECTION) == ()
    assert cancelled.status == "cancelled"
    assert replay.operation_id == cancelled.operation_id
    assert replay.replayed is True
    assert (cancelled_view.status, cancelled_view.index_status) == ("cancelled", "cancelled")


def test_failure_after_vector_write_is_compensated_and_retryable(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    vectors.fail_next_upsert_after_write(RuntimeError("recording write acknowledgement failed"))
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-uncertain-write",
            draft=_draft(source, "uncertain external write"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    points = tuple(
        PointEmbedding(point_id=point.point_id, vector=(0.4, 0.5, 0.6))
        for point in revision.points
    )

    with pytest.raises(VectorWriteError):
        evidence_index.command(
            UpsertRevisionVectors(
                command_id="uncertain-upsert-attempt",
                revision_id=staged.revision_id,
                points=points,
            )
        )

    assert vectors.list_points(COLLECTION) == ()
    retry = evidence_index.command(
        UpsertRevisionVectors(
            command_id="retry-after-compensation",
            revision_id=staged.revision_id,
            points=points,
        )
    )
    assert retry.status == "stored"
    assert len(vectors.list_points(COLLECTION)) == 1


def test_revision_cannot_activate_before_manifest_points_are_stored(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-without-vector-upsert",
            draft=_draft(source, "not stored yet"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))

    with pytest.raises(ActivationInvariantError):
        evidence_index.command(
            ActivateRevision(
                command_id="activate-before-vector-upsert",
                revision_id=staged.revision_id,
                verified_points=tuple(
                    VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                    for point in revision.points
                ),
            )
        )

    assert evidence_index.query(GetRevision(staged.revision_id)).status == "staging"
    assert vectors.list_points(COLLECTION) == ()


def test_reconciler_finishes_compensation_when_vector_delete_also_failed(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    vectors.fail_next_upsert_after_write(RuntimeError("upsert acknowledgement failed"))
    vectors.fail_next_delete(RuntimeError("compensation delete failed"))
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-double-failure",
            draft=_draft(source, "cleanup must be reconciled"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))

    with pytest.raises(VectorWriteError):
        evidence_index.command(
            UpsertRevisionVectors(
                command_id="double-failure-upsert",
                revision_id=staged.revision_id,
                points=(
                    PointEmbedding(
                        point_id=revision.points[0].point_id,
                        vector=(0.6, 0.7, 0.8),
                    ),
                ),
            )
        )

    assert len(vectors.list_points(COLLECTION)) == 1
    report = evidence_index.command(
        ReconcileIndex(
            command_id="apply-pending-compensation",
            collection_name=COLLECTION,
            apply=True,
        )
    )
    assert {(issue.kind, issue.point_id) for issue in report.issues} == {
        ("orphan", revision.points[0].point_id)
    }
    assert vectors.list_points(COLLECTION) == ()


def test_reconciler_finishes_a_cancel_when_vector_delete_failed(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    vectors = RecordingVectorAdapter()
    evidence_index = SqlEvidenceIndex(db_session, vector_adapter=vectors)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-cancel-delete-failure",
            draft=_draft(source, "cancel cleanup pending"),
        )
    )
    revision = evidence_index.query(GetRevision(staged.revision_id))
    evidence_index.command(
        UpsertRevisionVectors(
            command_id="upsert-before-cancel-delete-failure",
            revision_id=staged.revision_id,
            points=(
                PointEmbedding(
                    point_id=revision.points[0].point_id,
                    vector=(0.7, 0.8, 0.9),
                ),
            ),
        )
    )
    vectors.fail_next_delete(RuntimeError("cancel delete unavailable"))

    with pytest.raises(VectorWriteError):
        evidence_index.command(
            CancelRevision(
                command_id="cancel-with-delete-failure",
                revision_id=staged.revision_id,
                reason="user_cancelled",
            )
        )

    cancelled = evidence_index.query(GetRevision(staged.revision_id))
    assert (cancelled.status, cancelled.index_status) == ("cancelled", "cancelled")
    assert cancelled.points[0].status == "cleanup_pending"
    assert len(vectors.list_points(COLLECTION)) == 1

    evidence_index.command(
        ReconcileIndex(
            command_id="repair-cancel-delete",
            collection_name=COLLECTION,
            apply=True,
        )
    )
    reconciled = evidence_index.query(GetRevision(staged.revision_id))
    assert vectors.list_points(COLLECTION) == ()
    assert reconciled.points[0].status == "deleted"


class _RecordingQdrantClient:
    def __init__(self) -> None:
        self.points: dict[str, SimpleNamespace] = {}
        self.wait_values: list[bool] = []

    def upsert(self, *, collection_name: str, points: list[object], wait: bool) -> None:
        assert collection_name == COLLECTION
        self.wait_values.append(wait)
        for point in points:
            point_id = str(point.id)
            self.points[point_id] = SimpleNamespace(
                id=point_id,
                vector=point.vector,
                payload=point.payload,
            )

    def scroll(
        self,
        *,
        collection_name: str,
        limit: int,
        offset: object,
        with_payload: bool,
        with_vectors: bool,
    ) -> tuple[list[SimpleNamespace], None]:
        assert collection_name == COLLECTION
        assert limit > 0
        assert offset is None
        assert with_payload is True
        assert with_vectors is True
        return list(self.points.values()), None

    def delete(self, *, collection_name: str, points_selector: object, wait: bool) -> None:
        assert collection_name == COLLECTION
        self.wait_values.append(wait)
        for point_id in points_selector.points:
            self.points.pop(str(point_id), None)


def test_qdrant_adapter_satisfies_the_vector_port_without_a_network_connection() -> None:
    client = _RecordingQdrantClient()
    adapter = QdrantVectorAdapter(client, scroll_batch_size=17)
    point_id = "1101418a-6d25-5bce-9140-597582628ded"
    write = VectorPointWrite(
        point_id=point_id,
        vector=(0.1, 0.2, 0.3),
        payload={"revision_id": 7, "content_hash": "a" * 64},
    )

    adapter.upsert_points(COLLECTION, (write,))
    stored = adapter.list_points(COLLECTION)
    adapter.delete_points(COLLECTION, (point_id,))

    assert stored[0].point_id == point_id
    assert stored[0].vector == write.vector
    assert stored[0].payload == write.payload
    assert adapter.list_points(COLLECTION) == ()
    assert client.wait_values == [True, True]
