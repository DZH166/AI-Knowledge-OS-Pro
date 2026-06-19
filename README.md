# AI Knowledge OS Pro

AI Knowledge OS Pro is a personal AI learning operating system for AI application development learners. It combines a project knowledge base, RAG question answering, version learning archives, and a learning coach workflow.

V3.6 upgrades the V2.5 product experience into a task-engine-driven multimodal knowledge learning OS. The current implementation includes Redis/RQ background tasks, persistent task events, system diagnostics, unified multimodal sources, image OCR, screenshot error archives, timestamped audio/video transcription, video keyframes, media-task orchestration, citation jump links, and learning artifacts generated from real source chunks.

## Current V3.6 Capabilities

- Knowledge spaces, txt/md/pdf upload, parsing, chunking, embedding, Qdrant indexing, RAG answers, citations, and QA history.
- Real/demo runtime modes. Real mode does not silently fall back to fake answers.
- SQLite with Alembic migrations through `0006_v3_6_unified_media_tasks`.
- Redis/RQ task broker and independent Worker entrypoint for ingestion jobs.
- Persistent `job_events` with task steps, progress, messages, errors, worker metadata, duration, retry and cancel state.
- Task Center page at `/tasks` for job list, progress, event timeline, retry and cancel.
- System Status page with DB, Redis, Worker, Qdrant, Collection, LLM, Embedding and index diagnostics. Secrets are masked.
- Multimodal foundation tables: `sources`, `source_revisions`, `media_assets`, `transcript_segments`, `visual_frames`, `multimodal_chunks`, `citation_locators`, `index_revisions`.
- Image metadata ingestion for png/jpg/jpeg/webp/bmp: validates type and size, deduplicates by SHA256, reads width/height/format with Pillow, stores `Source` and `MediaAsset`, and clearly marks OCR/vision as not configured.
- Media Library page at `/media` and source detail page at `/media/sources/[id]`.
- Configurable image OCR through an OpenAI-compatible vision endpoint. Without `OCR_API_KEY`, OCR is blocked with `OCR_NOT_CONFIGURED` and no fake text is generated.
- OCR text is stored as `MultimodalChunk`, linked with `CitationLocator`, embedded, and searchable from Chat with citations.
- Screenshot error extraction creates traceable `ErrorArchive` records from explicit OCR error markers, with confidence, stack excerpt, diagnostic checklist and resolution status.
- Error Archive page at `/errors`; image details can create or reuse an archive without duplicating the same error.
- MP3/WAV/M4A upload with real duration metadata, configurable transcription, timestamped segments, Qdrant indexing and audio citations.
- Audio source details include a player and transcript timeline; unconfigured transcription returns `TRANSCRIPTION_NOT_CONFIGURED`.
- MP4/MOV upload with real duration, width, height and audio-track metadata from FFmpeg/ffprobe.
- Video upload extracts and stores at least one real keyframe as `VisualFrame` and `MediaAsset`.
- Video source details include a player, keyframe preview, metadata, real transcription action and transcript timeline.
- Video transcription extracts the audio track, calls the configured real transcription provider, stores `TranscriptSegment`, `MultimodalChunk`, `CitationLocator` and `IndexRevision`, and returns RAG citations with video timestamps.
- Unified media processing tasks for image OCR/visual analysis, screenshot analysis, audio transcription, video transcription, video keyframes, keyframe OCR, visual descriptions and full video pipeline.
- Task Center supports both document and media jobs with retry/cancel and target-aware result links.
- Media detail pages support player seek, transcript segment highlighting, keyframe timeline browsing, citation timestamp jumps and chunk selection.
- Chat citations include explicit `source_id`/`document_id`; media citations link to `/media/sources/{id}?t=...&chunk=...`.
- Learning artifacts can be created from real document or multimodal chunks as knowledge points, cards, quizzes, notes and interview expressions. Empty media with no real text is refused.
- Version learning archive in `docs/learning_log.md` and stage delivery archive in `docs/stage_delivery_log.md`.
- Release packaging script that excludes dependencies, caches, secrets, SQLite DBs, uploads, logs and old release artifacts.

## Tech Stack

- Frontend: Next.js App Router, React, TypeScript, lucide-react, react-markdown.
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, pytest.
- Task queue: Redis + RQ Worker.
- Database: SQLite for local V1-V3.6, with PostgreSQL reserved for future migration.
- Vector database: Qdrant Server.
- Model API: OpenAI-compatible chat completions and embeddings.

## Quick Start

1. Copy environment files:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

2. Start infrastructure:

```powershell
docker compose up -d qdrant redis
```

3. Create and activate a Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

4. Apply database migrations:

```powershell
python -m alembic upgrade head
```

5. Start the backend API:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

6. Start a Worker in another terminal:

```powershell
python -m app.worker
```

7. Start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

Backend OpenAPI: `http://localhost:8000/docs`

## Runtime Modes

Default is real mode:

```env
DEMO_MODE=false
LLM_API_KEY=
EMBEDDING_API_KEY=
```

Real mode blocks real model calls when model keys are missing. It does not silently generate fake answers.

Image OCR is also explicit:

```env
OCR_PROVIDER=openai_compatible_vision
OCR_API_KEY=
OCR_BASE_URL=https://api.openai.com/v1
OCR_MODEL=gpt-4o-mini
```

If OCR is not configured, image detail pages show the missing configuration and the backend returns `OCR_NOT_CONFIGURED`.

Audio and video transcription are configured through the same real provider:

```env
TRANSCRIPTION_PROVIDER=openai_compatible_audio
TRANSCRIPTION_API_KEY=
TRANSCRIPTION_BASE_URL=https://api.openai.com/v1
TRANSCRIPTION_MODEL=whisper-1
```

For local demos without API keys:

```env
DEMO_MODE=true
```

Demo mode is shown in the product UI and system status page.

## Worker Notes

Uploads and document actions create ingestion jobs. Redis/RQ stores the job dispatch, while SQLite stores durable job status and events.

Run this Worker command whenever you want queued uploads to process:

```powershell
python -m app.worker
```

If Redis or Worker is unavailable, the System Status page shows repair guidance and Task Center jobs remain visible.

## Verification

```powershell
python -m compileall backend/app backend/alembic scripts
python -m pytest
python -m alembic current
cd frontend
npm run typecheck
npm run build
```

Current verified state:

- Backend compile: passed.
- Pytest: 40 passed.
- Alembic current: `0006_v3_6_unified_media_tasks`.
- Frontend typecheck: passed.
- Frontend production build: passed, including `/tasks`, `/media` and `/media/sources/[id]`.

## Learning Package

Generate a V3.6 learning package draft from real project changes:

```powershell
python scripts/generate_learning_package.py --version V3.6 --output docs/v3_6_learning_package_draft.json
```

The script uses Git status/diff, API route scanning, dependency changes, migration changes and optional test/build reports. It does not rely on a hardcoded V2.5 template.

## Release

```powershell
python scripts/release.py --version V3.6
```

The release zip excludes `node_modules`, `.next`, virtual environments, caches, `.env`, SQLite databases, uploads, logs, old releases and `*.tsbuildinfo`.

## Current Boundaries

V3.6 implements configurable image OCR, screenshot error archiving, timestamped audio/video transcription, video keyframes, unified media tasks, citation jumps and deterministic learning artifacts from real chunks. Real OCR/transcription/vision features require configured model endpoints. It does not yet implement subtitle export, full shot-level scene segmentation, online GitHub sync, multi-user permissions, knowledge graph, multi-agent workflow, or the business-district growth engine integration.
