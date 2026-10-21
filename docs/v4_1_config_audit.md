# V4.1 Configuration Audit

## Files Reviewed

- `.env.example`
- `backend/.env.example`
- `frontend/.env.local.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `docs/environment_variables.md`

## Runtime Variables

| Variable | Required For | Notes |
| --- | --- | --- |
| `DATABASE_URL` | Backend persistence | Defaults to local SQLite; demo uses isolated synthetic DB paths. |
| `DEMO_MODE` | Demo labelling | Must not be used to fake provider-backed output. |
| `REDIS_URL` | Task queue | Used by Redis/RQ worker, task broker and diagnostics. |
| `QDRANT_URL` | Vector store | Used by retrieval and indexing. |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API client | Frontend-only public base URL. |

## Provider Variables

| Provider | Variables | Boundary |
| --- | --- | --- |
| LLM | `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Missing key must refuse generated answers. |
| Embedding | `EMBEDDING_PROVIDER`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL` | Missing key must refuse real semantic indexing. |
| OCR/Vision | `OCR_PROVIDER`, `OCR_API_KEY`, `OCR_BASE_URL`, `OCR_MODEL` | Missing key must return `OCR_NOT_CONFIGURED`. |
| Transcription | `TRANSCRIPTION_PROVIDER`, `TRANSCRIPTION_API_KEY`, `TRANSCRIPTION_BASE_URL`, `TRANSCRIPTION_MODEL` | Missing key must return `TRANSCRIPTION_NOT_CONFIGURED`. |

## Findings

- No real API keys should be committed; `.env` files remain ignored.
- `backend/app/core/config.py` still reports the public stable version as `V3.8 / 3.8.0`. V4.1 should only change visible version after final acceptance is proven.
- Documentation clearly marks provider-backed features as requiring configuration.
- Demo and showcase databases are isolated and ignored by release checks.

## Remaining Work

Run `scripts/check_secrets.py`, `scripts/check_repo_clean.py` and release dry-run after all docs/code changes are staged or otherwise included in the final release analysis.
