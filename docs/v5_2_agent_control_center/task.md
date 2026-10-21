# V5.2 Agent Evaluation and Control Center Tasks

## File List

| Operation | File | Responsibility |
|---|---|---|
| Create | `backend/app/models/agent_evaluation.py` | Durable evaluation snapshot and lease state. |
| Create | `backend/app/modules/agent_control/*` | Deep control Interface and implementation. |
| Create | `backend/app/schemas/agent_control_schema.py` | Strict HTTP contracts. |
| Create | `backend/app/api/routes_agent_control.py` | Evaluation and trace routes. |
| Create | `backend/app/tasks/evaluation_tasks.py` | Fixed evaluation worker entrypoint. |
| Create | `backend/alembic/versions/0009_v5_2_agent_control.py` | Upgrade/downgrade schema. |
| Modify | `backend/app/services/{task_broker,outbox_dispatcher}.py` | Durable `agent.evaluate` dispatch and dead-letter state. |
| Modify | `backend/app/worker.py` | Stale evaluation recovery. |
| Create | `backend/tests/test_v5_2_*.py` | Persistence, replay, privacy, comparison, worker, API, migration tests. |
| Create | `frontend/modules/agent-control/*` | Validated frontend contract and client. |
| Create | `frontend/components/agent-control/*` | Evaluation and trace presentation. |
| Create | `frontend/app/evaluations/*` | Catalog and detail routes. |
| Create | `frontend/app/runs/[runId]/trace/page.tsx` | Trace route. |
| Modify | Runs/navigation product files | Discoverable links without primary-nav expansion. |
| Create | `frontend/e2e/v5-2-agent-control.spec.ts` | Full product/runtime scenario. |
| Modify | Version, CI, release, README, logs | V5.2 delivery surfaces. |

## T1: Freeze Contracts and Pure Projections

**Files:** `backend/app/modules/agent_control/{contracts,interface,trace,comparison,triage}.py`, focused tests.

**Depends on:** None.

**Steps:**
1. Define the small command/query Interface and immutable result contracts.
2. Implement allowlisted trace projection, private redaction, replay digest/state match, comparison, and triage.
3. Add malformed payload, secret leakage, incompatible comparison, unknown failure, and stable-digest tests.

**Verification:** Run focused pure-module tests; require all adversarial fixtures to pass.

## T2: Add Durable Evaluation Schema

**Files:** model, `0009` migration, model registry, migration tests.

**Depends on:** T1.

**Steps:**
1. Add constrained evaluation identity/status/lease/report fields and indexes.
2. Add upgrade/downgrade migration and model registration.
3. Verify one Alembic head and populated `0008→0009→0008→0009` preservation behavior.

**Verification:** Run V5.2 migration tests and the repository migration round-trip.

## T3: Implement SQL AgentControl

**Files:** `service.py`, `wiring.py`, persistence tests.

**Depends on:** T1, T2.

**Steps:**
1. Implement idempotent start plus same-transaction outbox creation.
2. Implement bounded catalog/detail/comparison and run-trace queries.
3. Implement lease claim, terminal immutability, failure recording, and stale-running recovery.
4. Stress duplicate request, duplicate worker, stale lease, terminal mutation, and missing-run paths.

**Verification:** Run SQL concurrency and lifecycle tests against isolated SQLite databases.

## T4: Implement the Fixed Evaluation Executor and Worker Path

**Files:** `executor.py`, evaluation task, task broker, outbox dispatcher, worker, tests.

**Depends on:** T3.

**Steps:**
1. Implement fixed argument-list subprocess execution in an isolated temporary directory.
2. Validate schema, deterministic label, dataset identity, evaluator identity, and zero external calls.
3. Add RQ topic mapping, safe job id, retry/dead-letter handling, and stale recovery.
4. Inject timeout, non-zero exit, malformed JSON, dishonest provider count, duplicate dispatch, and cleanup failures.

**Verification:** Run executor/worker/outbox tests, then a real Redis worker evaluation once.

## T5: Add Strict HTTP Interfaces

**Files:** schema, routes, router registration, API tests.

**Depends on:** T3, T4.

**Steps:**
1. Add start/list/detail/compare evaluation routes and run-trace route.
2. Bound filters, labels, ids, list sizes, and response payloads.
3. Map domain errors to honest HTTP errors without raw exception or path disclosure.

**Verification:** Run route contracts including invalid mode/path/body/filter and production error cases.

## T6: Add Frontend Runtime Contracts and Client

**Files:** `frontend/modules/agent-control/*` and tests.

**Depends on:** T5.

**Steps:**
1. Define strict runtime schemas for summaries, details, comparisons, trace, triage, and receipts.
2. Implement the transport client and bounded polling helper.
3. Reject malformed success envelopes, private payload fields, dishonest provider modes, and invalid deltas.

**Verification:** Run focused Vitest contracts and transport tests.

## T7: Build the Run Trace Product Surface

**Files:** trace components/page, Run pages, styles, tests.

**Depends on:** T6.

**Steps:**
1. Present identity, replay integrity, policy facts, phases, events, calls, budgets, timings, and triage.
2. Clearly mark redacted events and provider/cost measurement boundaries.
3. Add accessible link from run list/workspace and resilient loading/error/empty states.

**Verification:** Run component tests, typecheck, keyboard inspection, narrow-viewport check, and production-error test.

## T8: Build Evaluation Catalog, Detail, and Comparison

**Files:** evaluation pages/components/styles/tests.

**Depends on:** T6.

**Steps:**
1. Add fixed-evaluation start/rerun, bounded polling, status and provenance disclosure.
2. Present metrics, hard gates, categories, cases, failures, and triage.
3. Add two-snapshot comparison with compatibility and regression warnings.
4. Add Runs and Developer Mode discovery links without changing primary-nav count.

**Verification:** Run component tests covering queued→running→passed, failed, incompatible, empty, and API-error states.

## T9: Add Full End-to-End and Runtime Evidence

**Files:** E2E spec, runtime prewarm/static checks, backend runtime tests.

**Depends on:** T4, T5, T7, T8.

**Steps:**
1. Start one fixed evaluation through real Redis/RQ and poll it to a terminal state.
2. Open evaluation detail/comparison and a real Agent trace in Chromium.
3. Verify zero provider calls, replay integrity, redaction, failure labels, exact cleanup, keyboard and mobile behavior.

**Verification:** Run targeted Playwright, then the canonical strict runtime twice.

## T10: Version, Documentation, Release, and Final Adversarial Review

**Files:** README, V5.2 docs, version/CI/release surfaces, append-only logs.

**Depends on:** T9.

**Steps:**
1. Update truthful V5.2 positioning, glossary, architecture, demo/resume path, and provider boundary.
2. Run full backend/frontend/migration/evaluation/security/release gates.
3. Perform two-axis standards/spec review and explicit privacy/concurrency/failure adversarial review.
4. Fix every current-scope finding, rerun affected/full gates, commit, archive, and push the V5.2 branch.

**Verification:** Require clean worktree, verified release archive, remote SHA equality, and zero open P0/P1 findings.

## Execution Order

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9 -> T10
```

## Delegated Approval Record

- Every planned Module and product surface has an ordered task and concrete verification.
- Persistence precedes dispatch; backend contracts precede frontend contracts; focused tests precede E2E.
- Adversarial checks occur inside each task rather than being postponed to the end.
- No task requires real-provider configuration or user approval during execution.

Status: **approved for acceptance design**.
