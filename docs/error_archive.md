# Screenshot Error Archive

## Purpose

V3.3 turns verified OCR text into a reusable error-learning record. The extractor is deterministic and explainable: it only creates an archive when OCR text contains an explicit exception name, HTTP status, or error marker. It does not invent a root cause.

## Pipeline

1. Upload an image and run real OCR from the media source detail page.
2. OCR text is stored as an active `MultimodalChunk`.
3. `POST /api/errors/from-source/{source_id}` scans the active OCR chunks.
4. The extractor detects an explicit error type and message.
5. The system stores `ErrorArchive` with source/chunk links, stack excerpt, confidence, severity, language and suggested diagnostic steps.
6. Repeated extraction of the same source/error fingerprint returns the existing archive.
7. Users can move the archive through `open`, `investigating`, `resolved` or `ignored`.

## Detection Boundary

The deterministic extractor currently recognizes:

- Exception/error/warning class names such as `ModuleNotFoundError`, `TypeError` and `ConnectionError`.
- HTTP status markers such as `HTTP 404` and `HTTP 500`.
- Explicit lines beginning with `error`, `fatal` or `failed`.

If no explicit marker exists, the API refuses to create an archive. Suggested actions are diagnostic checklists, not asserted root causes.

## APIs

- `GET /api/errors`
- `POST /api/errors/from-source/{source_id}`
- `GET /api/errors/{archive_id}`
- `PATCH /api/errors/{archive_id}`

## Data Safety

- V3.3 adds `error_archives` through Alembic revision `0005_v3_3_error_archive`.
- Existing sources, OCR chunks and learning archives are not overwritten.
- The migration includes downgrade support; rollback verification runs on a temporary database, not the real project database.
