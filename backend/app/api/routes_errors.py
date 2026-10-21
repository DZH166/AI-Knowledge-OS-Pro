from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.error_archive import ErrorArchive
from app.schemas.error_schema import ErrorArchiveRead, ErrorArchiveUpdate, ErrorExtractionResponse
from app.services.error_archive_service import error_archive_service


router = APIRouter(prefix="/errors", tags=["errors"])


@router.get("", response_model=list[ErrorArchiveRead])
def list_error_archives(
    space_id: int | None = None,
    source_id: int | None = None,
    archive_status: str | None = None,
    db: Session = Depends(get_db),
) -> list[ErrorArchive]:
    return error_archive_service.list_archives(
        db,
        space_id=space_id,
        source_id=source_id,
        status=archive_status,
    )


@router.post("/from-source/{source_id}", response_model=ErrorExtractionResponse)
def extract_error_from_source(source_id: int, db: Session = Depends(get_db)) -> ErrorExtractionResponse:
    try:
        archive, created = error_archive_service.extract_from_source(db, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    message = "已从 OCR 文本识别并创建报错档案。" if created else "相同报错已经归档，已返回现有记录。"
    return ErrorExtractionResponse(archive=archive, created=created, message=message)


@router.get("/{archive_id}", response_model=ErrorArchiveRead)
def get_error_archive(archive_id: int, db: Session = Depends(get_db)) -> ErrorArchive:
    try:
        return error_archive_service.get_archive(db, archive_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{archive_id}", response_model=ErrorArchiveRead)
def update_error_archive(
    archive_id: int,
    payload: ErrorArchiveUpdate,
    db: Session = Depends(get_db),
) -> ErrorArchive:
    try:
        return error_archive_service.update_archive(
            db,
            archive_id,
            status=payload.status,
            resolution_notes=payload.resolution_notes,
            tags=payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
