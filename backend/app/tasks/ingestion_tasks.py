from __future__ import annotations

import socket

from app.db.session import SessionLocal
from app.models.ingestion_job import IngestionJob
from app.services.ingestion_service import ingestion_service


def run_task_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        if job is None or job.status in {"cancelled", "completed"}:
            return
        job.worker_id = socket.gethostname()
        job.status = "claimed"
        db.commit()
        if job.source_id is not None or job.target_type == "media":
            from app.services.media_task_service import media_task_service

            media_task_service.process_job(db, job.id)
            return
        if job.document_id is None:
            raise ValueError("文档任务缺少 document_id。")
        mode = job.job_type if job.job_type in {"reparse", "reindex", "retry"} else "reparse"
        ingestion_service.process_document(db, job.document_id, job.id, mode=mode)
    finally:
        db.close()


def run_ingestion_job(job_id: int) -> None:
    """Backward-compatible RQ entrypoint for jobs queued before V3.6."""
    run_task_job(job_id)
