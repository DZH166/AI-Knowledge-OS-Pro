from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import DuplicateDocumentError
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_space import KnowledgeSpace
from app.models.task_event import JobEvent
from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.task_broker import task_broker


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
                self._clear_existing_index(db, document)
                parsed = self.parser.parse(Path(document.storage_path))
                text_chunks = self._split_parsed_document(parsed)
                if not text_chunks:
                    raise ValueError("没有解析到可用于问答的文本内容。扫描版 PDF 暂不支持 OCR，后续 V3 会接入 OCR。")

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
                self._delete_qdrant_points_for_chunks(chunks)
                for chunk in chunks:
                    chunk.qdrant_point_id = None
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
            point_ids = [str(uuid4()) for _ in chunks]
            fingerprint = self.embedding_service.fingerprint()
            payloads = [
                {
                    "space_id": document.space_id,
                    "document_id": document.id,
                    "document_name": document.original_filename,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "content_preview": chunk.content_preview,
                    "page_number": chunk.page_number,
                    "heading_path": chunk.heading_path,
                    "section_title": chunk.section_title,
                    "embedding_fingerprint": fingerprint,
                    "index_version": settings.index_version,
                }
                for chunk in chunks
            ]
            self._set_job(
                db,
                job,
                "running",
                72,
                "Embedding 已生成，正在写入 Qdrant。",
                current_step="indexing",
                step_index=4,
            )
            self.vector_store.upsert_chunks(point_ids=point_ids, vectors=vectors, payloads=payloads)
            self._raise_if_cancelled(db, document, job)

            for chunk, point_id in zip(chunks, point_ids, strict=True):
                chunk.qdrant_point_id = point_id

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
            job.result_json = json.dumps({"document_id": document.id, "chunk_count": len(chunks)}, ensure_ascii=False)
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
            return document
        except Exception as exc:
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
        self._delete_qdrant_points_for_chunks(chunks)
        Path(document.storage_path).unlink(missing_ok=True)
        db.delete(document)
        db.commit()

    def bulk_delete_documents(self, db: Session, document_ids: list[int]) -> int:
        documents = list(db.scalars(select(Document).where(Document.id.in_(document_ids))))
        if not documents:
            return 0
        chunks = list(db.scalars(select(Chunk).where(Chunk.document_id.in_([item.id for item in documents]))))
        self._delete_qdrant_points_for_chunks(chunks)
        storage_paths = [Path(document.storage_path) for document in documents]
        for document in documents:
            db.delete(document)
        db.commit()
        for storage_path in storage_paths:
            storage_path.unlink(missing_ok=True)
        return len(documents)

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

        return storage_path, hasher.hexdigest(), total_size

    def _split_parsed_document(self, parsed) -> list:
        if parsed.document_type == "pdf" and parsed.pages:
            return self.chunker.split_pdf_pages(parsed.pages)
        if parsed.document_type == "markdown":
            return self.chunker.split_markdown(parsed.text)
        return self.chunker.split(parsed.text)

    def _clear_existing_index(self, db: Session, document: Document) -> None:
        chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == document.id)))
        self._delete_qdrant_points_for_chunks(chunks)
        db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        document.chunk_count = 0
        document.chunk_status = "pending"
        document.vector_status = "pending"
        db.flush()

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
