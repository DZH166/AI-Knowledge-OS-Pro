# Local Development

This document describes the current V4.8 local development workflow for AI Knowledge OS Pro.

## Implemented

- Backend: FastAPI, SQLAlchemy, Alembic, SQLite.
- Frontend: Next.js, React, TypeScript.
- Task infrastructure: Redis/RQ.
- Vector store: Qdrant.
- Demo seeding and release safety scripts.
- V4.8 runtime performance endpoints and `/system/performance`.
- V4.8 frontend GET request cache, in-flight dedupe and mutation cache clearing.
- V4.8 release checks that support both Git checkout mode and extracted no-Git source tree mode.

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

Useful backend endpoints:

- `/api/system/status`
- `/api/system/observability`
- `/api/system/performance`

The performance endpoint uses a local in-process rolling buffer. Restarting the API clears the buffer.

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

Useful frontend routes:

- `/dashboard`
- `/upload`
- `/chat`
- `/media`
- `/tasks`
- `/learning/project-structure`
- `/system/observability`
- `/system/performance`

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

Use an isolated synthetic database under `.pytest_tmp` for local checks:

```powershell
python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_8_demo_showcase.db --reset
python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_8_demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_8_demo_showcase.db
python scripts/check_full_regression.py --database-path .pytest_tmp/v4_8_demo_showcase.db
```

Core checks:

```powershell
python -m compileall backend/app scripts
python -m pytest
python scripts/check_encoding.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/check_version.py
python scripts/check_docs_links.py
python scripts/check_readme_assets.py
python scripts/check_frontend_smoke.py
python scripts/check_ui_performance_budget.py
python scripts/check_interaction_feedback.py
python scripts/check_request_cache.py
python scripts/evaluate_providers.py --dry-run
python scripts/check_e2e.py
python scripts/run_demo_e2e.py
python scripts/run_demo_e2e.py --strict
python scripts/check_all.py --quick
python scripts/check_all.py --full
```

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Release Checks

Dry-run the release package:

```powershell
python scripts/release.py --version V4.8 --dry-run
```

Generate and inspect a local release archive:

```powershell
python scripts/release.py --version V4.8
python scripts/check_release.py --version V4.8
```

The release zip must not include `.env`, databases, uploads, logs, `node_modules`, `.next`, caches, old releases or secrets.

To validate the extracted source tree experience, unzip the archive into a temporary folder without `.git` and run:

```powershell
python scripts/check_version.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/check_all.py --quick
```

`check_secrets.py` and `check_repo_clean.py` should explicitly report filesystem scan mode when Git metadata is absent.

## Maintenance Scripts

V4.8 keeps stable root commands for historical docs and CI, while low-frequency self-check and CI diagnostic implementations live under:

- `scripts/maintenance/self_check/`
- `scripts/maintenance/ci/`

Directly executed root wrappers print a deprecated compatibility notice and delegate to the maintenance implementation.

## Current Limitations

- Global `npm` may not be available on every Windows PATH; the Codex desktop environment can use its bundled Node runtime.
- Browser E2E is strict when `--strict` is used; the optional command still skips honestly when Playwright or browser binaries are unavailable.
- Real provider checks require user-owned API keys and should not run in public CI.
- `/system/performance` shows local runtime evidence, browser cache counters and session-local button timing; it is not a hosted production monitoring system.

