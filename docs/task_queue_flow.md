# Task Queue Flow

## Implemented Flow

```text
API request
-> create IngestionJob
-> enqueue Redis/RQ work when available
-> worker updates status, progress and JobEvent records
-> frontend Task Center polls job state
-> user opens result link, retries or cancels
```

## Supported Task Targets

- Document ingestion.
- Image OCR and visual processing.
- Audio transcription.
- Video transcription and keyframe processing.

## Failure Behavior

- Provider missing: explicit NOT_CONFIGURED-style failure.
- Worker/service unavailable: task should expose failure state or pending state instead of silent success.
- Retry should create a recoverable path without deleting source records.

## Planned V4.0 Work

- More detailed task event pagination.
- Better observability fields.
- Lightweight UI smoke tests for retry/cancel/result navigation.
