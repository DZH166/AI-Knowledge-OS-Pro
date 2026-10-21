from fastapi import APIRouter

from app.schemas.performance_schema import PerformanceRequestRecord, PerformanceSnapshot, PerformanceSummary
from app.services.performance_service import performance_service

router = APIRouter(prefix="/system/performance", tags=["performance"])


@router.get("", response_model=PerformanceSnapshot)
def get_performance() -> PerformanceSnapshot:
    return performance_service.snapshot()


@router.get("/recent", response_model=list[PerformanceRequestRecord])
def get_recent_performance() -> list[PerformanceRequestRecord]:
    return performance_service.recent(50)


@router.get("/slow", response_model=list[PerformanceRequestRecord])
def get_slow_performance() -> list[PerformanceRequestRecord]:
    return performance_service.slow(10)


@router.get("/summary", response_model=PerformanceSummary)
def get_performance_summary() -> PerformanceSummary:
    return performance_service.summary()
