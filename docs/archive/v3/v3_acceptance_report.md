# V3 Acceptance Report

Date: 2026-06-18

## Scope

V3 is an incremental upgrade on top of V2.5. It does not rebuild the project, delete existing SQLite data, or overwrite old learning archives.

This stage focuses on:

- Redis/RQ background task engine.
- Durable ingestion job events.
- Task retry, cancel, stale heartbeat interruption and Worker recovery foundation.
- V3 Alembic migration with multimodal schema foundation.
- Task Center frontend page.
- System diagnostics for Redis and Worker.
- Frontend API error parsing and Chinese UI cleanup for shared shell/upload/system/task surfaces.
- V3 documentation, learning package script and release readiness.

## Completed

- Added Redis service to `docker-compose.yml`.
- Added `redis` and `rq` dependencies.
- Added task broker and Worker entrypoint:
  - `backend/app/services/task_broker.py`
  - `backend/app/tasks/ingestion_tasks.py`
  - `backend/app/worker.py`
- Extended `IngestionJob` and added `JobEvent`.
- Added V3 multimodal foundation models and migration:
  - `Source`
  - `SourceRevision`
  - `MediaAsset`
  - `TranscriptSegment`
  - `VisualFrame`
  - `MultimodalChunk`
  - `CitationLocator`
  - `IndexRevision`
- Added `/api/ingestion-jobs/{job_id}/events`.
- Converted document upload/retry/reparse/reindex APIs to enqueue background work.
- Added `/tasks` frontend page.
- Added Redis and Worker diagnostics to `/api/system/status` and `/system`.
- Rewrote `scripts/generate_learning_package.py` so drafts are based on real changes instead of hardcoded V2.5 content.
- Updated README, architecture, roadmap, ingestion flow and env examples for V3.

## Verified Commands

```powershell
python -m compileall backend/app backend/alembic scripts
```

Result: passed.

```powershell
python -m pytest
```

Result: 19 passed, 5 warnings.

```powershell
python -m alembic upgrade head
python -m alembic current
```

Result: current revision is `0004_v3_task_multimodal_foundation`.

```powershell
npm run typecheck
npm run build
```

Result: passed. Next.js build includes `/tasks`.

## Database Check

Current local SQLite:

- `learning_logs`: 2 records preserved.
- `knowledge_spaces`: 0 records.
- `documents`: 0 records.
- `ingestion_jobs`: 0 records.
- `job_events`: 0 records.
- `sources`: 0 records.
- `multimodal_chunks`: 0 records.
- Alembic revision: `0004_v3_task_multimodal_foundation`.

## Known Boundaries

- Real OCR is not implemented yet.
- Real audio transcription is not implemented yet.
- Real video keyframe/timeline processing is not implemented yet.
- V3 has the database and product foundation for multimodal sources, but runtime multimodal extraction will be implemented in a later V3.x stage.

## Next Recommended Stage

Implement one real multimodal pipeline at a time:

1. Image OCR and screenshot error extraction.
2. Audio transcription with timestamped segments.
3. Video audio extraction, keyframes and timestamp citations.
4. Source detail pages for image/audio/video.
