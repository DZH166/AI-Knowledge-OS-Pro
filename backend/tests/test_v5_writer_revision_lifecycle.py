from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.errors import DuplicateDocumentError
from app.models.chunk import Chunk
from app.models.source import CitationLocator, IndexRevision, MultimodalChunk, Source, SourceRevision
from app.modules.evidence_index import (
    ActiveScope,
    PinnedScope,
    ReconcileIndex,
    SearchEvidence,
    SqlEvidenceIndex,
    VectorWriteError,
)
from app.services.code_repository_service import CodeRepositoryService
from app.services.ingestion_service import DocumentIngestionService, LegacyVectorStoreEvidenceAdapter


def test_document_reprocess_reuses_source_and_only_exposes_new_active_revision(
    db_session,
    knowledge_space,
    fake_embedding,
    fake_vector_store,
    upload_factory,
) -> None:
    service = DocumentIngestionService(
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )
    document, _job = service.ingest_upload(
        db_session,
        knowledge_space.id,
        upload_factory(content="# RAG\nRAG 是检索增强生成。\n\ncanonical revision identity"),
    )

    source = db_session.scalar(select(Source).where(Source.document_id == document.id))
    assert source is not None
    first_revision_id = source.active_revision_id
    first_index_revision_id = source.active_index_revision_id
    assert first_revision_id is not None
    assert first_index_revision_id is not None

    _document, reprocess_job = service.reparse_document(db_session, document.id)
    db_session.expire_all()

    source = db_session.scalar(select(Source).where(Source.document_id == document.id))
    assert source is not None
    revisions = list(
        db_session.scalars(
            select(SourceRevision)
            .where(SourceRevision.source_id == source.id)
            .order_by(SourceRevision.revision_number)
        )
    )
    indexes = list(
        db_session.scalars(
            select(IndexRevision).where(IndexRevision.source_id == source.id).order_by(IndexRevision.id)
        )
    )
    active_chunks = list(
        db_session.scalars(
            select(MultimodalChunk)
            .where(MultimodalChunk.source_id == source.id, MultimodalChunk.status == "active")
            .order_by(MultimodalChunk.chunk_index)
        )
    )
    retired_chunks = list(
        db_session.scalars(
            select(MultimodalChunk).where(
                MultimodalChunk.source_id == source.id,
                MultimodalChunk.revision_id == first_revision_id,
            )
        )
    )
    legacy_chunks = list(
        db_session.scalars(select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index))
    )

    assert reprocess_job.status == "completed"
    assert len(revisions) == 2
    assert [revision.status for revision in revisions] == ["retired", "active"]
    assert revisions[0].retired_at is not None
    assert source.active_revision_id == revisions[1].id
    assert source.latest_revision_id == revisions[1].id
    assert len([index for index in indexes if index.status == "active"]) == 1
    assert indexes[0].id == first_index_revision_id
    assert indexes[0].status == "retired"
    assert source.active_index_revision_id == indexes[1].id
    assert active_chunks
    assert all(chunk.revision_id == revisions[1].id for chunk in active_chunks)
    assert all(chunk.content_hash and chunk.qdrant_point_id for chunk in active_chunks)
    assert all(chunk.status == "retired" and chunk.retired_at is not None for chunk in retired_chunks)
    assert {chunk.legacy_chunk_id for chunk in active_chunks} == {chunk.id for chunk in legacy_chunks}

    active_result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text="canonical revision identity",
            scope=ActiveScope(space_id=knowledge_space.id, source_ids=(source.id,)),
        )
    )
    pinned_result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text="canonical revision identity",
            scope=PinnedScope(space_id=knowledge_space.id, revision_ids=(first_revision_id,)),
        )
    )
    assert active_result.hits
    assert {hit.evidence.revision_id for hit in active_result.hits} == {revisions[1].id}
    assert pinned_result.hits
    assert all(not hit.evidence.currently_active for hit in pinned_result.hits)

    active_point_ids = {chunk.qdrant_point_id for chunk in active_chunks}
    active_payloads = [
        fake_vector_store.points[point_id]["payload"]
        for point_id in active_point_ids
        if point_id is not None
    ]
    assert active_payloads
    assert all(
        payload["source_id"] == source.id
        and payload["revision_id"] == source.active_revision_id
        and payload["index_revision_id"] == source.active_index_revision_id
        and len(payload["content_hash"]) == 64
        for payload in active_payloads
    )


def test_document_reprocess_failure_keeps_previous_revision_query_visible(
    db_session,
    knowledge_space,
    fake_embedding,
    fake_vector_store,
    upload_factory,
    monkeypatch,
) -> None:
    service = DocumentIngestionService(
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )
    document, _job = service.ingest_upload(
        db_session,
        knowledge_space.id,
        upload_factory(content="# Stable\nprevious active evidence survives writer failure"),
    )
    source = db_session.scalar(select(Source).where(Source.document_id == document.id))
    assert source is not None
    previous_revision_id = source.active_revision_id
    previous_index_revision_id = source.active_index_revision_id
    previous_point_ids = set(fake_vector_store.points)

    def fail_upsert(*_args, **_kwargs) -> None:
        raise RuntimeError("simulated vector write failure")

    monkeypatch.setattr(fake_vector_store, "upsert_chunks", fail_upsert)
    with pytest.raises(VectorWriteError, match="manifest was committed"):
        service.reparse_document(db_session, document.id)
    db_session.expire_all()

    source = db_session.scalar(select(Source).where(Source.document_id == document.id))
    assert source is not None
    revisions = list(
        db_session.scalars(
            select(SourceRevision)
            .where(SourceRevision.source_id == source.id)
            .order_by(SourceRevision.revision_number)
        )
    )
    assert source.active_revision_id == previous_revision_id
    assert source.active_index_revision_id == previous_index_revision_id
    assert [revision.status for revision in revisions] == ["active", "cancelled"]
    assert previous_point_ids.issubset(fake_vector_store.points)

    active_result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text="survives writer failure",
            scope=ActiveScope(space_id=knowledge_space.id, source_ids=(source.id,)),
        )
    )
    assert active_result.hits
    assert {hit.evidence.revision_id for hit in active_result.hits} == {previous_revision_id}


