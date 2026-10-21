# Observability

Observability means the system can explain what happened, where it failed and how to recover.

## Implemented Baseline

- API response envelope includes `request_id`.
- Task model stores status, progress and job events.
- System status page shows configured capabilities and service checks.
- Provider missing states are intended to be explicit.
- Hybrid retrieval exposes citation-level trace fields: `dense_score`, `keyword_score`, `rerank_score`, `final_score`, `retrieval_reason` and `citation_ready`.
- `/api/system/observability` returns recent request, task, retrieval, provider and error-category signals.
- `/system/observability` renders the runtime snapshot instead of a static placeholder.
- API error envelopes include an `x-error-code` response header for faster triage.

## V4.5 Fields

- `request_id`
- `task_id`
- `retrieval_trace_id`
- `error_code`
- `latency_ms`
- provider configuration status
- task duration
- retrieval count
- citation validation status where present in QA logs

## Runtime Routes

```text
/api/system/observability
/api/system/observability/recent-requests
/api/system/observability/recent-tasks
/api/system/observability/recent-retrievals
/api/system/observability/provider-status
/system/observability
```

## UI Rule

Normal user screens should show understandable status and recovery actions. Advanced logs can be placed in a technical detail panel; raw debug JSON should not dominate the main UI.

## Current Status

- V4.4 implemented a lightweight in-process request ring buffer and DB-backed task/retrieval snapshots.
- V4.5 adds strict live browser coverage for the observability page through `scripts/run_demo_e2e.py --strict` and the `live-e2e` GitHub Actions job.
- The request buffer is intentionally process-local; it resets when the API process restarts.
- Provider token usage, distributed tracing and long-term metrics storage remain planned.
