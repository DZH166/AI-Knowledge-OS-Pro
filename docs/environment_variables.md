# Environment Variables

Never commit real environment values. `.env`, `backend/.env`, `frontend/.env.local` and related files are ignored by Git.

## Runtime

| Variable | Status | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Implemented | SQLAlchemy database URL. Demo commonly uses `sqlite:///.../backend/data/demo_showcase.db`. |
| `DEMO_MODE` | Implemented | Labels runtime as demo mode and keeps demo presentation explicit. |
| `REDIS_URL` | Implemented | Redis/RQ connection for background tasks. |
| `TASK_QUEUE_NAME` | Implemented | Default Redis/RQ queue. Strict E2E assigns a unique value for every invocation. |
| `WORKER_QUEUES` | Implemented | Comma-separated queues consumed by the worker. Strict E2E limits this to its unique queue. |
| `WORKER_NAME` | Optional runtime isolation | Explicit RQ worker identity used by strict readiness checks. |
| `QDRANT_URL` | Implemented | Qdrant vector store endpoint. |
| `QDRANT_COLLECTION_PREFIX` | Implemented | Prefix used to derive the active collection; strict E2E assigns a unique prefix. |
| `NEXT_PUBLIC_API_BASE_URL` | Implemented; required by strict frontend E2E | Absolute frontend API base URL. The full orchestrator sets it to its isolated backend. |
| `E2E_BASE_URL` | Browser E2E | Exact frontend origin used by Next.js and Playwright. |
| `E2E_SKIP_WEBSERVER` | Browser E2E internal contract | Signals that the full orchestrator already owns the frontend; do not set for direct frontend E2E. |
| `API_PROXY_TARGET` | Optional local-preview helper | Server-only FastAPI target. Set `NEXT_PUBLIC_API_BASE_URL=/api-proxy` to route browser calls through the Next.js same-origin proxy. |

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

See [Provider Diagnostics](provider_diagnostics.md) for the System page setup guide and copyable placeholder examples.

## Safety Rules

- Missing provider keys must return explicit NOT_CONFIGURED-style errors.
- Demo data must be labelled synthetic.
- Public CI should not require real provider keys.
- Release archives must not contain `.env`, databases, uploads, logs, caches or provider secrets.
- `API_PROXY_TARGET` is server-only. Do not prefix it with `NEXT_PUBLIC_` or point it at an untrusted target.

## Current Limitations

- Provider-specific variable names may evolve as V4.0 expands capability registry and diagnostics.
- The project documents provider boundaries, but does not ship real credentials.
