from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.system_schema import (
    StorageHealthResponse,
    ObservabilityProviderStatus,
    ObservabilityRequest,
    ObservabilityRetrieval,
    ObservabilitySummary,
    ObservabilityTask,
    SystemStatusResponse,
    SystemTestResponse,
)
from app.services.storage_integrity import storage_integrity_service
from app.services.system_service import system_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)) -> SystemStatusResponse:
    return system_service.status(db)


@router.post("/test-llm", response_model=SystemTestResponse)
def test_llm() -> SystemTestResponse:
    return system_service.test_llm()


@router.post("/test-embedding", response_model=SystemTestResponse)
def test_embedding() -> SystemTestResponse:
    return system_service.test_embedding()


@router.post("/test-qdrant", response_model=SystemTestResponse)
def test_qdrant() -> SystemTestResponse:
    return system_service.test_qdrant()


@router.get("/observability", response_model=ObservabilitySummary)
def get_observability(db: Session = Depends(get_db)) -> ObservabilitySummary:
    return system_service.observability(db)


@router.get("/observability/recent-requests", response_model=list[ObservabilityRequest])
def get_recent_requests() -> list[ObservabilityRequest]:
    return system_service.recent_requests()


@router.get("/observability/recent-tasks", response_model=list[ObservabilityTask])
def get_recent_tasks(db: Session = Depends(get_db)) -> list[ObservabilityTask]:
    return system_service.recent_tasks(db)


@router.get("/observability/recent-retrievals", response_model=list[ObservabilityRetrieval])
def get_recent_retrievals(db: Session = Depends(get_db)) -> list[ObservabilityRetrieval]:
    return system_service.recent_retrievals(db)


@router.get("/observability/provider-status", response_model=list[ObservabilityProviderStatus])
def get_provider_status(db: Session = Depends(get_db)) -> list[ObservabilityProviderStatus]:
    return system_service.provider_status(db)


@router.get("/storage-health", response_model=StorageHealthResponse)
def get_storage_health(
    deep_hash: bool = False,
    scan_orphans: bool = True,
    db: Session = Depends(get_db),
) -> StorageHealthResponse:
    """Read-only audit of the database, uploads and evidence bookkeeping."""

    report = storage_integrity_service.check(
        db,
        deep_hash=deep_hash,
        scan_orphans=scan_orphans,
    )
    return StorageHealthResponse(**report.to_dict())
