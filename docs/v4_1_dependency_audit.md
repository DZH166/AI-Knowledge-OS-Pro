# V4.1 Dependency Audit

## Backend Dependencies

`backend/requirements.txt` currently declares 16 runtime/test dependencies.

| Dependency | Current Evidence | Decision |
| --- | --- | --- |
| `fastapi` | API routes, `UploadFile`, `TestClient`. | Keep. |
| `uvicorn[standard]` | Local API server runtime. | Keep. |
| `SQLAlchemy` | Models, sessions, services and tests. | Keep. |
| `pydantic-settings` | `backend/app/core/config.py`. | Keep. |
| `python-dotenv` | Pydantic settings env-file support. | Keep. |
| `python-multipart` | Required for FastAPI upload forms. | Keep. |
| `httpx` | LLM/OCR-compatible providers and transcription service. | Keep. |
| `qdrant-client` | Vector store integration. | Keep. |
| `pypdf` | PDF parsing. | Keep. |
| `Pillow` | Image metadata, keyframe handling, screenshot/demo image helpers. | Keep. |
| `mutagen` | Audio duration metadata. | Keep. |
| `imageio-ffmpeg` | FFmpeg path for video metadata/audio/keyframes and showcase generation. | Keep. |
| `alembic` | Database migrations. | Keep. |
| `pytest` | Backend regression suite. | Keep as current mixed runtime/dev dependency. |
| `redis` | RQ broker and diagnostics. | Keep. |
| `rq` | Background task queue. | Keep. |

## Frontend Dependencies

`frontend/package.json` has 6 runtime dependencies and 6 dev dependencies. Current source references confirm use of `next`, `react`, `react-dom`, `lucide-react`, `react-markdown` and `remark-gfm`.

## Cleanup Decision

- No tracked dependency was removed in this pass.
- Untracked `frontend/pnpm-lock.yaml` and `frontend/pnpm-workspace.yaml` were removed because the tracked project uses npm and `package-lock.json`; CI also uses `npm ci`.

## Remaining Dependency Debt

- Backend runtime and test dependencies are still mixed in `requirements.txt`; a later pass can split `requirements-dev.txt` after CI is updated.
- FFmpeg and image processing remain necessary for video/keyframe features, but should continue to be documented as media-processing dependencies rather than AI provider credentials.
