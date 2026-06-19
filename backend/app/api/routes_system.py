from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.system_schema import SystemStatusResponse, SystemTestResponse
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
