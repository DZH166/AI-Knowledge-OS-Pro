from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.db.session import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.document_schema import (
    BulkDocumentActionResponse,
    BulkDocumentIds,
    BulkTagRequest,
    ChunkRead,
    DocumentActionResponse,
    DocumentRead,
    DocumentUpdate,
    DocumentUploadResponse,
)
from app.services.ingestion_service import ingestion_service
from app.services.rag_service import rag_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _document_read(db: Session, document: Document) -> DocumentRead:
    actual_chunk_count = db.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == document.id)) or 0
    return DocumentRead.model_validate(document).model_copy(update={"chunk_count": int(actual_chunk_count)})


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    space_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    try:
        document, job_id = rag_service.ingest_document(
            db=db,
            space_id=space_id,
            upload_file=file,
            process_immediately=False,
        )
        try:
            ingestion_service.start_background_processing(document.id, job_id, mode="reparse", db=db)
        except Exception:
            db.refresh(document)
            return DocumentUploadResponse(
                document=document,
                message="文件已保存，但后台任务未能入队。请在任务中心检查 Redis/Worker 后重新处理。",
                job_id=job_id,
            )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentUploadResponse(document=document, message="文档已上传，正在后台处理。", job_id=job_id)


@router.get("", response_model=list[DocumentRead])
def list_documents(space_id: int | None = None, db: Session = Depends(get_db)) -> list[DocumentRead]:
    stmt = select(Document).order_by(Document.created_at.desc())
    if space_id is not None:
        stmt = stmt.where(Document.space_id == space_id)
    return [_document_read(db, document) for document in db.scalars(stmt).all()]


@router.post("/bulk-delete", response_model=BulkDocumentActionResponse)
def bulk_delete_documents(payload: BulkDocumentIds, db: Session = Depends(get_db)) -> BulkDocumentActionResponse:
    try:
        count = ingestion_service.bulk_delete_documents(db=db, document_ids=payload.document_ids)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    return BulkDocumentActionResponse(affected_count=count, message=f"已删除 {count} 个文档。")


@router.post("/bulk-reindex", response_model=BulkDocumentActionResponse)
def bulk_reindex_documents(payload: BulkDocumentIds, db: Session = Depends(get_db)) -> BulkDocumentActionResponse:
    try:
        jobs = ingestion_service.bulk_reindex_documents(db=db, document_ids=payload.document_ids)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    return BulkDocumentActionResponse(
        affected_count=len(jobs),
        job_ids=[job.id for job in jobs],
        message=f"已为 {len(jobs)} 个文档创建重建索引任务。",
    )


@router.post("/bulk-tags", response_model=BulkDocumentActionResponse)
def bulk_update_document_tags(payload: BulkTagRequest, db: Session = Depends(get_db)) -> BulkDocumentActionResponse:
    count = ingestion_service.bulk_update_tags(db=db, document_ids=payload.document_ids, tags=payload.tags)
    return BulkDocumentActionResponse(affected_count=count, message=f"已更新 {count} 个文档的标签。")


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentRead:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在。")
    return _document_read(db, document)


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)) -> Document:
    try:
        return ingestion_service.update_document(
            db=db,
            document_id=document_id,
            title=payload.title,
            tags=payload.tags,
            summary=payload.summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{document_id}", response_model=DocumentActionResponse)
def delete_document(document_id: int, db: Session = Depends(get_db)) -> DocumentActionResponse:
    try:
        ingestion_service.delete_document(db=db, document_id=document_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentActionResponse(document=None, message="文档、原文件、知识片段和 Qdrant points 已删除。")


@router.post("/{document_id}/retry", response_model=DocumentActionResponse)
def retry_document(document_id: int, db: Session = Depends(get_db)) -> DocumentActionResponse:
    return _enqueue_document_action(db, document_id, "retry")


@router.post("/{document_id}/reparse", response_model=DocumentActionResponse)
def reparse_document(document_id: int, db: Session = Depends(get_db)) -> DocumentActionResponse:
    return _enqueue_document_action(db, document_id, "reparse")


@router.post("/{document_id}/reindex", response_model=DocumentActionResponse)
def reindex_document(document_id: int, db: Session = Depends(get_db)) -> DocumentActionResponse:
    return _enqueue_document_action(db, document_id, "reindex")


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
def list_document_chunks(document_id: int, db: Session = Depends(get_db)) -> list[Chunk]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在。")
    stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index.asc())
    return list(db.scalars(stmt).all())


def _enqueue_document_action(db: Session, document_id: int, action: str) -> DocumentActionResponse:
    try:
        if action == "retry":
            document, job = ingestion_service.retry_document(db=db, document_id=document_id, process_immediately=False)
            message = "文档重试任务已创建，Worker 会在后台处理。"
        elif action == "reparse":
            document, job = ingestion_service.reparse_document(db=db, document_id=document_id, process_immediately=False)
            message = "文档重新解析任务已创建，Worker 会在后台处理。"
        elif action == "reindex":
            document, job = ingestion_service.reindex_document(db=db, document_id=document_id, process_immediately=False)
            message = "文档向量索引重建任务已创建，Worker 会在后台处理。"
        else:
            raise ValueError("不支持的文档操作。")
        ingestion_service.start_background_processing(document.id, job.id, mode=job.job_type, db=db)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentActionResponse(document=document, message=message, job_id=job.id)
