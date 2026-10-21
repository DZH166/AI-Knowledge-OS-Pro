# V5.1 Runtime and Strict E2E Spec

## Background

The current Strict E2E（严格端到端测试）entry point can start Playwright without a
`NEXT_PUBLIC_API_BASE_URL`. A minimized run then fails before its first backend request, and an
isolated `E2E_BASE_URL` is not propagated to the Next.js Web Server（Web 服务）command. In the
observed baseline this produced `21 passed / 10 failed`; using an isolated frontend port instead
produced a 120-second startup timeout because Next.js still attempted port 3000.

The existing demo orchestrator explicitly supplies the backend URL and isolated frontend/backend
ports, and an observed run completed all 32 browser tests. However, it uses an Inline Demo
Broker（内联演示代理）instead of the production Redis Queue（Redis 队列）worker path, and it does
not provision an isolated Qdrant Collection（Qdrant 集合）. Therefore it is useful diagnostic
evidence but is not yet the requested full runtime boundary.

## Goals

- Provide one reproducible Strict Runtime（严格运行环境）entry point for the current 32 browser
  tests.
- Start Backend（后端）, Frontend（前端）, Worker（工作进程）, Redis Queue, SQLite Database
  （SQLite 数据库）, and Qdrant Collection with run-specific isolation.
- Make frontend and backend origins explicit and consistent throughout startup and test execution.
- Report actual pass/fail/skip outcomes without presenting Demo Provider（演示模型提供方）output as
  real provider output.
- Clean up only resources created by the current run.

## Functional Requirements

- F1: The strict entry point must validate all required Runtime Inputs（运行时输入）before browser
  execution and emit an actionable error when a required dependency or setting is unavailable.
- F2: The orchestrated run must allocate or accept dedicated frontend, backend, Redis, and Qdrant
  ports and must not attach to an unrelated service already listening on a default port.
- F3: The orchestrated run must use a run-specific SQLite database, Redis queue name, and Qdrant
  collection name so concurrent worktrees or test windows do not share mutable state.
- F4: The frontend process and Playwright process must receive the same explicit
  `NEXT_PUBLIC_API_BASE_URL`, and Playwright must target the exact frontend origin started by the
  orchestrator.
- F5: The worker must execute through the production Redis/RQ Broker Path（Redis/RQ 代理路径）and
  durable Outbox Dispatcher（事务发件箱分发器）, not the inline demo broker.
- F6: Startup must wait for observable readiness of Redis, Qdrant, backend, worker path, and
  frontend before launching browser tests.
- F7: Normal and failed teardown must terminate only child processes and run-scoped containers
  created by the current invocation; it must not kill by shared port, executable name, or broad
  process match.
- F8: The strict run must execute the repository's current 32 Playwright tests and preserve their
  real exit status and artifacts.
- F9: Provider behavior must remain honest: explicitly labelled `DEMO_MODE=true` execution may be
  used for deterministic local coverage, but the runner must not inject fake credentials, claim a
  real Provider（模型提供方）was exercised, or convert provider failures into passes.
- F10: The runner must print a concise Runtime Manifest（运行清单）that identifies the isolated
  ports, database path, queue name, Qdrant collection, provider mode, and final test result without
  exposing secrets.

## Non-Functional Requirements

- N1: Re-running the strict command with the same machine prerequisites must be deterministic
  enough to produce the same 32-test verdict; failures must identify the service or test boundary
  that failed.
- N2: The orchestration and checks must work from PowerShell on Windows, while avoiding
  shell-specific process cleanup assumptions.
- N3: The runtime solution must not change the package dependency graph or require repository-wide
  dependency upgrades. A later user-authorized public version bump may update only the root project
  version fields in the shared lockfile, without changing resolved packages.
- N4: Existing optional E2E behavior must continue to skip honestly when optional browser tooling
  is absent; strict mode must fail instead of skipping.
- N5: Logs and generated runtime data must remain in ignored or explicitly documented temporary
  locations and must not dirty the Git Worktree（Git 工作树）after a successful run.
- N6: The implementation must stay within runtime scripts/configuration, backend worker/outbox/task
  broker runtime configuration, Playwright configuration, E2E runner code, documentation, and
  corresponding tests.

## Out of Scope

- Changes to the Agent Controller（智能体控制器）, agent models, or RunWorkspace product
  components.
- Changes to the shared package dependency graph. Root project-version metadata may follow a later
  user-authorized public release bump.
- Fabricating, proxying, or recording a successful real model-provider response when credentials
  are absent.
- Merging or pushing the branch.
- Making Docker Desktop or another system daemon start automatically without an explicit and
  observable preflight contract.

## Acceptance Criteria

- AC1: With `NEXT_PUBLIC_API_BASE_URL` absent from the caller environment, the supported strict
  orchestrator still starts the frontend with the exact isolated backend origin it created.
- AC2: A non-default isolated frontend origin is the origin served by Next.js and targeted by
  Playwright; the runner does not fall back to ports 3000/3001.
- AC3: The runtime manifest shows distinct run-specific SQLite, Redis queue, and Qdrant collection
  identifiers, and readiness checks confirm all required services before browser execution.
- AC4: A live Evidence Agent run is advanced to completion by the production Redis/RQ worker and
  durable outbox path under the explicitly labelled demo provider mode.
- AC5: Two consecutive strict executions complete with an honestly recorded verdict for all 32
  tests, with no unrelated process terminated and no tracked file changed by test execution.
- AC6: When Docker daemon, Playwright browser, Redis, Qdrant, backend, worker, or frontend readiness
  is unavailable, strict mode exits non-zero with a boundary-specific diagnostic and cleans up only
  resources it created.
- AC7: Static/unit regression tests cover API-base propagation, isolated identifier generation,
  readiness failure reporting, and ownership-scoped cleanup.
- AC8: Documentation gives one canonical command, prerequisites, provider-mode disclosure, resource
  isolation behavior, and troubleshooting instructions.
- AC9: The completed changes are committed locally on `codex/v5.1-runtime-e2e` and are neither
  merged nor pushed.
