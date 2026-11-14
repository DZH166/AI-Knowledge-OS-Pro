from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Mapping, Sequence
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import DuplicateDocumentError
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.models.task_event import JobEvent
from app.modules.evidence_index import (
    ActivateRevision,
    CancelRevision,
    ChunkDraft,
    GetRevision,
    PointEmbedding,
    QdrantVectorAdapter,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    UpsertRevisionVectors,
    VectorPointState,
    VectorPointWrite,
    VerifiedPoint,
)
from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.task_broker import task_broker


class LegacyVectorStoreEvidenceAdapter:
    """Expose the V4 VectorStore through the canonical EvidenceIndex vector seam.

    The legacy store accepts list-shaped writes while EvidenceIndex owns the
    immutable point payload.  This adapter translates only the transport shape;
    it deliberately leaves the payload byte-for-byte canonical so the independent
    Qdrant reconciler observes the same digest as activation validation.
    """

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    def upsert_points(self, collection: str, points: Sequence[VectorPointWrite]) -> None:
        self._assert_collection(collection)
        self._vector_store.upsert_chunks(
            point_ids=[point.point_id for point in points],
            vectors=[list(point.vector) for point in points],
            payloads=[dict(point.payload) for point in points],
        )

    def delete_points(self, collection: str, point_ids: Sequence[str]) -> None:
        self._assert_collection(collection)
        self._vector_store.delete_points(list(point_ids))

    def list_points(self, collection: str) -> tuple[VectorPointState, ...]:
        self._assert_collection(collection)
        in_memory_points = getattr(self._vector_store, "points", None)
        if isinstance(in_memory_points, Mapping):
            states = [
                VectorPointState(
                    point_id=str(point_id),
                    vector=tuple(float(value) for value in item.get("vector", ())),
                    payload=dict(item.get("payload", {})),
                )
                for point_id, item in in_memory_points.items()
                if isinstance(item, Mapping)
            ]
            return tuple(sorted(states, key=lambda point: point.point_id))

        client = getattr(self._vector_store, "client", None)
        if client is None:
            raise RuntimeError("Legacy vector store cannot enumerate points for activation verification.")
        return QdrantVectorAdapter(client).list_points(collection)

    def _assert_collection(self, collection: str) -> None:
        configured = getattr(self._vector_store, "collection_name", collection)
        if configured and configured != collection:
            raise ValueError(
                f"Legacy VectorStore is bound to collection {configured!r}, not {collection!r}."
            )


