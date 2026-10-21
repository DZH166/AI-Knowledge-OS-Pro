# Architecture

AI Knowledge OS Pro currently uses a Next.js frontend, FastAPI backend, SQLite relational store, Qdrant vector store, and Redis/RQ task engine. V4.4 is an evidence and observability pass after the V4.3 release-usability checkpoint. It does not add fake provider-backed capabilities; it makes demo flows, citation jumps, provider readiness and runtime failures easier to validate and explain.

## Backend

- FastAPI routers expose public APIs under `/api`.
- SQLAlchemy models store knowledge spaces, documents, chunks, QA logs, chat sessions, ingestion jobs, job events, learning entities, and multimodal source foundations.
- Alembic owns schema upgrades. Current head: `0006_v3_6_unified_media_tasks`.
- Provider adapters isolate LLM, embedding and image OCR calls from RAG business logic.
- `DocumentIngestionService` owns upload validation, parsing, chunking, embedding, Qdrant upsert, retry, cancel and delete behavior.
- Redis/RQ dispatches ingestion jobs to an independent Worker.
- `JobEvent` records durable task progress and errors, so UI and recovery logic do not depend on in-memory thread state.
- `RAGService` owns query checks, index compatibility, retrieval, prompt construction, citation validation, response generation and history.
- Learning services own version learning packages, knowledge points, cards, quizzes, notes and Markdown export.
- `ErrorArchiveService` extracts explicit error markers from active image OCR chunks and preserves source/chunk traceability.
- `TranscriptionProvider` isolates OpenAI-compatible audio/video transcription; `MediaService` persists timestamped segments, video keyframes and indexes transcript chunks for RAG.

## Frontend

- Next.js App Router renders product pages.
- `frontend/services/api.ts` centralizes API calls and structured error handling.
- `AppShell` organizes navigation into learning workspace, knowledge management, AI assistant, learning growth and system.
- `/tasks` shows ingestion jobs, Worker state, progress and event timeline.
- `/system` shows runtime mode, DB, Redis, Worker, Qdrant, LLM, Embedding, OCR and index diagnostics.
- `/system/observability` shows recent request IDs, task events, retrieval traces, provider status and error categories from real API/database state.

## Data Stores

- SQLite stores relational product data for V1-V3.6 local use.
- Qdrant Server stores chunk vectors and retrieval payload.
- Redis stores RQ queue state for background task dispatch.
- Uploaded files live under `backend/storage/uploads` by default and are excluded from release archives.

## Multimodal Foundation

V3 adds schema foundation for multimodal sources:

- `Source`: one logical uploaded or collected source.
- `SourceRevision`: staging/active revisions for safe reparse and future atomic switching.
- `MediaAsset`: original or derived media files.
- `TranscriptSegment`: audio/video transcript segments with timestamps.
- `VisualFrame`: video keyframes and future OCR/visual frame records.
- `MultimodalChunk`: unified searchable chunks across text, image, audio and video-derived content.
- `CitationLocator`: structured source locator for pages, headings, timestamps and frames.
- `IndexRevision`: embedding/index metadata for compatibility checks.

V3.2 adds a real OCR provider boundary for images:

- OCR is explicit and configurable through `OCR_PROVIDER`, `OCR_API_KEY`, `OCR_BASE_URL` and `OCR_MODEL`.
- When OCR is not configured, the system reports `OCR_NOT_CONFIGURED` and does not generate fake text.
- When OCR succeeds, recognized text is stored as `MultimodalChunk`, linked with `CitationLocator`, embedded, and upserted into Qdrant for Chat retrieval.

## Error Archive

V3.3 adds `ErrorArchive` as a separate product entity rather than placing mutable learning state inside Source metadata. The archive stores error type, message, stack excerpt, language, severity, confidence, diagnostic checklist, tags, resolution notes and lifecycle status. It references both the source image and the OCR chunk that produced the record.

## Audio Transcription

