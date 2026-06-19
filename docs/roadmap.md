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

## V3.x Next: Real Multimodal Pipelines

- Docling or equivalent parser for richer document formats.
- Visual description on top of the image OCR foundation.
- Subtitle export and richer video timeline controls.
- Shot-level scene segmentation and multi-keyframe indexing.
- Citation jump-to-page/timestamp/frame behavior.

## V5: Code Repository And Project Memory

- Git repository sync.
- Code file parsing and module explanation.
- Error archive and repair notes.
- Project version diffs and technical storytelling.

## V6: Interview And Portfolio System

- Project interview expression generation.
- Knowledge-point follow-up cards.
- Portfolio page and project story line.

## V7: Business Brain Integration

- Connect Business Growth Engine materials.
- Business document analysis, plan generation and review memory.
