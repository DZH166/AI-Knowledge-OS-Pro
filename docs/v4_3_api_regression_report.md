# V4.3 API Regression Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 adds API-level regression coverage for the release-ready demo surface and provider-boundary behavior.

## Tests Added

- `backend/tests/test_v4_3_api_regression.py`

## Covered API Areas

- `/health`
- `/api/dashboard/summary`
- `/api/system/status`
- `/api/media/sources`
- `/api/ingestion-jobs`
- `/api/learning/logs`
- `/api/chat/history`
- `/api/chat/ask` missing LLM provider refusal
- `/api/learning/from-source` source-based learning action
- `/api/portfolio/summary`

## Verification

Targeted V4.3 API/provider tests:

```text
7 passed, 2 warnings
```

Full backend test suite:

```text
70 passed, 9 warnings
```

## Boundary

The chat refusal test uses a real project `ConfigurationError` with code `LLM_NOT_CONFIGURED`. It does not mock a successful answer or bypass the real-mode refusal boundary.
