# V5.1 Runtime and Strict E2E Tasks

## File List

| Operation | File | Responsibility |
|---|---|---|
| Modify | `scripts/run_demo_e2e.py` | Full isolated Runtime Orchestrator（运行时编排器） |
| Modify | `scripts/check_e2e.py` | Static E2E contract validation |
| Modify | `backend/app/core/config.py` | Run-scoped Worker Name（工作进程名称） setting |
| Modify | `backend/app/worker.py` | Named Redis/RQ Worker（Redis/RQ 工作进程） registration |
| Modify | `backend/app/services/task_broker.py` | Runtime-default queue selection |
| Modify | `backend/app/services/outbox_dispatcher.py` | Preserve unspecified outbox queue routing |
| Modify | `frontend/e2e/run-optional-e2e.mjs` | API-base preflight and honest status |
| Modify | `frontend/playwright.config.ts` | Isolated port propagation and server ownership |
| Create | `backend/tests/test_v5_1_runtime_e2e.py` | Regression coverage |
| Modify | `backend/tests/test_v5_agent_worker_recovery.py` | Broker queue isolation regression |
| Modify | `backend/tests/test_v5_outbox_dispatcher_safety.py` | Outbox queue isolation regression |
| Modify | `docs/local_development.md` | Canonical Strict E2E（严格端到端测试） guide |
| Modify | `docs/environment_variables.md` | Runtime variable reference |
| Create | `docs/v5_1_runtime_e2e/acceptance_report.md` | Evidence-based acceptance result |

## T1: Add failing runtime contract tests

**Files:** `backend/tests/test_v5_1_runtime_e2e.py`, `scripts/check_e2e.py`

**Depends on:** None

**Steps:**

1. Add tests for run-specific identities and resolved collection names.
2. Add tests for exact backend/frontend environment propagation.
3. Add tests for Docker daemon diagnostics and exact owned-container cleanup calls.
4. Add tests for optional worker naming.
5. Extend the static E2E checker contract for strict API-base preflight and no server reuse.

**Verification:** Run
`python -m pytest backend/tests/test_v5_1_runtime_e2e.py -q`; expect failures at unimplemented seams.

## T2: Implement runtime identities, ports, preflight, and ownership cleanup

**Files:** `scripts/run_demo_e2e.py`

**Depends on:** T1

**Steps:**

1. Introduce run identity and port value objects.
2. Validate or allocate loopback ports and a safe showcase database path.
3. Add Docker CLI/daemon and Playwright asset preflight diagnostics.
4. Track child processes and container names only after successful creation.
5. Implement reverse-order, exact-resource teardown.

**Verification:** Run the T1 pytest target; expect identity/preflight/cleanup tests to pass.

## T3: Implement isolated Redis and Qdrant lifecycle

**Files:** `scripts/run_demo_e2e.py`

**Depends on:** T2

**Steps:**

1. Start loopback-only, uniquely named, ephemeral Redis and Qdrant containers.
2. Wait for Redis PING and Qdrant HTTP readiness.
3. Create and confirm the unique Qdrant collection.
4. Print non-secret infrastructure values in the Runtime Manifest（运行清单）.

**Verification:** With Docker Daemon（Docker 守护进程）running, invoke the strict runner with an
intentionally invalid frontend readiness timeout; expect infrastructure readiness to pass and exact
container cleanup after the later boundary fails.

## T4: Wire the production worker path

**Files:** `backend/app/core/config.py`, `backend/app/worker.py`,
`backend/app/services/task_broker.py`, `backend/app/services/outbox_dispatcher.py`,
`scripts/run_demo_e2e.py`

**Depends on:** T3

**Steps:**

1. Add optional `WORKER_NAME` configuration.
2. Register `SimpleWorker` with that name when configured.
3. Make unspecified outbox envelopes defer to the configured runtime queue.
4. Give backend and worker the same isolated database, Redis, queue, and Qdrant settings.
5. Wait for the named worker to register for the unique queue.

**Verification:** Run the runtime pytest target and a focused live-worker Playwright test; expect
the durable Evidence Agent run to complete through Redis/RQ and the outbox path.

## T5: Fix strict frontend API and port propagation

**Files:** `frontend/e2e/run-optional-e2e.mjs`, `frontend/playwright.config.ts`, `scripts/check_e2e.py`

**Depends on:** T1

**Steps:**

1. Add strict failure/optional skip output when `NEXT_PUBLIC_API_BASE_URL` is absent.
2. Parse the configured frontend origin and start Next.js directly with its exact host/port.
3. Disable Playwright-owned server startup/reuse and clean the Node-owned PID tree exactly.
4. Preserve browser-missing strict/optional behavior and the Playwright exit status.

**Verification:** Run the minimized one-test command without the API base; expect an immediate
boundary-specific failure. Run direct strict E2E on a non-default frontend port with an available
backend; expect Next.js and Playwright to use that exact origin.

## T6: Complete full orchestration and regression gates

**Files:** `scripts/run_demo_e2e.py`, `scripts/check_e2e.py`, `backend/tests/test_v5_1_runtime_e2e.py`

**Depends on:** T4, T5

**Steps:**

1. Seed the unique SQLite database after infrastructure preflight.
2. Start backend, named production worker, and frontend in dependency order.
3. Wait for each readiness boundary and invoke the existing strict E2E checker.
4. Preserve the browser exit code and always perform owned-resource teardown.
5. Run relevant static and unit suites.

**Verification:** Run `python scripts/check_e2e.py` and
`python -m pytest backend/tests/test_v5_1_runtime_e2e.py backend/tests/test_v5_demo_agent_worker.py backend/tests/test_v5_outbox_dispatcher_safety.py -q`;
expect all checks to pass.

## T7: Document and execute acceptance

**Files:** `docs/local_development.md`, `docs/environment_variables.md`,
`docs/v5_1_runtime_e2e/acceptance_report.md`

**Depends on:** T6

**Steps:**

1. Document the canonical command, Docker prerequisites, isolation identifiers, provider disclosure,
   and troubleshooting.
2. Run the canonical command twice consecutively.
3. Record actual 32-test verdicts, manifest values, cleanup evidence, and Git Worktree（Git 工作树）
   status.
4. Run `git diff --check` and confirm the package lock is unchanged.

**Verification:** Both strict runs report all 32 real tests and leave no tracked runtime artifacts.

## T8: Commit locally

**Files:** All approved task files

**Depends on:** T7

**Steps:**

1. Review the final diff against `spec.md` and `checklist.md`.
2. Commit on `codex/v5.1-runtime-e2e` with the confirmed root cause in the message.
3. Confirm the branch is not merged or pushed by this task.

**Verification:** Run `git status --short --branch` and `git log -1 --oneline`; expect a clean
dedicated branch with the new local commit.

## Execution Order

```text
T1 -> T2 -> T3 -> T4
  \-> T5 --------> T6 -> T7 -> T8
```