class DocumentIngestionService:
    def __init__(
        self,
        parser: DocumentParser | None = None,
        chunker: Chunker | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.parser = parser or DocumentParser()
        self.chunker = chunker or Chunker()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def ingest_upload(
        self,
        db: Session,
        space_id: int,
        upload_file: UploadFile,
        *,
        process_immediately: bool = True,
    ) -> tuple[Document, IngestionJob]:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")

        original_name = upload_file.filename or "untitled"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.parser.supported_extensions:
            raise ValueError("当前支持 txt、md、pdf 文件。")

        storage_path, content_hash, file_size = self._save_upload(upload_file, original_name)
        duplicate = db.scalar(
            select(Document).where(
                Document.space_id == space_id,
                Document.content_hash == content_hash,
                Document.status != "deleted",
            )
        )
        if duplicate is not None:
            storage_path.unlink(missing_ok=True)
            latest_job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.document_id == duplicate.id)
                .order_by(IngestionJob.created_at.desc())
            )
            raise DuplicateDocumentError(
                "同一知识库中已经存在内容相同的文档。",
                details={
                    "document_id": duplicate.id,
                    "filename": duplicate.original_filename,
                    "status": duplicate.status,
                    "processing_status": duplicate.processing_status,
                    "vector_status": duplicate.vector_status,
                    "job_id": latest_job.id if latest_job else None,
                    "next_action": "ask" if duplicate.status == "ready" and duplicate.vector_status == "indexed" else "reprocess",
                },
            )

        document = Document(
            space_id=space.id,
            filename=storage_path.name,
            original_filename=original_name,
            file_type=suffix.lstrip("."),
            content_type=upload_file.content_type,
            file_size=file_size,
            storage_path=str(storage_path),
            status="uploaded",
            parse_status="pending",
            chunk_status="pending",
            vector_status="pending",
            processing_status="queued",
            processing_progress=0,
            content_hash=content_hash,
            title=Path(original_name).stem,
        )
        db.add(document)
        db.flush()

        job = self._create_job(db, document, "reparse", "queued", 0, "文档已保存，等待解析。")
        db.commit()
        db.refresh(document)
        db.refresh(job)

        if process_immediately:
            self.process_document(db, document.id, job.id, mode="reparse")
            db.refresh(document)
            db.refresh(job)
        return document, job

    def start_background_processing(
        self,
        document_id: int,
        job_id: int,
        mode: str = "reparse",
        db: Session | None = None,
    ) -> None:
        from app.db.session import SessionLocal

        owns_session = db is None
        db = db or SessionLocal()
        try:
            job = db.get(IngestionJob, job_id)
            if job is None:
                raise ValueError("处理任务不存在。")
            job.job_type = mode
            job.status = "queued"
            job.current_step = "queued"
            db.add(
                JobEvent(
                    job_id=job.id,
                    event_type="queued",
                    step="queued",
                    progress=job.progress,
                    message="任务已写入 Redis 队列。",
                )
            )
            db.commit()
            task_broker.enqueue_ingestion(job.id, job.queue_name)
        except Exception as exc:
            job = db.get(IngestionJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_code = "TASK_BROKER_UNAVAILABLE"
                job.error_message = str(exc)
                document = db.get(Document, job.document_id)
                if document is not None:
                    document.status = "failed"
                    document.processing_status = "failed"
                    document.error_message = "TASK_BROKER_UNAVAILABLE: background processing could not be queued."
                db.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="failed",
                        step="queued",
                        progress=job.progress,
                        message="任务队列不可用。",
                        technical_message=str(exc),
                    )
                )
                db.commit()
            raise
        finally:
            if owns_session:
                db.close()

    def process_document(self, db: Session, document_id: int, job_id: int | None = None, mode: str = "reindex") -> Document:
        document = db.get(Document, document_id)
        if document is None:
            raise ValueError("文档不存在。")
        job = db.get(IngestionJob, job_id) if job_id else self._create_job(db, document, mode, "queued", 0, "任务已创建。")
        if job is None:
            raise ValueError("处理任务不存在。")

        evidence_index: SqlEvidenceIndex | None = None
        staged_revision_id: int | None = None
        command_prefix: str | None = None
        try:
            self._raise_if_cancelled(db, document, job)
            now = datetime.now(timezone.utc)
            job.started_at = job.started_at or now
            job.heartbeat_at = now
            job.attempt = (job.attempt or 0) + 1
            self._set_job(db, job, "running", 8, "开始处理文档。", current_step="parsing", step_index=1)
            document.processing_status = "running"
            document.processing_progress = 8
            document.error_message = None
            db.flush()

            if mode in {"reparse", "retry"}:
                parsed = self.parser.parse(Path(document.storage_path))
                text_chunks = self._split_parsed_document(parsed)
                if not text_chunks:
                    raise ValueError("没有解析到可用于问答的文本内容。扫描版 PDF 暂不支持 OCR，后续 V3 会接入 OCR。")
                old_point_ids = self._clear_existing_index(db, document)

                document.parse_status = "parsed"
                document.chunk_status = "chunked"
                document.summary = parsed.summary
                document.extractive_preview = parsed.summary
                document.chunk_count = len(text_chunks)
                document.processing_progress = 45
                self._set_job(
                    db,
                    job,
                    "running",
                    45,
                    f"解析完成，切分出 {len(text_chunks)} 个知识片段。",
                    current_step="chunking",
                    step_index=2,
                )

                chunks: list[Chunk] = []
                for text_chunk in text_chunks:
                    chunks.append(
                        Chunk(
                            document_id=document.id,
                            space_id=document.space_id,
                            chunk_index=text_chunk.chunk_index,
                            content=text_chunk.content,
                            content_preview=text_chunk.content_preview,
                            char_count=text_chunk.char_count,
                            token_count=text_chunk.token_count,
                            section_title=text_chunk.section_title,
                            page_number=text_chunk.page_number,
                            heading_path=text_chunk.heading_path,
                            metadata_json=json.dumps(
                                {
                                    "source_type": document.source_type,
                                    "page_number": text_chunk.page_number,
                                    "heading_path": text_chunk.heading_path,
                                    "section_title": text_chunk.section_title,
                                },
                                ensure_ascii=False,
                            ),
                        )
                    )
                db.add_all(chunks)
                db.flush()
            elif mode == "reindex":
                chunks = list(
                    db.scalars(select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index.asc()))
                )
                if not chunks:
                    return self.process_document(db, document.id, job.id, mode="reparse")
                old_point_ids = [chunk.qdrant_point_id for chunk in chunks if chunk.qdrant_point_id]
                db.flush()
                self._set_job(
                    db,
                    job,
                    "running",
                    45,
                    f"准备重建 {len(chunks)} 个知识片段的向量索引。",
                    current_step="embedding",
                    step_index=3,
                )
            else:
                raise ValueError(f"不支持的处理模式：{mode}")

            self._raise_if_cancelled(db, document, job)
            chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index.asc())))
            vectors = self.embedding_service.embed_texts([chunk.content for chunk in chunks])
            fingerprint = self.embedding_service.fingerprint()
            self._set_job(
                db,
                job,
                "running",
                72,
                "Embedding 已生成，正在写入 Qdrant。",
                current_step="indexing",
                step_index=4,
            )

            source = self._document_source(db, document)
            vector_adapter = LegacyVectorStoreEvidenceAdapter(self.vector_store)
            evidence_index = SqlEvidenceIndex(db, vector_adapter=vector_adapter)
            command_prefix = f"document:{document.id}:job:{job.id}:attempt:{job.attempt}"
            staged = evidence_index.command(
                StageRevision(
                    command_id=f"{command_prefix}:stage",
                    draft=RevisionDraft(
                        source_id=source.id,
                        content_hash=document.content_hash or hashlib.sha256(
                            "\n".join(chunk.content for chunk in chunks).encode("utf-8")
                        ).hexdigest(),
                        index_version=settings.index_version,
                        collection_name=settings.qdrant_collection,
                        chunks=tuple(
                            ChunkDraft(
                                chunk_index=chunk.chunk_index,
                                modality="text",
                                content=chunk.content,
                                search_text=chunk.content,
                                locator={
                                    "kind": "document_page" if chunk.page_number is not None else "document_chunk",
                                    "source_type": "document",
                                    "source_id": source.id,
                                    "document_id": document.id,
                                    "document_name": document.original_filename,
                                    "legacy_chunk_id": chunk.id,
                                    "page_number": chunk.page_number,
                                    "heading_path": chunk.heading_path,
                                    "section_title": chunk.section_title,
                                },
                            )
                            for chunk in chunks
                        ),
                        parser_name="document_ingestion_service",
                        parser_version="v5-canonical-1",
                        embedding_provider=self.embedding_service.provider.name,
                        embedding_model=self.embedding_service.provider.model,
                        embedding_dimensions=self.embedding_service.provider.dimensions,
                        embedding_fingerprint=fingerprint,
                        metadata={
                            "document_id": document.id,
                            "job_id": job.id,
                            "mode": mode,
                            "original_filename": document.original_filename,
                        },
                    ),
                )
            )
            staged_revision_id = staged.revision_id
            canonical_chunks = list(
                db.scalars(
                    select(MultimodalChunk)
                    .where(MultimodalChunk.revision_id == staged_revision_id)
                    .order_by(MultimodalChunk.chunk_index, MultimodalChunk.id)
                )
            )
            if len(canonical_chunks) != len(chunks):
                raise RuntimeError("Canonical document revision did not preserve the legacy chunk cardinality.")
            revision = db.get(SourceRevision, staged_revision_id)
            if revision is None:
                raise RuntimeError("Canonical document revision disappeared after staging.")
            revision.document_id = document.id
            for legacy_chunk, canonical_chunk in zip(chunks, canonical_chunks, strict=True):
                canonical_chunk.legacy_chunk_id = legacy_chunk.id
                canonical_chunk.page_number = legacy_chunk.page_number
            db.commit()

            evidence_index.command(
                UpsertRevisionVectors(
                    command_id=f"{command_prefix}:upsert",
                    revision_id=staged_revision_id,
                    points=tuple(
                        PointEmbedding(
                            point_id=canonical_chunk.qdrant_point_id or "",
                            vector=tuple(float(value) for value in vector),
                        )
                        for canonical_chunk, vector in zip(canonical_chunks, vectors, strict=True)
                    ),
                )
            )
            revision_view = evidence_index.query(GetRevision(revision_id=staged_revision_id))
            self._raise_if_cancelled(db, document, job)
            evidence_index.command(
                ActivateRevision(
                    command_id=f"{command_prefix}:activate",
                    revision_id=staged_revision_id,
                    verified_points=tuple(
                        VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                        for point in revision_view.points
                    ),
                )
            )

            for legacy_chunk, canonical_chunk in zip(chunks, canonical_chunks, strict=True):
                legacy_chunk.qdrant_point_id = canonical_chunk.qdrant_point_id
            self._best_effort_delete_points(
                [
                    point_id
                    for point_id in old_point_ids
                    if point_id not in {chunk.qdrant_point_id for chunk in canonical_chunks}
                ]
            )

            document.vector_status = "indexed"
            document.status = "ready"
            document.processing_status = "completed"
            document.processing_progress = 100
            document.indexed_at = datetime.now(timezone.utc)
            document.embedding_provider = self.embedding_service.provider.name
            document.embedding_model = self.embedding_service.provider.model
            document.embedding_dimensions = self.embedding_service.provider.dimensions
            document.embedding_fingerprint = fingerprint
            document.index_version = settings.index_version
            job.finished_at = datetime.now(timezone.utc)
            job.duration_ms = self._duration_ms(job)
            job.result_json = json.dumps(
                {
                    "document_id": document.id,
                    "source_id": source.id,
                    "revision_id": staged_revision_id,
                    "index_revision_id": source.active_index_revision_id,
                    "chunk_count": len(chunks),
                },
                ensure_ascii=False,
            )
            self._set_job(
                db,
                job,
                "completed",
                100,
                "文档解析、切片和索引已完成。",
                current_step="completed",
                step_index=5,
            )
            db.commit()
            return document
        except _JobCancelled:
            self._cancel_staged_revision(
                db,
                evidence_index=evidence_index,
                revision_id=staged_revision_id,
                command_prefix=command_prefix,
                reason="Document ingestion was cancelled before activation.",
            )
            return document
        except Exception as exc:
            self._cancel_staged_revision(
                db,
                evidence_index=evidence_index,
                revision_id=staged_revision_id,
                command_prefix=command_prefix,
                reason=f"Document ingestion failed: {exc}",
            )
            document.status = "failed"
            document.processing_status = "failed"
            document.error_message = str(exc)
            if document.parse_status == "pending":
                document.parse_status = "failed"
            elif document.chunk_status == "pending":
                document.chunk_status = "failed"
            else:
                document.vector_status = "failed"
            job.finished_at = datetime.now(timezone.utc)
            job.duration_ms = self._duration_ms(job)
            job.error_code = exc.__class__.__name__.upper()
            job.error_details_json = json.dumps({"type": exc.__class__.__name__}, ensure_ascii=False)
            self._set_job(db, job, "failed", document.processing_progress or 0, "处理失败。", str(exc))
            db.commit()
            raise

    def retry_document(
        self,
        db: Session,
        document_id: int,
        *,
        process_immediately: bool = True,
    ) -> tuple[Document, IngestionJob]:
        document = db.get(Document, document_id)
        if document is None:
            raise ValueError("文档不存在。")
        document.retry_count += 1
        job = self._create_job(db, document, "retry", "queued", 0, "准备重试处理文档。")
        db.commit()
        if process_immediately:
            self.process_document(db, document.id, job.id, mode="retry")
        db.refresh(document)
        db.refresh(job)
        return document, job

    def reparse_document(
        self,
        db: Session,
        document_id: int,
        *,
        process_immediately: bool = True,
    ) -> tuple[Document, IngestionJob]:
        document = db.get(Document, document_id)
        if document is None:
            raise ValueError("文档不存在。")
        job = self._create_job(db, document, "reparse", "queued", 0, "准备重新解析文档。")
        db.commit()
        if process_immediately:
            self.process_document(db, document.id, job.id, mode="reparse")
        db.refresh(document)
        db.refresh(job)
        return document, job

    def reindex_document(
        self,
        db: Session,
        document_id: int,
        *,
        process_immediately: bool = True,
    ) -> tuple[Document, IngestionJob]:
        document = db.get(Document, document_id)
        if document is None:
            raise ValueError("文档不存在。")
        job = self._create_job(db, document, "reindex", "queued", 0, "准备重建向量索引。")
        db.commit()
        if process_immediately:
            self.process_document(db, document.id, job.id, mode="reindex")
        db.refresh(document)
        db.refresh(job)
        return document, job

    def retry_job(self, db: Session, job_id: int, *, process_immediately: bool = False) -> IngestionJob:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise ValueError("处理任务不存在。")
        document = db.get(Document, job.document_id)
        if document is None:
            raise ValueError("文档不存在。")
        document.retry_count += 1
        mode = job.job_type if job.job_type in {"reparse", "reindex"} else "retry"
        new_job = self._create_job(
            db,
            document,
            mode,
            "queued",
            0,
            "准备重新执行处理任务。",
            parent_job_id=job.id,
        )
        db.commit()
        if process_immediately:
            self.process_document(db, document.id, new_job.id, mode=mode)
        return new_job

    def cancel_job(self, db: Session, job_id: int) -> IngestionJob:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise ValueError("处理任务不存在。")
        job.cancel_requested_at = datetime.now(timezone.utc)
        document = db.get(Document, job.document_id)
        if document is not None and job.status in {"queued", "retry_scheduled", "interrupted", "failed"}:
            self._mark_cancelled(db, document, job)
        elif document is not None and job.status in {"claimed", "running"}:
            job.status = "cancelling"
            job.message = "已请求取消，Worker 将在安全检查点停止。"
            db.add(
                JobEvent(
                    job_id=job.id,
                    event_type="cancelling",
                    step=job.current_step,
                    progress=job.progress,
                    message=job.message,
                )
            )
            db.commit()
            try:
                task_broker.cancel(job.id)
            except Exception:
                pass
        return job

    def delete_document(self, db: Session, document_id: int) -> None:
        document = db.get(Document, document_id)
        if document is None:
            raise ValueError("文档不存在。")
        chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == document.id)))
        source = db.scalar(select(Source).where(Source.document_id == document.id))
        if source is not None:
            storage_path = Path(document.storage_path)
            point_ids = list(
                db.scalars(
                    select(MultimodalChunk.qdrant_point_id).where(
                        MultimodalChunk.source_id == source.id,
                        MultimodalChunk.qdrant_point_id.is_not(None),
                    )
                ).all()
            )
            self._soft_retire_document_source(db, source)
            db.delete(document)
            db.commit()
            self._best_effort_delete_points([*point_ids, *(chunk.qdrant_point_id for chunk in chunks)])
            storage_path.unlink(missing_ok=True)
            return
        self._delete_qdrant_points_for_chunks(chunks)
        Path(document.storage_path).unlink(missing_ok=True)
        db.delete(document)
        db.commit()

    def bulk_delete_documents(self, db: Session, document_ids: list[int]) -> int:
        documents = list(db.scalars(select(Document).where(Document.id.in_(document_ids))))
        if not documents:
            return 0
        chunks = list(db.scalars(select(Chunk).where(Chunk.document_id.in_([item.id for item in documents]))))
        sources = list(db.scalars(select(Source).where(Source.document_id.in_([item.id for item in documents]))))
        canonical_source_ids = {source.id for source in sources}
        canonical_document_ids = {source.document_id for source in sources if source.document_id is not None}
        canonical_storage_paths = [Path(document.storage_path) for document in documents if document.id in canonical_document_ids]
        point_ids = list(
            db.scalars(
                select(MultimodalChunk.qdrant_point_id).where(
                    MultimodalChunk.source_id.in_(canonical_source_ids),
                    MultimodalChunk.qdrant_point_id.is_not(None),
                )
            ).all()
        ) if canonical_source_ids else []
        if sources:
            for source in sources:
                self._soft_retire_document_source(db, source)
        else:
            self._delete_qdrant_points_for_chunks(chunks)
        storage_paths = [Path(document.storage_path) for document in documents if document.id not in canonical_document_ids]
        for document in documents:
            db.delete(document)
        db.commit()
        for storage_path in storage_paths:
            storage_path.unlink(missing_ok=True)
        for storage_path in canonical_storage_paths:
            storage_path.unlink(missing_ok=True)
        self._best_effort_delete_points([*point_ids, *(chunk.qdrant_point_id for chunk in chunks)])
        return len(documents)

    def _soft_retire_document_source(self, db: Session, source: Source) -> None:
        """Make canonical evidence query-invisible while preserving provenance."""
        now = datetime.now(timezone.utc)
        source.status = "retired"
        source.retired_at = now
        source.active_revision_id = None
        source.active_index_revision_id = None
        source.document_id = None
        revisions = list(db.scalars(select(SourceRevision).where(SourceRevision.source_id == source.id)))
        for revision in revisions:
            revision.status = "retired"
            revision.retired_at = now
            revision.document_id = None
            for chunk in revision.chunks:
                chunk.status = "retired"
                chunk.retired_at = now
        for index_revision in db.scalars(select(IndexRevision).where(IndexRevision.source_id == source.id)):
            index_revision.status = "retired"
            index_revision.retired_at = now
        db.flush()

    def bulk_reindex_documents(self, db: Session, document_ids: list[int]) -> list[IngestionJob]:
        jobs: list[IngestionJob] = []
        for document_id in document_ids:
            document = db.get(Document, document_id)
            if document is None:
                continue
            jobs.append(self._create_job(db, document, "reindex", "queued", 0, "已加入重建索引队列。"))
        db.commit()
        for job in jobs:
            self.start_background_processing(job.document_id, job.id, mode="reindex", db=db)
        return jobs

    def bulk_update_tags(self, db: Session, document_ids: list[int], tags: list[str]) -> int:
        count = 0
        encoded = json.dumps(tags, ensure_ascii=False)
        for document_id in document_ids:
            document = db.get(Document, document_id)
            if document is None:
                continue
            document.tags_json = encoded
            count += 1
        db.commit()
        return count

    def update_document(
        self,
        db: Session,
        document_id: int,
        title: str | None,
        tags: list[str] | None,
        summary: str | None,
    ) -> Document:
        document = db.get(Document, document_id)
        if document is None:
            raise ValueError("文档不存在。")
        if title is not None:
            document.title = title
        if tags is not None:
            document.tags_json = json.dumps(tags, ensure_ascii=False)
        if summary is not None:
            document.summary = summary
        db.commit()
        db.refresh(document)
        return document

    def _save_upload(self, upload_file: UploadFile, original_name: str) -> tuple[Path, str, int]:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(original_name)
        storage_path = settings.upload_dir / f"{uuid4().hex}_{safe_name}"
        hasher = hashlib.sha256()
        total_size = 0

        upload_file.file.seek(0)
        try:
            with storage_path.open("wb") as buffer:
                while True:
                    chunk = upload_file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > settings.max_upload_size_bytes:
                        buffer.close()
                        storage_path.unlink(missing_ok=True)
                        raise ValueError(f"文件超过上传限制：{settings.max_upload_size_mb} MB。")
                    hasher.update(chunk)
                    buffer.write(chunk)
                buffer.flush()
                os.fsync(buffer.fileno())
        except OSError as exc:
            storage_path.unlink(missing_ok=True)
            raise ValueError("文件未能安全写入磁盘；请检查磁盘空间和权限后重试。") from exc
        if storage_path.stat().st_size != total_size:
            storage_path.unlink(missing_ok=True)
            raise ValueError("文件写入不完整；已删除残留文件，请重试上传。")

        return storage_path, hasher.hexdigest(), total_size

    def _split_parsed_document(self, parsed) -> list:
        if parsed.document_type == "pdf" and parsed.pages:
            return self.chunker.split_pdf_pages(parsed.pages)
        if parsed.document_type == "markdown":
            return self.chunker.split_markdown(parsed.text)
        return self.chunker.split(parsed.text)

    def _document_source(self, db: Session, document: Document) -> Source:
        source = db.scalar(select(Source).where(Source.document_id == document.id))
        metadata = {
            "ingestion_mode": "document",
            "document_id": document.id,
            "file_type": document.file_type,
            "legacy_document_status": document.status,
        }
        if source is None:
            source = Source(
                space_id=document.space_id,
                document_id=document.id,
                source_type="document",
                title=document.title,
                original_filename=document.original_filename,
                mime_type=document.content_type,
                file_size=document.file_size,
                storage_path=document.storage_path,
                content_hash=document.content_hash,
                status="uploaded",
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(source)
        else:
            source.title = document.title
            source.original_filename = document.original_filename
            source.mime_type = document.content_type
            source.file_size = document.file_size
            source.storage_path = document.storage_path
            source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.flush()
        return source

    def _clear_existing_index(self, db: Session, document: Document) -> list[str]:
        chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == document.id)))
        old_point_ids = [chunk.qdrant_point_id for chunk in chunks if chunk.qdrant_point_id]
        legacy_chunk_ids = [chunk.id for chunk in chunks]
        if legacy_chunk_ids:
            # Canonical historical evidence remains immutable after the V4
            # current-view rows are replaced, so detach only the compatibility
            # foreign key before deleting those legacy Chunk rows.
            db.execute(
                update(MultimodalChunk)
                .where(MultimodalChunk.legacy_chunk_id.in_(legacy_chunk_ids))
                .values(legacy_chunk_id=None)
            )
        db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        document.chunk_count = 0
        document.chunk_status = "pending"
        document.vector_status = "pending"
        db.flush()
        return [point_id for point_id in old_point_ids if point_id]

    def _cancel_staged_revision(
        self,
        db: Session,
        *,
        evidence_index: SqlEvidenceIndex | None,
        revision_id: int | None,
        command_prefix: str | None,
        reason: str,
    ) -> None:
        if evidence_index is None or revision_id is None or command_prefix is None:
            return
        revision = db.get(SourceRevision, revision_id)
        if revision is None or revision.status in {"active", "cancelled"}:
            return
        try:
            evidence_index.command(
                CancelRevision(
                    command_id=f"{command_prefix}:cancel",
                    revision_id=revision_id,
                    reason=reason[:1000],
                )
            )
        except Exception:
            # The EvidenceIndex operation/manifest records remain the durable
            # recovery surface for the reconciler when compensation also fails.
            db.rollback()

    def _best_effort_delete_points(self, point_ids: Sequence[str]) -> None:
        unique_point_ids = list(dict.fromkeys(point_id for point_id in point_ids if point_id))
        if not unique_point_ids:
            return
        try:
            self.vector_store.delete_points(unique_point_ids)
        except Exception:
            # Activation already made the old revision query-invisible. Physical
            # cleanup is intentionally non-fatal and can be repaired by reconcile.
            return

    def _delete_qdrant_points_for_chunks(self, chunks: list) -> None:
        point_ids = [chunk.qdrant_point_id for chunk in chunks if getattr(chunk, "qdrant_point_id", None)]
        self.vector_store.delete_points([point_id for point_id in point_ids if point_id])

    def _create_job(
        self,
        db: Session,
        document: Document,
        job_type: str,
        status: str,
        progress: int,
        message: str,
        parent_job_id: int | None = None,
    ) -> IngestionJob:
        job = IngestionJob(
            document_id=document.id,
            space_id=document.space_id,
            job_type=job_type,
            status=status,
            current_step="queued",
            step_index=0,
            step_total=5,
            progress=progress,
            message=message,
            queue_name=settings.task_queue_name,
            priority=settings.task_default_priority,
            max_attempts=settings.task_max_attempts,
            parent_job_id=parent_job_id,
            retry_count=document.retry_count,
        )
        db.add(job)
        db.flush()
        db.add(
            JobEvent(
                job_id=job.id,
                event_type=status,
                step="queued",
                progress=progress,
                message=message,
            )
        )
        return job

    def _set_job(
        self,
        db: Session,
        job: IngestionJob,
        status: str,
        progress: int,
        message: str | None = None,
        error_message: str | None = None,
        current_step: str | None = None,
        step_index: int | None = None,
    ) -> None:
        job.status = status
        job.progress = progress
        job.message = message
        job.error_message = error_message
        job.current_step = current_step or job.current_step
        if step_index is not None:
            job.step_index = step_index
        job.heartbeat_at = datetime.now(timezone.utc)
        db.add(
            JobEvent(
                job_id=job.id,
                event_type=status,
                step=job.current_step,
                progress=progress,
                message=message,
                technical_message=error_message,
            )
        )
        db.commit()
        db.refresh(job)

    def _raise_if_cancelled(self, db: Session, document: Document, job: IngestionJob) -> None:
        db.refresh(job)
        if job.cancel_requested_at is not None or job.status in {"cancelling", "cancelled"}:
            self._mark_cancelled(db, document, job)
            raise _JobCancelled()

    def _mark_cancelled(self, db: Session, document: Document, job: IngestionJob) -> None:
        job.status = "cancelled"
        job.progress = min(job.progress, 99)
        job.message = "任务已取消。"
        job.finished_at = datetime.now(timezone.utc)
        job.duration_ms = self._duration_ms(job)
        document.processing_status = "cancelled"
        document.status = "failed"
        document.error_message = "处理任务已取消。"
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="cancelled",
                step=job.current_step,
                progress=job.progress,
                message=job.message,
            )
        )
        db.commit()

    @staticmethod
    def _duration_ms(job: IngestionJob) -> int | None:
        if job.started_at is None:
            return None
        started_at = job.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000))

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", filename).strip("._")
        return cleaned or "document"


class _JobCancelled(Exception):
    pass


ingestion_service = DocumentIngestionService()
