# Local Development

This document describes the current local development workflow for AI Knowledge OS Pro.

## Implemented

- Backend: FastAPI, SQLAlchemy, Alembic, SQLite.
- Frontend: Next.js, React, TypeScript.
- Task infrastructure: Redis/RQ.
- Vector store: Qdrant.
- Demo seeding and release safety scripts.

## Backend

Install backend dependencies according to the environment used on your machine, then run:

```powershell
python -m compileall backend/app scripts
python -m pytest
```

Start the API:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

## Frontend

```powershell
cd frontend
npm ci
npm run typecheck
npm run build
npm run dev
```

Set the API base URL for local development:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
```

## Services

Start Redis and Qdrant:

```powershell
docker compose up -d redis qdrant
```

Validate the Compose file:

```powershell
docker compose config --quiet
```

## Database Migrations

Current Alembic head:

```text
0006_v3_6_unified_media_tasks
```

Use Alembic when schema changes are introduced:

```powershell
python -m alembic upgrade head
python -m alembic current
```

## Quality Gates

```powershell
python scripts/check_encoding.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/check_version.py
python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_4_demo_showcase.db --reset
python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_4_demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_4_demo_showcase.db
python scripts/check_full_regression.py --database-path .pytest_tmp/v4_4_demo_showcase.db
python scripts/evaluate_providers.py --dry-run
python scripts/check_e2e.py
python scripts/run_demo_e2e.py
python scripts/check_docs_links.py
python scripts/check_readme_assets.py
python scripts/check_all.py --quick
python scripts/release.py --version V4.4 --dry-run
```

## Current Limitations

- Global `npm` may not be available on every Windows PATH; the Codex desktop environment can use its bundled Node runtime.
- Browser E2E scaffolding exists in V4.4 and skips honestly when Playwright or browser binaries are unavailable.
- Real provider checks require user-owned API keys and should not run in public CI.
