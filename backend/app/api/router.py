from fastapi import APIRouter

from app.api import (
    routes_chat,
    routes_dashboard,
    routes_documents,
    routes_errors,
    routes_ingestion_jobs,
    routes_knowledge_spaces,
    routes_learning,
    routes_media,
    routes_onboarding,
    routes_system,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(routes_dashboard.router)
api_router.include_router(routes_knowledge_spaces.router)
api_router.include_router(routes_documents.router)
api_router.include_router(routes_errors.router)
api_router.include_router(routes_ingestion_jobs.router)
api_router.include_router(routes_chat.router)
api_router.include_router(routes_learning.router)
api_router.include_router(routes_media.router)
api_router.include_router(routes_onboarding.router)
api_router.include_router(routes_system.router)
