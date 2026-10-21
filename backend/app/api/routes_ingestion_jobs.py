from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ingestion_job import IngestionJob
from app.models.task_event import JobEvent
from app.schemas.document_schema import IngestionJobRead, JobEventRead
from app.services.ingestion_service import ingestion_service
from app.services.media_task_service import media_task_service

router = APIRouter(prefix="/ingestion-jobs", tags=["ingestion-jobs"])


@router.get("", response_model=list[IngestionJobRead])
def list_ingestion_jobs(
    space_id: int | None = None,
    target_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[IngestionJob]:
    stmt = select(IngestionJob).order_by(IngestionJob.created_at.desc())
    if space_id is not None:
        stmt = stmt.where(IngestionJob.space_id == space_id)
    if target_type is not None:
        stmt = stmt.where(IngestionJob.target_type == target_type)
    return list(db.scalars(stmt).all())


@router.get("/{job_id}", response_model=IngestionJobRead)
def get_ingestion_job(job_id: int, db: Session = Depends(get_db)) -> IngestionJob:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="处理任务不存在。")
    return job


@router.get("/{job_id}/events", response_model=list[JobEventRead])
def list_ingestion_job_events(job_id: int, db: Session = Depends(get_db)) -> list[JobEvent]:
    if db.get(IngestionJob, job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="处理任务不存在。")
    stmt = select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc(), JobEvent.id.asc())
    return list(db.scalars(stmt).all())


@router.post("/{job_id}/retry", response_model=IngestionJobRead)
def retry_ingestion_job(job_id: int, db: Session = Depends(get_db)) -> IngestionJob:
    try:
        existing = db.get(IngestionJob, job_id)
        if existing is None:
            raise ValueError("处理任务不存在。")
        if existing.source_id is not None or existing.target_type == "media":
            job = media_task_service.retry_job(db=db, job_id=job_id, process_immediately=False)
            try:
                media_task_service.start_background_processing(db, job.id)
            except Exception:
                pass
            return job
        job = ingestion_service.retry_job(db=db, job_id=job_id, process_immediately=False)
        mode = job.job_type if job.job_type in {"reparse", "reindex"} else "retry"
        if job.document_id is None:
            raise ValueError("文档任务缺少 document_id。")
        ingestion_service.start_background_processing(job.document_id, job.id, mode=mode, db=db)
        return job
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{job_id}/cancel", response_model=IngestionJobRead)
def cancel_ingestion_job(job_id: int, db: Session = Depends(get_db)) -> IngestionJob:
    try:
        job = db.get(IngestionJob, job_id)
        if job is not None and (job.source_id is not None or job.target_type == "media"):
            return media_task_service.cancel_job(db=db, job_id=job_id)
        return ingestion_service.cancel_job(db=db, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
