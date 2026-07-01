# Environment Variables

Never commit real environment values. `.env`, `backend/.env`, `frontend/.env.local` and related files are ignored by Git.

## Runtime

| Variable | Status | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Implemented | SQLAlchemy database URL. Demo commonly uses `sqlite:///.../backend/data/demo_showcase.db`. |
| `DEMO_MODE` | Implemented | Labels runtime as demo mode and keeps demo presentation explicit. |
| `REDIS_URL` | Implemented | Redis/RQ connection for background tasks. |
| `QDRANT_URL` | Implemented | Qdrant vector store endpoint. |
| `NEXT_PUBLIC_API_BASE_URL` | Implemented | Frontend API base URL. |

## AI Providers

| Variable | Status | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | Implemented provider boundary | Selects LLM provider where supported. |
| `LLM_API_KEY` | Requires configuration | Required for real generated answers. |
| `EMBEDDING_PROVIDER` | Implemented provider boundary | Selects embedding provider where supported. |
| `EMBEDDING_API_KEY` | Requires configuration | Required for real semantic indexing. |
| `OCR_PROVIDER` | Requires configuration for real OCR | Used by image OCR flows. |
| `OCR_API_KEY` | Requires configuration | Required by real OCR provider. |
| `TRANSCRIPTION_PROVIDER` | Requires configuration for real transcription | Used by audio/video transcription flows. |
| `TRANSCRIPTION_API_KEY` | Requires configuration | Required by real transcription provider. |

## Safety Rules

- Missing provider keys must return explicit NOT_CONFIGURED-style errors.
- Demo data must be labelled synthetic.
- Public CI should not require real provider keys.
- Release archives must not contain `.env`, databases, uploads, logs, caches or provider secrets.

## Current Limitations

- Provider-specific variable names may evolve as V4.0 expands capability registry and diagnostics.
- The project documents provider boundaries, but does not ship real credentials.
