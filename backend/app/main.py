from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import ServiceError
from app.core.logging import configure_logging
from app.core.responses import ApiEnvelopeMiddleware, RequestIdMiddleware, error_envelope, service_error_response
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_semver,
    description=(
        "溯知 Evidence OS V5.1: an evidence-native research agent with immutable "
        "provenance, durable execution and human review."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiEnvelopeMiddleware)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(ServiceError)
def handle_service_error(request: Request, exc: ServiceError):
    return service_error_response(request, exc)


@app.exception_handler(HTTPException)
def handle_http_error(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", "unknown")
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "HTTP_ERROR"))
        message = str(detail.get("message", detail.get("user_message", "请求处理失败")))
        user_message = str(detail.get("user_message", message))
        details = detail.get("details", {})
        retryable = bool(detail.get("retryable", False))
    else:
        code = "HTTP_ERROR"
        message = str(detail)
        user_message = message
        details = {}
        retryable = False
    return error_envelope(
        code=code,
        message=message,
        user_message=user_message,
        details=details if isinstance(details, dict) else {},
        retryable=retryable,
        status_code=exc.status_code,
        request_id_value=rid,
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", "unknown")
    return error_envelope(
        code="VALIDATION_ERROR",
        message="请求参数校验失败",
        user_message="请检查输入内容是否完整、格式是否正确。",
        details={"errors": exc.errors()},
        retryable=False,
        status_code=422,
        request_id_value=rid,
    )

app.include_router(api_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.app_version,
        "semantic_version": settings.app_semver,
        "runtime_mode": settings.runtime_mode,
    }
