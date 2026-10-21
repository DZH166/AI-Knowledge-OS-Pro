# V4.8 Request Cache Report

V4.8 adds a small browser-side request cache for repeated read endpoints. The goal is perceived speed and duplicate-request control, not fake backend acceleration.

## Implemented

- `frontend/services/request-cache.ts` tracks TTL cache entries, in-flight requests and recent cache metrics.
- `frontend/services/api.ts` adds request IDs, timeout handling, `x-client-cache-status` and GET-only TTL cache/dedupe behavior.
- Cached methods include Dashboard, System Status, Observability, Performance, Learning Dashboard and Portfolio Summary.
- Mutations clear cached reads to avoid stale UI after write operations.
- `scripts/check_request_cache.py` verifies cache wiring and performance panel integration.

## Boundaries

- Only GET requests with `ttlMs` participate in cache/dedupe.
- `forceRefresh` bypasses cached reads and records refresh metrics.
- Provider responses are not fabricated; missing provider keys still return NOT_CONFIGURED-style errors.

## Verification So Far

- `python scripts/check_request_cache.py`: passed.
- `python -m pytest backend/tests/test_v4_8_request_cache_static.py`: passed.

