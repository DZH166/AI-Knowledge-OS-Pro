# V5.1 Runtime and Strict E2E Plan

## Architecture Overview

The canonical Strict E2E（严格端到端测试）flow will remain
`python scripts/run_demo_e2e.py --strict`, but the script will become an ownership-scoped Runtime
Orchestrator（运行时编排器）instead of an inline-demo shortcut.

Each invocation creates a `RuntimeIdentity` with a unique token. The identity determines an ignored
SQLite Database（SQLite 数据库）path, one Redis Queue（Redis 队列）name, one Qdrant Collection
（Qdrant 集合）prefix, and unique Docker Container（Docker 容器）names. Frontend, backend, Redis,
and Qdrant ports are either explicit CLI values or free loopback ports selected for that invocation.

The orchestrator performs Docker/Playwright preflight checks, starts run-scoped Redis and Qdrant
containers, creates the isolated Qdrant collection, seeds SQLite, starts FastAPI, starts the
production Redis/RQ Worker（Redis/RQ 工作进程）, starts Next.js on the exact frontend origin, and
finally invokes the existing 32-test Playwright suite. Readiness is checked at every boundary.

All owned processes and containers are recorded as they start. Teardown walks only those recorded
resources in reverse order. No port-based or executable-name-based process termination is used.

The frontend Strict Runner（严格运行器）will fail fast when called directly without
`NEXT_PUBLIC_API_BASE_URL`. When the full Python orchestrator has not prestarted the frontend, the
Node runner will start Next.js directly on the hostname and port from `E2E_BASE_URL`, then tear down
that exact owned PID tree. Playwright itself will never start or reuse a Web Server（Web 服务）and
therefore cannot attach to an unrelated process on port 3000.

## Core Data Structures and Interfaces

### `RuntimeIdentity`

Immutable run-scoped values:

- `token`: filesystem/container-safe unique identifier.
- `database_path`: ignored SQLite showcase database path.
- `queue_name`: Redis/RQ queue used by backend and worker.
- `qdrant_collection_prefix`: prefix whose configured index suffix produces the exact collection.
- `qdrant_collection`: resolved Qdrant collection name printed in the manifest.
- `redis_container` and `qdrant_container`: exact owned Docker resource names.
- `worker_name`: exact RQ Worker（RQ 工作进程）identity used by readiness checks.

### `RuntimePorts`

Validated loopback ports for frontend, backend, Redis, and Qdrant. A value of zero at the CLI seam
means select a currently free loopback port; an explicit occupied port is a preflight failure.

### `OwnedRuntime`

Tracks only successfully started `subprocess.Popen` children and Docker container names. Its
`close()` operation terminates child processes in reverse order and stops only recorded containers.

### Readiness Functions

- `wait_url`: require a non-5xx HTTP response within a bounded timeout.
- `wait_redis`: require `PING` success at the isolated Redis URL.
- `wait_qdrant_collection`: require the isolated collection to exist.
- `wait_worker`: require the named RQ worker to register for the isolated queue.
- `ensure_process_alive`: report an early child-process exit at its service boundary.

### Environment Builders

- Backend/worker environment: isolated `DATABASE_URL`, `REDIS_URL`, `TASK_QUEUE_NAME`,
  `WORKER_QUEUES`, `WORKER_NAME`, `QDRANT_URL`, `QDRANT_COLLECTION_PREFIX`, explicit demo mode,
  and isolated frontend CORS origin.
- Frontend/Playwright environment: exact `NEXT_PUBLIC_API_BASE_URL`, `E2E_BASE_URL`, and
  `E2E_SKIP_WEBSERVER=1` because the full orchestrator owns the frontend process.

## Module Design

### `scripts/run_demo_e2e.py`

**Responsibility:** Own the complete deterministic local runtime and preserve the browser suite's
real exit status.

**Public interface:** CLI arguments for strict/optional behavior, database path, four loopback
ports, startup timeouts, and Docker image overrides. The canonical command requires no caller-set
runtime URL.

**Dependencies:** Python standard library, installed backend dependencies (`redis`, `rq`,
`qdrant-client`), Docker CLI/daemon, repository seed/check scripts, FastAPI/Next.js entry points.

**Requirements:** F1-F10.

### `backend/app/core/config.py` and `backend/app/worker.py`

**Responsibility:** Accept an optional `WORKER_NAME` runtime setting and register the production
worker under that exact run-scoped name.

**Public interface:** `settings.worker_name`; no behavior change when unset.

**Dependencies:** Existing Pydantic settings and RQ `SimpleWorker`.

**Requirements:** F3, F5, F6.

### `backend/app/services/task_broker.py` and `backend/app/services/outbox_dispatcher.py`

**Responsibility:** Preserve an explicitly routed queue, while making an unspecified outbox queue
defer to the configured run-specific `TASK_QUEUE_NAME` instead of hard-coding `default`.

**Public interface:** Empty `TaskEnvelope.queue_name` means “use the broker runtime default.”

**Dependencies:** Existing Redis/RQ adapter and durable outbox envelope projection.

**Requirements:** F3, F5, F6.

### `frontend/e2e/run-optional-e2e.mjs`

