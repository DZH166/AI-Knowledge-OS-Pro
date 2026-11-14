# V3.6 Acceptance Report

## Scope

V3.6 unifies document and media processing under the durable task engine, improves media citation navigation, and adds deterministic learning artifacts created only from real source text.

## Delivered

- Added Alembic revision `0006_v3_6_unified_media_tasks`.
- Made `ingestion_jobs.document_id` nullable and added `source_id` plus `target_type`.
- Added unified task dispatch for document and media jobs.
- Added media processing jobs for image OCR, image visual description, screenshot analysis, audio transcription, video transcription, video keyframes, keyframe OCR, visual description, and full video pipeline.
- Added multi-keyframe extraction and real provider-backed visual description plumbing.
- Added `learning_artifacts` audit table and source/document chunk based learning artifact creation.
- Added chat citation `source_id` and `document_id` fields.
- Added frontend citation links to document chunks and media timestamps.
- Rebuilt media detail page with player seek, transcript highlighting, keyframe timeline, task actions, selected chunk evidence, and learning artifact actions.
- Updated Task Center to distinguish document and media jobs.
- Unified product/backend/package version reporting as `V3.6` and `3.6.0`.
- Added a portfolio README, seven reproducible synthetic screenshots, demo instructions and GitHub governance files.
- Added GitHub Actions coverage for backend, frontend, migration, encoding, version and release safety checks.
- Added UTF-8, version consistency and release archive verification scripts.
- Corrected the public media-task response contract so nullable `document_id`, `source_id` and `target_type` serialize without API failures.

## Real-Mode Boundary

- Missing transcription provider keys return `TRANSCRIPTION_NOT_CONFIGURED`.
- Missing OCR or vision provider keys return explicit NOT_CONFIGURED-style errors.
- Screenshot analysis does not create an error archive unless OCR evidence contains explicit error markers.
- Learning artifacts are refused when no real document chunk or active multimodal text exists.

## Verification

```text
python -m compileall backend/app backend/alembic scripts
Result: passed

python\python.exe -m pytest
Result: 41 passed, 18 warnings

python\python.exe -m alembic upgrade head
python\python.exe -m alembic current
Result: 0006_v3_6_unified_media_tasks (head)

frontend typecheck
Result: passed

frontend production build
Result: passed

encoding, version and release checks
Result: passed; release inspection reported 199 files, forbidden=0, missing=0
```

The isolated showcase API returned HTTP 200 for dashboard summary, ingestion jobs, learning logs, chat history and chat sessions. Seven `1440 x 960` screenshots were regenerated; the capture guard found no `Failed to fetch` page and rejected blank-image output during validation.

## Boundaries

- Subtitle export is not implemented.
- Full shot-level scene segmentation is not implemented.
- Vision description depends on a configured real provider.
- Historical learning logs remain append-only and were not rewritten.
- Showcase screenshots use synthetic persisted results and are not evidence that an unconfigured provider ran locally.
- Release packaging uses Git-tracked files and excludes ignored/nested repositories as well as local agent metadata.
