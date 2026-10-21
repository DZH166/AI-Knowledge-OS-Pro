from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.db.session import get_db
from app.models.source import Source
from app.schemas.code_repository_schema import CodeRepositoryIngestRequest, CodeRepositoryIngestResponse
from app.schemas.media_schema import SourceDetail
from app.services.code_repository_service import code_repository_service

router = APIRouter(prefix="/code-repositories", tags=["code-repositories"])


@router.post("/ingest-local", response_model=CodeRepositoryIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_local_repository(
    payload: CodeRepositoryIngestRequest,
    db: Session = Depends(get_db),
) -> CodeRepositoryIngestResponse:
    try:
        source, file_count, skipped_count = code_repository_service.ingest_local_repository(
            db,
            space_id=payload.space_id,
            local_path=payload.local_path,
            title=payload.title,
            github_url=payload.github_url,
            max_files=payload.max_files,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    chunk_count = sum(len(revision.chunks) for revision in source.revisions)
    return CodeRepositoryIngestResponse(
        source=source,
        file_count=file_count,
        chunk_count=chunk_count,
        skipped_count=skipped_count,
        message="代码仓库已按安全白名单扫描、切片并写入可检索索引。",
    )


@router.get("", response_model=list[SourceDetail])
def list_code_repositories(space_id: int | None = None, db: Session = Depends(get_db)) -> list[Source]:
    return code_repository_service.list_repositories(db, space_id=space_id)


@router.get("/{source_id}", response_model=SourceDetail)
def get_code_repository(source_id: int, db: Session = Depends(get_db)) -> Source:
    try:
        return code_repository_service.get_source(db, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
