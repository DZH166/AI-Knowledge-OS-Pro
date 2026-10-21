# Quickstart

This guide starts the current V4.8 application locally for portfolio review, demo validation, citation checks, live E2E and runtime performance review. It does not require paid AI provider calls unless you enable real mode.

## Implemented

- FastAPI backend with SQLite persistence.
- Next.js frontend.
- Redis and Qdrant through Docker Compose.
- Synthetic demo database seeding.
- Demo readiness, RAG evaluation and full regression checks.
- Provider dry-run diagnostics and optional browser E2E scaffolding.
- Real provider refusal when required keys are missing.
- V4.8 runtime performance panel at `/system/performance`.
- V4.8 frontend GET request cache and in-flight dedupe checks.
- V4.8 release safety checks that also work in extracted source trees without `.git`.

## Prerequisites

- Python 3.12.
- Node.js 20.
- Docker Desktop for Redis and Qdrant.
- Optional real provider keys for LLM, embedding, OCR and transcription.

## One-Command Demo Preparation

```powershell
python scripts/setup_demo.py --reset
```

If Docker is already running elsewhere or not available:

```powershell
python scripts/setup_demo.py --skip-docker --reset
```

The script creates an isolated synthetic database at:

```text
backend/data/demo_showcase.db
```

This file is ignored by Git and is not a user database.

## Start Backend

```powershell
$env:DATABASE_URL="sqlite:///C:/Users/Lenovo/Documents/AI Knowledge OS Pro/backend/data/demo_showcase.db"
$env:DEMO_MODE="true"
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

## Start Frontend

```powershell
cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

Useful V4.8 pages:

- Dashboard: `http://127.0.0.1:3000/dashboard`
- Knowledge Q&A: `http://127.0.0.1:3000/chat`
- Task center: `http://127.0.0.1:3000/tasks`
- Media library: `http://127.0.0.1:3000/media`
- Runtime performance: `http://127.0.0.1:3000/system/performance`

## Verify Demo Data

```powershell
python scripts/check_demo_ready.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path backend/data/demo_showcase.db
python scripts/check_full_regression.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_providers.py --dry-run
python scripts/check_request_cache.py
python scripts/check_e2e.py
python scripts/run_demo_e2e.py
python scripts/run_demo_e2e.py --strict
```

Expected demo readiness result:

```text
Demo readiness check passed
```

If Playwright is not installed, `run_demo_e2e.py` reports `PLAYWRIGHT_NOT_INSTALLED` and exits without claiming a browser pass. Use `--strict` only after `npm ci` and `npx playwright install chromium`; strict mode fails when the browser runtime is missing.

## Runtime Performance Check

After using a few API-backed pages, open `/system/performance`.

The page shows:

- backend request timing from the current API process;
- slow path summaries;
- frontend request-cache hit/miss/dedupe counters;
- recent shared button action timing.

These are local runtime signals, not production APM metrics.

## Reset Demo Data

```powershell
python scripts/reset_demo_data.py
```

The reset script refuses to delete a database outside `backend/data/demo_showcase.db`.

## Release Dry Run

```powershell
python scripts/release.py --version V4.8 --dry-run
```

The dry run reports included/excluded files and checks that forbidden content such as `.env`, databases, uploads, logs, `node_modules`, `.next`, caches and release artifacts are excluded.

For a generated V4.8 archive:

```powershell
python scripts/check_release.py --version V4.8
```

The authoritative archive digest is the `.sha256` file generated next to the zip.

## No-Git Zip Validation

Extract a generated release zip into a temporary folder that does not contain `.git`, then run:

```powershell
python scripts/check_version.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/check_all.py --quick
```

In this mode, `check_secrets.py` and `check_repo_clean.py` should print filesystem scan mode with a no-Git reason instead of raising a Python traceback.

## Real Mode

To use real AI capabilities, set provider variables and do not use synthetic demo results as proof of model output. Missing provider keys must produce explicit NOT_CONFIGURED-style failures.

See:

- [Demo Mode](demo_mode.md)
- [Environment Variables](environment_variables.md)
- [Local Development](local_development.md)
- [Runtime Performance Report](v4_8_runtime_performance_report.md)

