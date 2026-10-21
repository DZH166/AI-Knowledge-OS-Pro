# Backend Architecture

The backend is a FastAPI application with SQLAlchemy persistence, Alembic migrations, provider adapters and Redis/RQ-backed task processing.

## API Layer

All public product APIs are mounted below `/api` through `backend/app/api/router.py`.

| Domain | Route File | Responsibility |
| --- | --- | --- |
| Dashboard | `routes_dashboard.py` | Aggregate counts and learning workspace summary. |
| Knowledge spaces | `routes_knowledge_spaces.py` | Workspace CRUD and space details. |
| Documents | `routes_documents.py` | Upload, governance, chunks, retry/reparse/reindex. |
| Media | `routes_media.py` | Image/audio/video upload, media processing tasks, source files and asset files. |
| Chat | `routes_chat.py` | RAG answers, sessions, favorites and regeneration. |
| Learning | `routes_learning.py` | Logs, packages, knowledge points, cards, quizzes, notes and source-derived artifacts. |
| Errors | `routes_errors.py` | Screenshot/error archive lifecycle. |
| Tasks | `routes_ingestion_jobs.py` | Durable job list, events, retry and cancel. |
| Portfolio | `routes_portfolio.py` | Portfolio summary and provider-backed markdown generation. |
| Code repositories | `routes_code_repositories.py` | Safe local repository ingestion. |
| Onboarding | `routes_onboarding.py` | First-use state. |
| System | `routes_system.py` | Provider, Redis, Worker, Qdrant and runtime diagnostics. |

## Service Layer

Service modules own domain behavior and are called by routes, workers and tests. The most important boundaries are:

- `ingestion_service.py`: document upload, parsing, chunking, embedding, indexing and document job lifecycle.
- `media_service.py`: media upload, metadata extraction, OCR/transcription/keyframes, multimodal chunks and source-derived learning inputs.
- `media_task_service.py`: durable media job orchestration on top of the unified ingestion job model.
- `rag_service.py`, `hybrid_retriever.py`, `vector_store.py`: retrieval and grounded answer flow.
- `providers.py`, `transcription_service.py`, `video_service.py`: external provider and media-processing adapters.
- `learning_*_service.py`: learning archive, cards, notes, packages and source-derived artifacts.
- `portfolio_service.py`: real project summary plus optional provider-backed resume/interview/project-review generation.
- `system_service.py`: runtime diagnostics without leaking secrets.

## Data Layer

SQLAlchemy models live under `backend/app/models`. Alembic revisions live under `backend/alembic/versions`.

Key model groups:

- Knowledge and document RAG: `KnowledgeSpace`, `Document`, `Chunk`, `QALog`, `ChatSession`.
- Task engine: `IngestionJob`, `JobEvent`.
- Multimodal source graph: `Source`, `SourceRevision`, `MediaAsset`, `TranscriptSegment`, `VisualFrame`, `MultimodalChunk`, `CitationLocator`, `IndexRevision`.
- Learning system: `LearningLog`, `LearningPackage`, `LearningCard`, `LearningNote`, `LearningArtifact`.
- Portfolio/code/error modules: `CodeRepository`, `ErrorArchive`, onboarding/system support models.

## Provider Boundary

Missing provider keys must produce explicit NOT_CONFIGURED-style errors. Real mode must never create fake OCR, fake transcription, fake embeddings or fake generated answers.

Provider-owned work:

- LLM and embedding calls in `providers.py`.
- OCR/vision via explicit image and media tasks.
- Audio/video transcription in `transcription_service.py`.
- FFmpeg/ffprobe media analysis and keyframe/audio extraction in `video_service.py`.

## Task Boundary

Document jobs and media jobs share the durable `IngestionJob`/`JobEvent` contract. Document jobs use `document_id`; media jobs use `source_id`; `target_type` distinguishes ownership. Task Center UI can observe, retry and cancel both kinds without separate state machines.

## Error Boundary

Routes raise `ServiceError` or `HTTPException`; `backend/app/main.py` turns them into the shared API envelope. Error responses should remain structured, user-readable and explicit about retryability.
