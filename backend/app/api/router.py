from fastapi import APIRouter

from app.api import (
    routes_chat,
    routes_feedback,
    routes_agent_runs,
    routes_agent_control,
    routes_agent_policy,
    routes_optimizer,
    routes_agent_run_share,
    routes_code_repositories,
    routes_dashboard,
    routes_documents,
    routes_errors,
    routes_evidence,
    routes_ingestion_jobs,
    routes_knowledge_spaces,
    routes_learning,
    routes_media,
    routes_onboarding,
    routes_performance,
    routes_portfolio,
    routes_system,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(routes_feedback.router)
api_router.include_router(routes_agent_runs.router)
api_router.include_router(routes_agent_control.router)
api_router.include_router(routes_agent_policy.router)
api_router.include_router(routes_optimizer.router)
api_router.include_router(routes_agent_run_share.router)
api_router.include_router(routes_evidence.router)
api_router.include_router(routes_dashboard.router)
api_router.include_router(routes_code_repositories.router)
api_router.include_router(routes_knowledge_spaces.router)
api_router.include_router(routes_documents.router)
api_router.include_router(routes_errors.router)
api_router.include_router(routes_ingestion_jobs.router)
api_router.include_router(routes_chat.router)
api_router.include_router(routes_learning.router)
api_router.include_router(routes_media.router)
api_router.include_router(routes_onboarding.router)
api_router.include_router(routes_portfolio.router)
api_router.include_router(routes_system.router)
api_router.include_router(routes_performance.router)
