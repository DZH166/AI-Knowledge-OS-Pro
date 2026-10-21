from __future__ import annotations

from typing import Any
import time
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json

from app.core.errors import ServiceError
from app.core.observability import observability_store
from app.services.performance_service import performance_service


def request_id() -> str:
    return uuid4().hex


def envelope(data: Any = None, request_id_value: str | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "request_id": request_id_value or request_id(),
    }


def error_envelope(
    *,
    code: str,
    message: str,
    status_code: int,
    request_id_value: str,
    user_message: str | None = None,
    details: dict | None = None,
    retryable: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers={"x-error-code": code},
        content={
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "user_message": user_message or message,
                "details": details or {},
                "request_id": request_id_value,
                "retryable": retryable,
            },
            "request_id": request_id_value,
        },
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or request_id()
        request.state.request_id = rid
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = int((time.perf_counter() - started) * 1000)
            if request.url.path.startswith("/api/"):
                performance_service.record_request(
                    request_id=rid,
                    method=request.method,
                    path=request.url.path,
                    status_code=500,
                    latency_ms=latency_ms,
                    error_code="UNHANDLED_EXCEPTION",
                    cache_status=request.headers.get("x-client-cache-status"),
                )
            raise
        latency_ms = int((time.perf_counter() - started) * 1000)
        response.headers["x-request-id"] = rid
        response.headers["x-request-latency-ms"] = str(latency_ms)
        if request.url.path.startswith("/api/"):
            error_code = response.headers.get("x-error-code")
            observability_store.record_request(
                request_id=rid,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
                error_code=error_code,
            )
            performance_service.record_request(
                request_id=rid,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
                error_code=error_code,
                cache_status=response.headers.get("x-cache-status") or request.headers.get("x-client-cache-status"),
            )
        return response


class ApiEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/") or response.status_code >= 400:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        if not body:
            return Response(status_code=response.status_code, headers=dict(response.headers))

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers))

        if isinstance(payload, dict) and {"success", "data", "error", "request_id"}.issubset(payload.keys()):
            wrapped = payload
        else:
            rid = getattr(request.state, "request_id", request.headers.get("x-request-id") or request_id())
            wrapped = envelope(payload, rid)

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return JSONResponse(content=wrapped, status_code=response.status_code, headers=headers)


def service_error_response(request: Request, exc: ServiceError) -> JSONResponse:
    rid = getattr(request.state, "request_id", request_id())
    return error_envelope(
        code=exc.code,
        message=exc.message,
        user_message=exc.user_message,
        details=exc.details,
        retryable=exc.retryable,
        status_code=exc.status_code,
        request_id_value=rid,
    )
