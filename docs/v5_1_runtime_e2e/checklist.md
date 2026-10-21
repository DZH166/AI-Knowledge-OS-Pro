# V5.1 Runtime and Strict E2E Checklist

## Implementation Completeness

- [x] Required Runtime Inputs（运行时输入）fail at a named preflight boundary with an actionable
  message. (Verification: run focused preflight regression tests and one Docker-daemon-unavailable
  invocation.) [AC6; F1]
- [x] A caller with no `NEXT_PUBLIC_API_BASE_URL` can use the canonical orchestrator, which supplies
  the exact isolated backend origin to both frontend and Playwright. (Verification: clear the caller
  variable, run the canonical strict command, and inspect the manifest/test environment.) [AC1; F4]
- [x] Next.js and Playwright use the same non-default isolated frontend origin and never attach to
  port 3000/3001. (Verification: run with explicit non-default ports and inspect startup/test URLs.)
  [AC2; F2; F4]
- [x] Each invocation has unique SQLite, Redis queue, Qdrant collection, worker, and container
  identities. (Verification: compare two consecutive Runtime Manifests（运行清单）.) [AC3; F3; F10]
- [x] The live agent test completes through the named production Redis/RQ Worker（Redis/RQ 工作进程）
  and durable Outbox Dispatcher（事务发件箱分发器）. (Verification: observe worker registration,
  queue/outbox progression, and the Playwright live-worker pass.) [AC4; F5; F6]
- [x] Provider Mode（模型提供方模式）is explicitly `demo`, without injected credentials or claims
  of a real provider pass. (Verification: inspect the runtime manifest, environment builder tests,
  and browser output.) [F9]
- [x] Teardown targets only recorded child PIDs and exact run-scoped container names. (Verification:
  run cleanup unit tests and inspect two live-run teardown logs.) [AC5; AC6; F7]

## Integration

- [x] Redis PING, Qdrant collection, FastAPI health, named worker registration, and Next.js URL all
  pass bounded Readiness Checks（就绪检查）before browser execution. (Verification: inspect canonical
  runner output and boundary tests.) [AC3; F6]
- [x] The existing checker still executes all four E2E spec files and preserves the Playwright exit
  code. (Verification: run `python scripts/check_e2e.py --run-browser --strict` through the
  orchestrator and inspect `Running 32 tests` plus the process exit code.) [F8]
- [x] Optional E2E still skips honestly for absent Playwright/browser/API prerequisites, while
  strict mode fails. (Verification: static checks plus targeted child-process invocations with each
  prerequisite absent.) [F1; N4]
- [x] The runtime track changed no package dependency resolution, Agent Controller（智能体控制器）,
  agent model, or RunWorkspace product behavior. The later integration tracks and public V5.1 version
  bump are recorded separately. (Verification: inspect commits and the lockfile's root-only version diff.) [N3; N6]

## Build and Test

- [x] Runtime regression tests pass. (Verification: run
  `python -m pytest backend/tests/test_v5_1_runtime_e2e.py -q`.) [AC7]
- [x] Worker/outbox regressions pass. (Verification: run
  `python -m pytest backend/tests/test_v5_demo_agent_worker.py backend/tests/test_v5_outbox_dispatcher_safety.py -q`.)
- [x] E2E static checks pass. (Verification: run `python scripts/check_e2e.py`.) [AC7]
- [x] Frontend Type Check（前端类型检查）passes. (Verification: run `npm run typecheck` in
  `frontend`.)
- [x] Relevant Python suite passes without warnings promoted to errors. (Verification: run the
  combined pytest command from `task.md`.)
- [x] Formatting/whitespace validation passes. (Verification: run `git diff --check`.)
- [x] Runtime dependency resolution is unchanged; the package lock changed only at its two root
  project-version fields for the V5.1 release bump. (Verification: inspect the lockfile diff.) [N3]

## End-to-End Scenarios

- [x] Canonical Run 1（规范运行 1）: caller API base absent -> unique infrastructure starts -> all
  readiness checks pass -> the actual 32-test suite completes -> only owned resources stop.
  (Verification: run `python scripts/run_demo_e2e.py --strict`; record manifest and verdict.)
  [AC1-AC6]
- [x] Canonical Run 2（规范运行 2）: immediately repeat the same command -> different isolation
  identifiers -> same honest 32-test verdict -> clean teardown. (Verification: repeat the command
  and compare manifests/results.) [AC3; AC5]
- [x] Failure Cleanup（失败清理）: force a bounded readiness failure after containers start ->
  non-zero exit -> exact owned containers/processes are gone -> unrelated local services remain.
  (Verification: use a documented invalid timeout/port scenario and inspect exact container names.)
  [AC6]
- [x] Direct Strict Runner（直接严格运行器）: omit API base -> immediate named failure; provide API
  base and non-default frontend origin -> exact-origin startup with no server reuse. (Verification:
  run the minimized commands from the acceptance report.) [AC1; AC2]

## Documentation and Delivery

- [x] Local development docs describe one canonical command, Docker prerequisite, isolation,
  provider disclosure, and troubleshooting. (Verification: review rendered Markdown content.) [AC8]
- [x] Acceptance report contains actual commands and results, not “should pass” statements.
  (Verification: compare recorded output with current command results.) [AC5; AC8]
- [x] Changes are committed locally on `codex/v5.1-runtime-e2e`, with no merge or push. (Verification:
  inspect branch status and local log.) [AC9]
