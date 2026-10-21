# V4.8 Runtime Performance Report

V4.8 adds real runtime performance observability without recording request bodies, API keys, uploaded file contents or full user prompts.

## Backend Scope

- `backend/app/services/performance_service.py` stores an in-process rolling buffer of request metadata.
- `backend/app/core/responses.py` records API path, method, status, latency, request id, cache status and error code after each `/api/*` request.
- `backend/app/api/routes_performance.py` exposes:
  - `GET /api/system/performance`
  - `GET /api/system/performance/recent`
  - `GET /api/system/performance/slow`
  - `GET /api/system/performance/summary`

## Browser Page Timing

- `frontend/services/page-metrics.ts` records the initial browser navigation timing with `PerformanceNavigationTiming`.
- `frontend/components/AppShell.tsx` marks main-navigation clicks and records route-switch duration when the next route becomes active.
- These metrics stay in the browser session and are displayed on `/system/performance`; they are not posted to the backend and do not include user input, prompts, file content or secrets.

## Privacy Boundary

- Query strings are stripped before storage.
- Secret-like request bodies are never read by this service.
- Provider keys, uploads, prompts and stack traces are not recorded.
- The buffer resets when the API process restarts.

## Verification

- `python -m pytest backend/tests/test_v4_8_performance_observability.py backend/tests/test_v4_8_request_cache_static.py`: passed.
- Frontend typecheck and production build passed after adding the browser page timing panel.