def test_code_repository_reingest_creates_revision_on_same_source_and_retires_old_evidence(
    db_session,
    knowledge_space,
    tmp_path,
    fake_embedding,
    fake_vector_store,
) -> None:
    repository = tmp_path / "versioned-repository"
    repository.mkdir()
    code_file = repository / "main.py"
    code_file.write_text(
        "def obsolete_marker():\n    return 'obsolete evidence phrase'\n",
        encoding="utf-8",
    )
    service = CodeRepositoryService(
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )

    first_source, _file_count, _skipped = service.ingest_local_repository(
        db_session,
        space_id=knowledge_space.id,
        local_path=str(repository),
    )
    first_source_id = first_source.id
    first_revision_id = first_source.active_revision_id
    assert first_revision_id is not None

    code_file.write_text(
        "def canonical_marker():\n    return 'brand new canonical evidence phrase'\n",
        encoding="utf-8",
    )
    second_source, _file_count, _skipped = service.ingest_local_repository(
        db_session,
        space_id=knowledge_space.id,
        local_path=str(repository),
    )
    db_session.expire_all()

    source = db_session.get(Source, first_source_id)
    assert source is not None
    revisions = list(
        db_session.scalars(
            select(SourceRevision)
            .where(SourceRevision.source_id == source.id)
            .order_by(SourceRevision.revision_number)
        )
    )
    indexes = list(
        db_session.scalars(
            select(IndexRevision).where(IndexRevision.source_id == source.id).order_by(IndexRevision.id)
        )
    )
    all_chunks = list(
        db_session.scalars(
            select(MultimodalChunk)
            .where(MultimodalChunk.source_id == source.id)
            .order_by(MultimodalChunk.revision_id, MultimodalChunk.chunk_index)
        )
    )
    active_chunks = [chunk for chunk in all_chunks if chunk.status == "active"]

    assert second_source.id == first_source_id
    assert db_session.scalar(
        select(Source).where(
            Source.space_id == knowledge_space.id,
            Source.source_type == "code_repository",
            Source.storage_path == str(repository.resolve()),
        )
    ).id == first_source_id
    assert len(revisions) == 2
    assert [revision.status for revision in revisions] == ["retired", "active"]
    assert revisions[0].retired_at is not None
    assert source.active_revision_id == revisions[1].id
    assert source.latest_revision_id == revisions[1].id
    assert len([index for index in indexes if index.status == "active"]) == 1
    assert source.active_index_revision_id == indexes[1].id
    assert indexes[0].status == "retired"
    assert active_chunks
    assert all(chunk.revision_id == source.active_revision_id for chunk in active_chunks)
    assert all(chunk.content_hash and chunk.qdrant_point_id for chunk in active_chunks)
    assert all(
        chunk.status == "retired" and chunk.retired_at is not None
        for chunk in all_chunks
        if chunk.revision_id == first_revision_id
    )
    assert db_session.query(CitationLocator).filter_by(source_id=source.id).count() == len(all_chunks)

    evidence_index = SqlEvidenceIndex(db_session)
    active_old = evidence_index.search(
        SearchEvidence(
            text="obsolete_marker",
            scope=ActiveScope(space_id=knowledge_space.id, source_ids=(source.id,)),
        )
    )
    active_new = evidence_index.search(
        SearchEvidence(
            text="canonical_marker",
            scope=ActiveScope(space_id=knowledge_space.id, source_ids=(source.id,)),
        )
    )
    pinned_old = evidence_index.search(
        SearchEvidence(
            text="obsolete_marker",
            scope=PinnedScope(space_id=knowledge_space.id, revision_ids=(first_revision_id,)),
        )
    )
    assert not active_old.hits
    assert active_new.hits
    assert {hit.evidence.revision_id for hit in active_new.hits} == {source.active_revision_id}
    assert pinned_old.hits
    assert all(not hit.evidence.currently_active for hit in pinned_old.hits)

    active_payloads = [
        fake_vector_store.points[chunk.qdrant_point_id]["payload"]
        for chunk in active_chunks
        if chunk.qdrant_point_id is not None
    ]
    assert active_payloads
    assert all(
        payload["revision_id"] == source.active_revision_id
        and payload["index_revision_id"] == source.active_index_revision_id
        and payload["content_hash"]
        and payload["locator"]["file_path"] == "main.py"
        for payload in active_payloads
    )

    reconciliation = SqlEvidenceIndex(
        db_session,
        vector_adapter=LegacyVectorStoreEvidenceAdapter(fake_vector_store),
    ).command(
        ReconcileIndex(
            command_id="test-code-writer-reconciliation",
            collection_name=indexes[1].qdrant_collection or "",
        )
    )
    assert not reconciliation.issues

    with pytest.raises(DuplicateDocumentError):
        service.ingest_local_repository(
            db_session,
            space_id=knowledge_space.id,
            local_path=str(repository),
        )
    assert db_session.query(SourceRevision).filter_by(source_id=source.id).count() == 2
