# AI Knowledge OS Pro Roadmap

## V1: Foundation RAG

- Knowledge spaces.
- txt/md/pdf upload, parsing, chunking.
- Embedding to Qdrant.
- RAG question answering with citations and history.
- Version learning archive.

## V2: Real Mode, Governance, Learning Coach

- Explicit real/demo runtime modes.
- Provider adapter layer for LLM and embedding.
- System diagnostics and service tests.
- Alembic V1 baseline and V2 migration.
- Ingestion jobs, deduplication, delete/retry/reparse/reindex.
- Embedding fingerprint and index compatibility checks.
- RAG refusal, score threshold, citation ids, confidence fields.
- Learning packages, knowledge points, cards, quizzes, notes and progress.
- Release zip and stage delivery log.

## V2.5: Product Learning Workspace

- Productized navigation and AppShell.
- First-use onboarding workflow.
- Dashboard as a learning workspace.
- Multi-file upload queue and task progress polling.
- Document management search, filters, tags and bulk actions.
- Document detail with overview, structure, chunks, jobs and index metadata.
- PDF page metadata and Markdown heading path through chunks and citations.
- Multi-turn chat sessions and citation drawer.
- Citation authenticity validation: no forced first citation.
- Learning dashboard, cards, quizzes, notes and review-needed state.
- Git-change-based learning package draft generation.
- V2.5 learning archive, stage delivery record and release zip.

## V3: Stable Task Engine And Multimodal Foundation

- Redis/RQ task broker and independent Worker.
- Persistent task events, progress, worker id, heartbeat, duration, retry and cancellation state.
- Task Center page with job list and event timeline.
- System Status page with Redis and Worker diagnostics.
- Alembic V3 migration with upgrade/downgrade checks.
- Unified multimodal schema foundation: Source, SourceRevision, MediaAsset, TranscriptSegment, VisualFrame, MultimodalChunk, CitationLocator and IndexRevision.
- V3 release learning package based on real Git changes.

## V3.1: Image Metadata Ingestion

- Image upload for png, jpg, jpeg, webp and bmp.
- Pillow-based real image width, height and format inspection.
- SHA256 duplicate detection inside a knowledge space.
- Source, SourceRevision and MediaAsset records for uploaded images.
- Metadata-only boundary: OCR and visual description are explicitly marked as not configured.
- Media Library page and media source detail page.
- V3.1 learning archive, acceptance report and release package.

## V3.2: Configurable Image OCR

- OpenAI-compatible vision OCR provider configuration.
- `POST /api/media/sources/{id}/ocr` for explicit image OCR execution.
- No fake OCR: unconfigured OCR returns `OCR_NOT_CONFIGURED`.
- OCR text saved as `MultimodalChunk`.
- Image source locator saved as `CitationLocator`.
- OCR chunks embedded and upserted into Qdrant for Chat retrieval.
- System Status page includes OCR diagnostics.
- Image detail page displays OCR action, status and recognized chunks.

## V3.3: Screenshot Error Archive

- Deterministic extraction of explicit exception names, HTTP statuses and error markers from OCR text.
- `ErrorArchive` model and Alembic `0005_v3_3_error_archive` migration.
- Source/chunk traceability, confidence, severity, language and stack excerpt.
- Duplicate fingerprint protection and lifecycle states: open, investigating, resolved and ignored.
- Error Archive page and source-image archive action.
- Clear boundary: diagnostic suggestions are not fabricated root-cause claims.

## V3.4: Audio Transcription And Timestamp Citations

- MP3, WAV and M4A upload with real duration metadata.
- Configurable OpenAI-compatible transcription provider.
- No fake transcript: unconfigured provider returns `TRANSCRIPTION_NOT_CONFIGURED`.
- Timestamped `TranscriptSegment`, `MultimodalChunk` and `CitationLocator` records.
- Qdrant indexing and RAG citations with start/end milliseconds.
- Audio player and transcript timeline on source detail pages.
- System diagnostics for transcription provider configuration.

## V3.5: Video Pipeline And Timestamp Citations

