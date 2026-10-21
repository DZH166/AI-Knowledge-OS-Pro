# V3 Ingestion Job Flow

V3 moves ingestion from request-bound work to Redis/RQ-backed background jobs. The API creates durable records in SQLite, writes a queued event, dispatches an RQ job, and returns `job_id` to the frontend.

## Flow

1. User uploads a txt/md/pdf file.
2. API validates file type, size and duplicate hash.
3. API creates `Document` and `IngestionJob`.
4. API writes a `JobEvent` and enqueues `app.tasks.ingestion_tasks.run_ingestion_job`.
5. Worker claims the job and stores `worker_id`.
6. Worker parses, chunks, embeds and writes Qdrant points.
7. Each major step writes `JobEvent` and updates job progress.
8. Completion writes result JSON, duration and final status.
9. Failures write error code, error details and failed event.

## States

- `queued`: task is durable and waiting for Worker dispatch.
- `claimed`: Worker has picked up the job.
- `running`: document processing is active.
- `cancelling`: user requested cancellation while Worker is running.
- `cancelled`: job stopped at a safe cancellation checkpoint.
- `completed`: document is ready and indexed.
- `failed`: task ended with an error.
- `interrupted`: Worker heartbeat became stale and the job can be retried.

## Observability

The `/tasks` page reads:

- `GET /api/ingestion-jobs`
- `GET /api/ingestion-jobs/{job_id}`
- `GET /api/ingestion-jobs/{job_id}/events`

This makes the long-running AI ingestion pipeline visible to a learner: they can see parsing, chunking, embedding, indexing, errors and retries.

## Worker

Start a Worker:

```powershell
python -m app.worker
```

The Worker marks stale running jobs as interrupted on startup, then re-enqueues queued, retry-scheduled and interrupted jobs.

## Why This Matters

The V2.5 lightweight thread approach was easy to start but fragile: state could disappear on process restart, cancellation was partly in memory, and progress was less trustworthy. V3 stores task state and events in SQLite and uses Redis/RQ for dispatch, so recovery and diagnosis are much clearer.
