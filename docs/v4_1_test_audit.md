# V4.1 Test Audit

## Current Test Inventory

The V4.1 inventory reports 34 backend test files under `backend/tests`.

Coverage areas include:

- Health and system status.
- Demo readiness and reset path safety.
- Document ingestion, deduplication, indexing and RAG citations.
- Task engine creation, retry, cancel and media job fields.
- Image upload/OCR refusal and error archive.
- Audio/video upload, transcription refusal/success paths and timestamp citations.
- Learning packages, learning artifacts, roadmap and graph endpoints.
- Code repository ingestion and provider refusal.
- Portfolio summary and generation refusal boundaries.
- Release exclusions and repository safety scripts.

## Recent Test-Related Cleanup

- Updated `backend/tests/test_v3_6_citations_release_package.py` to use the archived V3.6 acceptance report path.
- Removed frontend hooks dependency suppression comments and verified TypeScript with `tsc --noEmit`.

## Required Final Gates

V4.1 is not complete until these commands are run and recorded:

```powershell
python -m compileall backend/app scripts
python -m pytest
cd frontend; npm run typecheck
cd frontend; npm run build
python scripts/check_encoding.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/release.py --dry-run
```

Optional when available:

```powershell
python scripts/evaluate_rag.py --demo
python scripts/check_frontend_smoke.py
```

## Current Evidence

- `python scripts/check_encoding.py`: passed after docs cleanup.
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: passed, 61 tests and 8 warnings.
- Frontend `tsc --noEmit`: passed after hooks cleanup.
- Frontend production build: passed, 28 generated routes.
- Alembic upgrade/current against an isolated `.pytest_tmp` SQLite database: passed, current head `0006_v3_6_unified_media_tasks`.

Secret, repo-clean and release dry-run checks passed after the final V4.1 file set was staged for tracked-file analysis.