- MP4 and MOV upload with real duration, width, height and audio-track metadata from FFmpeg/ffprobe.
- Original video stored as `MediaAsset`.
- At least one real keyframe extracted and stored as `VisualFrame` plus keyframe `MediaAsset`.
- Video detail page includes player, metadata, keyframe preview, real transcription action and transcript timeline.
- Video transcription extracts WAV audio, calls the configured real provider, and refuses with `TRANSCRIPTION_NOT_CONFIGURED` when absent.
- Timestamped video `TranscriptSegment`, `MultimodalChunk`, `CitationLocator` and `IndexRevision` records.
- Qdrant indexing and RAG citations with `source_type=video`, `start_ms` and `end_ms`.

## V3.6: Unified Multimodal Knowledge Workflow

- Image, audio and video operations run through the Redis/RQ task center.
- Media jobs expose progress, events, retry, cancel, reprocess and result navigation.
- Audio/video citations deep-link to timestamps and highlight transcript evidence.
- Video detail combines keyframes, transcript chunks, notes, questions and learning actions.
- Multiple keyframes persist `timestamp_ms` and support timeline seeking.
- Source-derived knowledge points, cards, quizzes, notes and interview expressions retain evidence ownership.
- GitHub portfolio README, reproducible synthetic screenshots, CI, governance files, encoding checks and release safety checks.
- V3.6 learning package generation uses real Git changes, routes, dependencies and verification reports.

## Future Media Understanding

- Docling or equivalent parser for richer document formats.
- Subtitle export and richer video timeline controls.
- Shot-level scene segmentation and semantic keyframe retrieval.
- More complete PDF page/section navigation and frame-level citation highlighting.

## V4.0 Target: Code Repository And Project Memory

- Git repository sync.
- Code file parsing and module explanation.
- Error archive and repair notes.
- Project version diffs and technical storytelling.

## V4.0 Target: Interview And Portfolio System

- Project interview expression generation.
- Knowledge-point follow-up cards.
- Portfolio page and project story line.

## Future: Business Brain Integration

- Connect Business Growth Engine materials.
- Business document analysis, plan generation and review memory.

## V3.7: GitHub Showcase Demo And Engineering Trust

- Professional GitHub README with honest capability matrix and demo path.
- `scripts/setup_demo.py`, `scripts/seed_demo_data.py` and `scripts/check_demo_ready.py` for isolated synthetic demo setup.
- Release dry-run, secret scan and repository cleanliness checks.
- CI quality job runs encoding, version, secret, repo-clean and release dry-run checks.
- Mermaid architecture diagrams and resume/interview pitch documentation.
- System Status capability matrix groups direct, local-service, provider-backed, demo-only and planned features.
- V3.7 learning package documents open-source project hygiene, CI/CD and portfolio presentation.

## V3.8: GitHub Portfolio Demo Docs And Reset Workflow

- Version unified to `V3.8 / 3.8.0`.
- Added quickstart, demo mode, local development, environment variables, release, versioning and commit convention docs.
- Added storyboard and interview QA docs for GitHub and interview explanation.
- Added V4.0 design notes for RAG evaluation, hybrid retrieval, code repository ingestion, portfolio system, interview system, observability and performance.
- Added `scripts/reset_demo_data.py` to safely rebuild the isolated synthetic demo database.
- Preserved demo/real boundaries: synthetic demo data is labelled and missing providers must not be faked.

## V3.9 In Progress: Product Experience And Quality Gates

- Extend `scripts/evaluate_rag.py --demo` beyond seeded evidence-chain checks into richer retrieval quality reporting.
- Add lightweight UI smoke checks for Dashboard, Upload, Tasks, Chat, Media, Learning and System Status.
- Improve provider diagnostics with safer setup hints and copyable env template guidance.
- Improve task center failure recovery, retry/cancel clarity and media result navigation.

## V4.0 Next: Knowledge-Enhanced Portfolio Edition

- Record and commit a short demo GIF after final UI confirmation.
- Add hybrid retrieval and rerank fallback.
- Add code repository ingestion with file/line citation locators.
- Add portfolio generation pages and APIs.
- Add mock interview sessions and saved feedback.
- Add observability page and structured trace reports.
