# Observability

Observability means the system can explain what happened, where it failed and how to recover.

## Implemented Baseline

- API response envelope includes `request_id`.
- Task model stores status, progress and job events.
- System status page shows configured capabilities and service checks.
- Provider missing states are intended to be explicit.

## Target V4.0 Fields

- `request_id`
- `task_id`
- `generation_id`
- `retrieval_trace_id`
- `error_code`
- `latency_ms`
- provider latency
- token usage when available
- task duration
- retrieval count
- citation validation status

## Target Page

```text
/system/observability
```

## UI Rule

Normal user screens should show understandable status and recovery actions. Advanced logs can be placed in a technical detail panel; raw debug JSON should not dominate the main UI.

## Current Status

- Foundation exists.
- Dedicated observability page and structured trace reports are planned.