V3.4 reuses the existing multimodal schema without another migration. Audio upload creates Source/SourceRevision/MediaAsset records. Real transcription creates TranscriptSegment, MultimodalChunk, CitationLocator and IndexRevision records. Timestamp fields travel through the Qdrant payload, RAG response and frontend citation panel.

## Video Pipeline

V3.5 reuses the existing multimodal schema without another migration. Video upload reads real duration, width, height and audio-track metadata with FFmpeg/ffprobe, stores the original video, and extracts at least one keyframe into `VisualFrame` and `MediaAsset`. Video transcription first verifies a real transcription provider is configured, extracts a WAV audio track, calls the provider, then creates video `TranscriptSegment`, `MultimodalChunk`, `CitationLocator` and `IndexRevision` records. Chat citations carry `source_type=video` plus `start_ms`/`end_ms`.

## V3.6 Unified Media Tasks And Learning Artifacts

V3.6 adds Alembic revision `0006_v3_6_unified_media_tasks`. `ingestion_jobs.document_id` is nullable, media jobs store `source_id`, and `target_type` distinguishes document jobs from media jobs. The same Task Center can now observe, retry and cancel image OCR, image visual description, screenshot analysis, audio transcription, video transcription, keyframe extraction, keyframe OCR, visual description and full video pipeline tasks.

V3.6 also adds `learning_artifacts` as an audit table for source-derived study material. Learning artifacts are deterministic transformations of existing document chunks or active multimodal chunks; empty media is refused rather than filled with fake notes. Chat citations now carry explicit `source_id` and `document_id`, so frontend citations can deep-link to document chunks or media timestamps.

The public task contract mirrors the nullable database ownership model: document jobs return `document_id`, media jobs return `source_id`, and both expose `target_type`. This prevents response validation from turning valid media jobs into API failures.

## Portfolio And Release Verification

- GitHub Actions runs backend compilation/tests/migrations, frontend typecheck/build, UTF-8 checks, version checks and release archive inspection.
- `scripts/seed_showcase.py` creates only an isolated synthetic database whose filename must contain `showcase`.
- `scripts/check_demo_ready.py`, `scripts/evaluate_rag.py` and `scripts/check_full_regression.py` validate synthetic demo readiness, RAG evidence plumbing and full regression coverage.
- `scripts/check_docs_links.py`, `scripts/check_readme_assets.py` and `scripts/check_all.py` validate docs integrity, README media safety and quality-gate orchestration.
- `scripts/check_e2e.py` validates optional Playwright E2E scaffolding, and `scripts/evaluate_providers.py --dry-run` reports provider readiness without external calls.
- `scripts/capture_showcase.py` waits for real page data and rejects failed or blank captures before writing the seven README screenshots.
- `scripts/check_release.py` validates the generated zip against the same exclusions used by the release builder.
- Real `.env` files, SQLite databases, uploads, logs, dependencies, build caches and previous releases are excluded from release artifacts.

## V4.4 Runtime Observability And Demo E2E

V4.4 adds a lightweight observability layer without a new migration. `RequestIdMiddleware` records a bounded in-process request history, error responses expose `x-error-code`, and the system service combines recent request, task, retrieval, provider and error-category views. The frontend observability page consumes these endpoints directly.

The browser E2E layer is intentionally optional. The repository ships Playwright config and specs for demo smoke, citation jumps and observability, while `npm run test:e2e` skips honestly when Playwright or browser binaries are not installed. This keeps public CI free of paid provider/browser assumptions while preserving a runnable path for local or hosted E2E environments.

## V4.1 Architecture Consolidation

V4.1 adds a repository-wide code inventory, dead-code review plan, archive structure and module-boundary docs. Historical reports are preserved under `docs/archive`, while active architecture, setup, release and learning docs remain in `docs/`.

New V4.1 architecture references:

- `docs/backend_architecture.md`
- `docs/frontend_architecture.md`
- `docs/module_boundaries.md`
- `docs/scripts_reference.md`
- `docs/v4_1_code_inventory.md`
- `docs/v4_1_cleanup_report.md`
