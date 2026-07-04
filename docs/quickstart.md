# Quickstart

This guide starts the current V4.4 baseline locally for portfolio review, demo validation, citation checks and observability review. It does not require paid AI provider calls unless you enable real mode.

## Implemented

- FastAPI backend with SQLite persistence.
- Next.js frontend.
- Redis and Qdrant through Docker Compose.
- Synthetic demo database seeding.
- Demo readiness, RAG evaluation and full regression checks.
- Provider dry-run diagnostics and optional browser E2E scaffolding.
- Real provider refusal when required keys are missing.

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

## Verify Demo Data

```powershell
python scripts/check_demo_ready.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path backend/data/demo_showcase.db
python scripts/check_full_regression.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_providers.py --dry-run
python scripts/check_e2e.py
python scripts/run_demo_e2e.py
```

Expected result:

```text
Demo readiness check passed
```

If Playwright is not installed, `run_demo_e2e.py` reports `PLAYWRIGHT_NOT_INSTALLED` and exits without claiming a browser pass.

## Reset Demo Data

```powershell
python scripts/reset_demo_data.py
```

The reset script refuses to delete a database outside `backend/data/demo_showcase.db`.

## Real Mode

To use real AI capabilities, set provider variables and do not use synthetic demo results as proof of model output. Missing provider keys must produce explicit NOT_CONFIGURED-style failures.

See:

- [Demo Mode](demo_mode.md)
- [Environment Variables](environment_variables.md)
- [Local Development](local_development.md)
