from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ServiceError
from app.models.ingestion_job import IngestionJob
from app.models.source import Source
from app.models.task_event import JobEvent
from app.services.error_archive_service import error_archive_service
from app.services.media_service import MediaService, media_service
from app.services.task_broker import task_broker


class _MediaJobCancelled(Exception):
    pass


class MediaTaskService:
    active_statuses = {"queued", "claimed", "running", "cancelling", "retry_scheduled", "interrupted"}
    operation_types = {
        "image_ocr": {"image"},
        "image_visual_description": {"image"},
        "image_screenshot_analysis": {"image"},
        "image_full_analysis": {"image"},
        "audio_transcription": {"audio"},
        "video_transcription": {"video"},
        "video_keyframes": {"video"},
        "video_keyframe_ocr": {"video"},
        "video_visual_description": {"video"},
        "video_full_pipeline": {"video"},
    }

    def __init__(self, processor: MediaService | None = None) -> None:
        self.processor = processor or media_service

    def create_job(
        self,
        db: Session,
        source_id: int,
        operation: str,
        *,
        process_immediately: bool = False,
        parent_job_id: int | None = None,
    ) -> IngestionJob:
        source = self.processor.get_source(db, source_id)
        self._validate_operation(source, operation)
        existing = db.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.source_id == source.id,
                IngestionJob.job_type == operation,
                IngestionJob.status.in_(self.active_statuses),
            )
            .order_by(IngestionJob.created_at.desc())
        )
        if existing is not None and parent_job_id is None:
            return existing

        step_total = len(self._steps(operation))
        retry_count = 0
        if parent_job_id is not None:
            parent = db.get(IngestionJob, parent_job_id)
            retry_count = (parent.retry_count + 1) if parent is not None else 1
        job = IngestionJob(
            document_id=None,
            source_id=source.id,
            space_id=source.space_id,
            target_type="media",
            job_type=operation,
            status="queued",
            current_step="queued",
            step_index=0,
            step_total=step_total,
            progress=0,
            queue_name=settings.task_queue_name,
            priority=settings.task_default_priority,
            max_attempts=settings.task_max_attempts,
            parent_job_id=parent_job_id,
            retry_count=retry_count,
            message="媒体任务已创建，等待 Worker 处理。",
        )
        db.add(job)
        db.flush()
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="queued",
                step="queued",
                progress=0,
                message=job.message,
            )
        )
        self._update_source_task_metadata(source, job, "queued")
        db.commit()
        db.refresh(job)
        if process_immediately:
            self.process_job(db, job.id)
            db.refresh(job)
        return job

    def start_background_processing(self, db: Session, job_id: int) -> IngestionJob:
        job = db.get(IngestionJob, job_id)
        if job is None or job.source_id is None:
            raise ValueError("媒体处理任务不存在。")
        job.status = "queued"
        job.current_step = "queued"
        job.error_code = None
        job.error_message = None
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="queued",
                step="queued",
                progress=job.progress,
                message="媒体任务已写入 Redis 队列。",
            )
        )
        db.commit()
        try:
            enqueue = getattr(task_broker, "enqueue_task", task_broker.enqueue_ingestion)
            enqueue(job.id, job.queue_name)
        except Exception as exc:
            job = db.get(IngestionJob, job_id)
            if job is not None:
                self._fail_job(db, job, "TASK_BROKER_UNAVAILABLE", str(exc), retryable=True)
            raise
        return db.get(IngestionJob, job_id)  # type: ignore[return-value]

    def process_job(self, db: Session, job_id: int) -> IngestionJob:
        job = db.get(IngestionJob, job_id)
        if job is None or job.source_id is None:
            raise ValueError("媒体处理任务不存在。")
        source = self.processor.get_source(db, job.source_id)
        steps = self._steps(job.job_type)
        try:
            now = datetime.now(timezone.utc)
            job.started_at = job.started_at or now
            job.heartbeat_at = now
            job.attempt = (job.attempt or 0) + 1
            self._set_job(db, job, "running", 3, "Worker 已接管媒体任务。", "preflight", 0)
            for index, (step_name, message, action) in enumerate(steps, start=1):
                self._raise_if_cancelled(db, job)
                start_progress = 5 + round((index - 1) / max(1, len(steps)) * 85)
                self._set_job(db, job, "running", start_progress, message, step_name, index)
                action(db, source.id)
                job = db.get(IngestionJob, job_id)
                if job is None:
                    raise ValueError("媒体处理任务不存在。")
                self._raise_if_cancelled(db, job)
                completed_progress = 5 + round(index / max(1, len(steps)) * 85)
                self._set_job(db, job, "running", completed_progress, f"{message}完成。", step_name, index)
            job = db.get(IngestionJob, job_id)
            source = self.processor.get_source(db, source.id)
            if job is None:
                raise ValueError("媒体处理任务不存在。")
            job.status = "completed"
            job.progress = 100
            job.current_step = "completed"
            job.message = "媒体处理已完成，可查看资料详情。"
            job.error_code = None
            job.error_message = None
            job.finished_at = datetime.now(timezone.utc)
            job.duration_ms = self._duration_ms(job)
            job.result_json = json.dumps(
                {
                    "source_id": source.id,
                    "source_type": source.source_type,
                    "detail_url": f"/media/sources/{source.id}",
                    "operation": job.job_type,
                },
                ensure_ascii=False,
            )
            self._update_source_task_metadata(source, job, "completed")
            db.add(
                JobEvent(
                    job_id=job.id,
                    event_type="completed",
                    step="completed",
                    progress=100,
                    message=job.message,
                )
            )
            db.commit()
            db.refresh(job)
            return job
        except _MediaJobCancelled:
            job = db.get(IngestionJob, job_id)
            if job is None:
                raise
            return job
        except Exception as exc:
            db.rollback()
            job = db.get(IngestionJob, job_id)
            if job is None:
                raise
            code = exc.code if isinstance(exc, ServiceError) else "MEDIA_PROCESSING_FAILED"
            retryable = exc.retryable if isinstance(exc, ServiceError) else False
            self._fail_job(db, job, code, str(exc), retryable=retryable)
            raise

    def retry_job(self, db: Session, job_id: int, *, process_immediately: bool = False) -> IngestionJob:
        job = db.get(IngestionJob, job_id)
        if job is None or job.source_id is None:
            raise ValueError("媒体处理任务不存在。")
        if job.status in {"queued", "claimed", "running", "cancelling"}:
            raise ValueError("任务仍在处理中，不能重复重试。")
        return self.create_job(
            db,
            job.source_id,
            job.job_type,
            process_immediately=process_immediately,
            parent_job_id=job.id,
        )

    def cancel_job(self, db: Session, job_id: int) -> IngestionJob:
        job = db.get(IngestionJob, job_id)
        if job is None or job.source_id is None:
            raise ValueError("媒体处理任务不存在。")
        if job.status in {"completed", "cancelled"}:
            return job
        job.cancel_requested_at = datetime.now(timezone.utc)
        if job.status in {"queued", "retry_scheduled", "interrupted", "failed"}:
            self._mark_cancelled(db, job)
        else:
            job.status = "cancelling"
            job.message = "已请求取消，当前步骤结束后停止。"
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
        db.refresh(job)
        return job

    def _steps(self, operation: str) -> list[tuple[str, str, Callable[[Session, int], object]]]:
        operations: dict[str, list[tuple[str, str, Callable[[Session, int], object]]]] = {
            "image_ocr": [("ocr", "正在识别图片文字。", self.processor.process_image_ocr)],
            "image_visual_description": [
                ("visual_description", "正在分析图片内容。", self.processor.process_image_visual_description)
            ],
            "image_screenshot_analysis": [
                ("ocr", "正在识别截图文字。", self.processor.process_image_ocr),
                ("screenshot_analysis", "正在分析截图中的明确报错。", self._analyze_screenshot),
            ],
            "image_full_analysis": [
                ("ocr", "正在识别图片文字。", self.processor.process_image_ocr),
                ("visual_description", "正在分析图片内容。", self.processor.process_image_visual_description),
                ("screenshot_analysis", "正在检查图片中的明确报错。", self._analyze_screenshot),
            ],
            "audio_transcription": [
                ("transcription", "正在执行音频转写。", self.processor.process_audio_transcription)
            ],
            "video_transcription": [
                ("transcription", "正在提取音轨并执行视频转写。", self.processor.process_audio_transcription)
            ],
            "video_keyframes": [
                ("keyframes", "正在抽取并去重视频关键帧。", self.processor.process_video_keyframes)
            ],
            "video_keyframe_ocr": [
                ("keyframe_ocr", "正在识别关键帧文字。", self.processor.process_video_keyframe_ocr)
            ],
            "video_visual_description": [
                ("visual_description", "正在分析关键帧画面。", self.processor.process_video_visual_description)
            ],
            "video_full_pipeline": [
                ("keyframes", "正在抽取并去重视频关键帧。", self.processor.process_video_keyframes),
                ("keyframe_ocr", "正在识别关键帧文字。", self.processor.process_video_keyframe_ocr),
                ("visual_description", "正在分析关键帧画面。", self.processor.process_video_visual_description),
                ("transcription", "正在提取音轨并执行视频转写。", self.processor.process_audio_transcription),
            ],
        }
        if operation not in operations:
            raise ValueError(f"不支持的媒体处理操作：{operation}")
        return operations[operation]

    @staticmethod
    def _analyze_screenshot(db: Session, source_id: int) -> dict:
        try:
            archive, created = error_archive_service.extract_from_source(db, source_id)
            return {"archive_id": archive.id, "created": created}
        except ValueError as exc:
            if "没有识别到明确报错标记" in str(exc) or "还没有可用 OCR 文本" in str(exc):
                return {"archive_id": None, "created": False, "result": "no_explicit_error"}
            raise

    def _validate_operation(self, source: Source, operation: str) -> None:
        allowed_types = self.operation_types.get(operation)
        if allowed_types is None:
            raise ValueError(f"不支持的媒体处理操作：{operation}")
        if source.source_type not in allowed_types:
            raise ValueError(f"{operation} 不支持 {source.source_type} 资料。")

    def _set_job(
        self,
        db: Session,
        job: IngestionJob,
        status: str,
        progress: int,
        message: str,
        step: str,
        step_index: int,
    ) -> None:
        job.status = status
        job.progress = progress
        job.message = message
        job.current_step = step
        job.step_index = step_index
        job.heartbeat_at = datetime.now(timezone.utc)
        db.add(
            JobEvent(
                job_id=job.id,
                event_type=status,
                step=step,
                progress=progress,
                message=message,
            )
        )
        db.commit()
        db.refresh(job)

    def _raise_if_cancelled(self, db: Session, job: IngestionJob) -> None:
        db.refresh(job)
        if job.cancel_requested_at is not None or job.status in {"cancelling", "cancelled"}:
            self._mark_cancelled(db, job)
            raise _MediaJobCancelled()

    @staticmethod
    def _mark_cancelled(db: Session, job: IngestionJob) -> None:
        job.status = "cancelled"
        job.progress = min(job.progress, 99)
        job.current_step = job.current_step or "cancelled"
        job.message = "媒体任务已取消。"
        job.finished_at = datetime.now(timezone.utc)
        job.duration_ms = MediaTaskService._duration_ms(job)
        source = db.get(Source, job.source_id) if job.source_id is not None else None
        if source is not None:
            MediaTaskService._update_source_task_metadata(source, job, "cancelled")
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
    def _fail_job(db: Session, job: IngestionJob, code: str, message: str, *, retryable: bool) -> None:
        job.status = "failed"
        job.error_code = code
        job.error_message = message
        job.error_details_json = json.dumps({"retryable": retryable}, ensure_ascii=False)
        job.message = "媒体处理失败，可在任务中心重试。"
        job.finished_at = datetime.now(timezone.utc)
        job.duration_ms = MediaTaskService._duration_ms(job)
        source = db.get(Source, job.source_id) if job.source_id is not None else None
        if source is not None:
            MediaTaskService._update_source_task_metadata(source, job, "failed")
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="failed",
                step=job.current_step,
                progress=job.progress,
                message=job.message,
                technical_message=message,
            )
        )
        db.commit()

    @staticmethod
    def _update_source_task_metadata(source: Source, job: IngestionJob, status: str) -> None:
        metadata = source.metadata_data
        metadata.update(
            {
                "processing_status": status,
                "last_job_id": job.id,
                "last_job_type": job.job_type,
                "last_job_status": status,
            }
        )
        if status in {"queued", "running"}:
            metadata["active_job_id"] = job.id
        elif metadata.get("active_job_id") == job.id:
            metadata.pop("active_job_id", None)
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)

    @staticmethod
    def _duration_ms(job: IngestionJob) -> int | None:
        if job.started_at is None:
            return None
        started_at = job.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000))


media_task_service = MediaTaskService()
