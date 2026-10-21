# V4.4 Observability Report

## Scope

V4.4 adds lightweight runtime observability for demo review and local debugging.

## Implemented

- Request ID middleware records recent API requests in a bounded in-process ring buffer.
- Error responses include `x-error-code`.
- System service exposes recent requests, tasks, retrievals, provider status and error categories.
- FastAPI routes:
  - `GET /api/system/observability`
  - `GET /api/system/observability/recent-requests`
  - `GET /api/system/observability/recent-tasks`
  - `GET /api/system/observability/recent-retrievals`
  - `GET /api/system/observability/provider-status`
- Frontend page: `/system/observability`

## Backend Contract Tests

- `backend/tests/test_v4_4_observability.py`

## Limit

The request buffer is process-local and resets on API restart. Long-term metrics storage and distributed tracing remain future work.