**Responsibility:** Preserve Playwright/browser optional-versus-strict behavior, add an explicit
API-base preflight result, and own direct Next.js startup/teardown when no frontend was prestarted.

**Public interface:** Existing `--strict` argument and stable status/reason output.

**Dependencies:** Node.js and `@playwright/test`.

**Requirements:** F1, F4, F8, F9.

### `frontend/playwright.config.ts`

**Responsibility:** Supply the tested frontend base URL while explicitly disabling Playwright-owned
web-server startup and reuse.

**Public interface:** Existing `E2E_BASE_URL`, `PLAYWRIGHT_BASE_URL`, and `E2E_SKIP_WEBSERVER`
environment contract.

**Dependencies:** Playwright Test and the repository `npm run dev` command.

**Requirements:** F2, F4, F7, F8.

### Runtime Regression Tests（运行时回归测试）

**Responsibility:** Lock down identity isolation, environment propagation, Docker preflight
diagnostics, worker naming, and exact-resource cleanup without requiring Docker for unit tests.

**Public interface:** Pytest cases and the existing static E2E checker.

**Dependencies:** Pytest, monkeypatch/fake subprocess seams, Node runner source inspection where a
live Node dependency is not guaranteed.

**Requirements:** F1-F7, F10.

### Runtime Documentation（运行时文档）

**Responsibility:** Publish the canonical command, prerequisites, isolation model, provider-mode
disclosure, failure diagnostics, and observed acceptance evidence.

**Public interface:** `docs/local_development.md`, `docs/environment_variables.md`, and the V5.1
Runtime/E2E acceptance report.

**Requirements:** F9, F10, AC8.

## Module Interactions

1. CLI parsing creates `RuntimeIdentity` and `RuntimePorts`.
2. Preflight validates Playwright assets, Docker CLI/daemon, image availability, database safety,
   and all explicit ports.
3. `OwnedRuntime` starts isolated Redis and Qdrant containers.
4. Readiness probes confirm Redis and Qdrant, then create/confirm the run-specific collection.
5. The seeder populates the run-specific SQLite database.
6. FastAPI starts with the shared backend/worker environment and reaches `/health`.
7. The named production worker starts, registers against the isolated Redis queue, and runs the
   durable Outbox Dispatcher（事务发件箱分发器）maintenance thread.
8. Next.js starts with the exact backend API base URL and isolated frontend port.
9. The E2E checker invokes the 32 browser scenarios with the prestarted-server contract;
   direct Node-runner use follows the same origin contract with its own exact child cleanup.
10. The browser exit code is recorded, then `OwnedRuntime` closes only owned resources.

## File Organization

| Operation | File | Responsibility |
|---|---|---|
| Modify | `scripts/run_demo_e2e.py` | Full isolated runtime orchestration and manifest |
| Modify | `scripts/check_e2e.py` | Static contract checks for strict API/port behavior |
| Modify | `backend/app/core/config.py` | Optional run-scoped worker name |
| Modify | `backend/app/worker.py` | Register RQ worker with configured name |
| Modify | `backend/app/services/task_broker.py` | Defer unspecified envelopes to the runtime queue |
| Modify | `backend/app/services/outbox_dispatcher.py` | Preserve unspecified queue routing for the broker |
| Modify | `frontend/e2e/run-optional-e2e.mjs` | Strict API-base preflight |
| Modify | `frontend/playwright.config.ts` | Exact isolated web-server command and no reuse |
| Create | `backend/tests/test_v5_1_runtime_e2e.py` | Runtime orchestration regression coverage |
| Modify | `backend/tests/test_v5_agent_worker_recovery.py` | Isolated broker queue regression coverage |
| Modify | `backend/tests/test_v5_outbox_dispatcher_safety.py` | Unspecified outbox queue regression coverage |
| Modify | `docs/local_development.md` | Canonical local Strict E2E command and troubleshooting |
| Modify | `docs/environment_variables.md` | New/clarified runtime variables |
| Create | `docs/v5_1_runtime_e2e/acceptance_report.md` | Actual command and verdict evidence |

## Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Infrastructure ownership | Per-run `docker run --rm` containers | Exact names and no shared Compose project/volume make cleanup ownership explicit. |
| Host exposure | Loopback-only published ports | Prevents accidental LAN exposure and supports concurrent worktrees. |
| Queue isolation | One unique queue consumed by one named production worker | Proves Redis/RQ and outbox flow while excluding unrelated jobs/workers. |
| Qdrant isolation | Unique collection prefix on an ephemeral per-run Qdrant container | Provides both process and collection isolation with no persistent volume. |
| Provider mode | Explicit `DEMO_MODE=true`, printed in the manifest | Deterministic browser coverage remains honest and does not simulate real credentials. |
| Frontend ownership | Python orchestrator for the full run; Node E2E runner for direct use | Both paths own exact child processes; Playwright never owns or reuses a server. |
| Server reuse | No Playwright `webServer` configuration | Avoids Windows child-tree leaks and attaching to another task's server. |
| Docker daemon | Fail-fast preflight; never auto-start from repository code | Makes the system prerequisite explicit and avoids hidden external state changes. |
| Package management | Reuse existing locked dependencies | Meets the no-lockfile-change constraint. |
