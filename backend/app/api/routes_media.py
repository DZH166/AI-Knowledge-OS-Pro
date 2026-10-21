from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.db.session import get_db
from app.models.source import MediaAsset, Source
from app.schemas.media_schema import (
    AudioTranscriptionResponse,
    AudioUploadResponse,
    ImageOCRResponse,
    ImageUploadResponse,
    MediaProcessRequest,
    MediaTaskResponse,
    SourceDetail,
    VideoUploadResponse,
)
from app.services.media_service import media_service
from app.services.media_task_service import media_task_service

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/images/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_image(
    space_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImageUploadResponse:
    try:
        source = media_service.upload_image(db=db, space_id=space_id, upload_file=file)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ImageUploadResponse(source=source, message="图片已保存为多模态资料。当前版本仅记录真实图片元数据，未生成伪 OCR。")


@router.post("/audio/upload", response_model=AudioUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_audio(
    space_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AudioUploadResponse:
    try:
        source = media_service.upload_audio(db=db, space_id=space_id, upload_file=file)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AudioUploadResponse(source=source, message="音频已保存并读取真实时长，可在详情页配置真实转写。")


@router.post("/video/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_video(
    space_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoUploadResponse:
    try:
        source = media_service.upload_video(db=db, space_id=space_id, upload_file=file)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    job = media_task_service.create_job(db, source.id, "video_keyframes")
    try:
        media_task_service.start_background_processing(db, job.id)
    except Exception:
        job = db.get(type(job), job.id) or job
    return VideoUploadResponse(
        source=media_service.get_source(db, source.id),
        job_id=job.id,
        message="视频已保存并读取真实元数据，多关键帧任务已进入任务中心。",
    )


@router.get("/sources", response_model=list[SourceDetail])
def list_sources(
    space_id: int | None = None,
    source_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[Source]:
    return media_service.list_sources(db=db, space_id=space_id, source_type=source_type)


@router.get("/sources/{source_id}", response_model=SourceDetail)
def get_source(source_id: int, db: Session = Depends(get_db)) -> Source:
    try:
        return media_service.get_source(db=db, source_id=source_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/sources/{source_id}/file", response_class=FileResponse)
def get_source_file(source_id: int, db: Session = Depends(get_db)) -> FileResponse:
    try:
        source = media_service.get_source(db=db, source_id=source_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not source.storage_path or not Path(source.storage_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料文件不存在。")
    return FileResponse(
        path=source.storage_path,
        media_type=source.mime_type or "application/octet-stream",
        filename=source.original_filename,
    )


@router.get("/assets/{asset_id}/file", response_class=FileResponse)
def get_media_asset_file(asset_id: int, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体资产不存在。")
    if not asset.storage_path or not Path(asset.storage_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体资产文件不存在。")
    return FileResponse(
        path=asset.storage_path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=Path(asset.storage_path).name,
    )


@router.post("/sources/{source_id}/process", response_model=MediaTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_media_process(
    source_id: int,
    payload: MediaProcessRequest,
    db: Session = Depends(get_db),
) -> MediaTaskResponse:
    try:
        job = media_task_service.create_job(db, source_id, payload.operation)
        if job.status == "queued":
            try:
                media_task_service.start_background_processing(db, job.id)
            except Exception:
                job = db.get(type(job), job.id) or job
        return MediaTaskResponse(
            source=media_service.get_source(db, source_id),
            job=job,
            message="媒体处理任务已进入任务中心。",
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/sources/{source_id}/ocr", response_model=MediaTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def run_image_ocr(source_id: int, db: Session = Depends(get_db)) -> MediaTaskResponse:
    return enqueue_media_process(source_id, MediaProcessRequest(operation="image_ocr"), db)


@router.post("/sources/{source_id}/transcribe", response_model=MediaTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def run_audio_transcription(source_id: int, db: Session = Depends(get_db)) -> MediaTaskResponse:
    source = media_service.get_source(db, source_id)
    operation = "video_transcription" if source.source_type == "video" else "audio_transcription"
    return enqueue_media_process(source_id, MediaProcessRequest(operation=operation), db)
