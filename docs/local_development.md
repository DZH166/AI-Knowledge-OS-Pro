# Local Development

This document describes the current V5.7 local development workflow for AI Knowledge OS Pro.

## Implemented

- Backend: FastAPI, SQLAlchemy, Alembic, SQLite.
- Frontend: Next.js, React, TypeScript.
- Task infrastructure: Redis/RQ.
- Vector store: Qdrant.
- Demo seeding and release safety scripts.
- Evidence-native Agent Runs with recovery, approvals, citations and persistent event traces.
- Fixed Agent evaluation and a versioned retrieval Policy Lab.
- Release checks that support both Git checkout mode and extracted no-Git source tree mode.

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

## V5.7 Strict Browser Runtime

The canonical Strict E2E（严格端到端测试）command owns a complete, isolated local runtime:

```powershell
docker info
python scripts/run_demo_e2e.py --strict
```

Prerequisites:

- Docker Desktop（Docker 桌面）or another compatible Docker daemon must already be running.
- `frontend/node_modules` must be restored with `npm ci`.
- Chromium must be installed with `npx playwright install chromium` when it is not already present.

Every invocation allocates dedicated loopback ports and creates a unique SQLite Database（SQLite
数据库）, Redis Queue（Redis 队列）, named RQ Worker（RQ 工作进程）, Qdrant Collection（Qdrant
集合）, and ephemeral Redis/Qdrant containers. It starts the FastAPI backend, production worker,
and Next.js frontend in dependency order, waits for each readiness boundary, then runs the current
40 Playwright tests. Teardown targets only child PID trees and exact container names recorded by the
invocation; Playwright never starts or reuses an unrelated server.

The runtime is deliberately `DEMO_MODE=true`. Synthetic outputs remain labelled and the command
does not inject provider credentials or claim that a real model Provider（模型提供方）passed.

To pin ports for diagnosis, provide all or any of the explicit options:

```powershell
python scripts/run_demo_e2e.py --strict `
  --frontend-port 34101 `
  --backend-port 34102 `
  --redis-port 34103 `
  --qdrant-port 34104
```

An occupied explicit port fails at `port_preflight`; it is never reused. A stopped Docker daemon
fails at `docker_preflight` before containers or child processes start. Other boundary names include
`redis_readiness`, `qdrant_readiness`, `backend_readiness`, `worker_readiness`, and
`frontend_readiness`.

For direct frontend-only Strict E2E, a live backend origin is mandatory. The Node runner owns the
exact Next.js PID tree and port:

```powershell
cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
$env:E2E_BASE_URL="http://127.0.0.1:34101"
npm run test:e2e:strict
```

Omitting `NEXT_PUBLIC_API_BASE_URL` produces an immediate
`NEXT_PUBLIC_API_BASE_URL_MISSING` result instead of a partial browser run.

## Database Migrations

Current Alembic head:

```text
0015_v5_7_integration
```

Use Alembic when schema changes are introduced:

```powershell
python -m alembic upgrade head
python -m alembic current
```

## Quality Gates

Use an isolated synthetic database under `.pytest_tmp` for local checks:

```powershell
python scripts/seed_demo_data.py --database-path .pytest_tmp/v5_7_demo_showcase.db --reset
python scripts/check_demo_ready.py --database-path .pytest_tmp/v5_7_demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v5_7_demo_showcase.db
python scripts/check_full_regression.py --database-path .pytest_tmp/v5_7_demo_showcase.db
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
python scripts/release.py --version V5.7 --dry-run
```

Generate and inspect a local release archive:

```powershell
python scripts/release.py --version V5.7
python scripts/check_release.py --version V5.7
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

V5.7 keeps stable root commands for historical docs and CI, while low-frequency self-check and CI diagnostic implementations live under:

- `scripts/maintenance/self_check/`
- `scripts/maintenance/ci/`

Directly executed root wrappers print a deprecated compatibility notice and delegate to the maintenance implementation.

## Current Limitations

- Global `npm` may not be available on every Windows PATH; the Codex desktop environment can use its bundled Node runtime.
- Browser E2E is strict when `--strict` is used; the optional command still skips honestly when the API base, Playwright, or browser binaries are unavailable.
- Real provider checks require user-owned API keys and should not run in public CI.
- `/system/performance` shows local runtime evidence, browser cache counters and session-local button timing; it is not a hosted production monitoring system.

