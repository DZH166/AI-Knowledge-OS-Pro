# V5.3 Adaptive Policy and Retrieval Lab Tasks

## File List

| Operation | File | Responsibility |
|---|---|---|
| Create | `backend/app/modules/agent_policy/*` | Deep policy Interface and pure decisions/simulation. |
| Create | `backend/app/models/agent_policy.py` | Immutable versions, commands, and activation audit. |
| Create | `backend/alembic/versions/0010_v5_3_agent_policy.py` | Policy schema, default seed, Run/evaluation pinning columns. |
| Modify | EvidenceAgent/AgentRunner files | Pin and execute adaptive policy. |
| Modify | AgentControl/evaluator files | Candidate-policy fixed evaluation. |
| Create | policy HTTP schema/routes | Strict lifecycle, comparison, and simulation transport. |
| Create | `backend/tests/test_v5_3_*.py` | Pure, SQL, migration, runtime, evaluation, API tests. |
| Create | `frontend/modules/agent-policy/*` | Runtime contracts and transport client. |
| Create | `frontend/components/agent-policy/*` | Policy catalog/detail/lab UI. |
| Create | `frontend/app/policies/*` | Policy Lab routes. |
| Create | `frontend/e2e/v5-3-agent-policy.spec.ts` | Full candidate-to-rollback scenario. |
| Modify | docs/version/release/navigation | V5.3 delivery and discovery surfaces. |

## T1: Freeze Policy Configuration and Pure Decisions

**Files:** policy contracts/config/decision/comparison/simulation inputs, pure tests.

**Depends on:** None.

**Steps:** define strict frozen config and result contracts; implement requirement-kind top-k, score/source filtering,
neighbor windows, fingerprints, field diff, and pure simulation projection; attack unknown fields, booleans-as-integers,
non-finite values, range edges, secret-looking labels, duplicate hits, and unstable ordering.

**Verification:** focused pure tests and Ruff; repeat digest/order fixtures.

## T2: Add Durable Policy Schema and Migration

**Files:** policy model, AgentRun/evaluation model changes, `0010` migration, migration tests.

**Depends on:** T1.

**Steps:** add immutable version/command/activation tables; seed one canonical default active policy; add legacy-safe
Run/evaluation policy columns and indexes; verify constraints, one head, model parity, and populated round-trip.

**Verification:** focused migration tests plus `verify_v5_migration.py --roundtrip` updated for `0010`.

## T3: Implement SQL AgentPolicy

**Files:** policy Interface/service/wiring and SQL tests.

**Depends on:** T1, T2.

**Steps:** implement catalog/detail/active, idempotent draft allocation, compare, evaluation-gated activation, audited
rollback, CAS conflict handling, and pure simulation data loading; stress duplicate/concurrent commands and immutable
content.

**Verification:** SQLite lifecycle/concurrency tests with injected stale ids, mismatched evaluations, and rollback.

## T4: Pin Policy to Agent Runs

**Files:** EvidenceAgent contracts/service/view/trace and adjacent tests.

**Depends on:** T3.

**Steps:** inject short-session active-policy port; pin exact policy on new Runs; preserve policy on continuation; expose
safe identity in Run view/trace; keep legacy Runs readable.

**Verification:** open-before/after activation, continuation, recovery, idempotency, and legacy projection tests.

## T5: Execute Adaptive Retrieval

**Files:** AgentRunner/tools/policy decisions and runtime tests.

**Depends on:** T4.

**Steps:** use pinned config for top-k, score threshold, source cap, and neighbor window; persist exact arguments and
policy audit facts; keep search/evidence calls outside SQL; cover execution fences and recovery for changed arguments.

**Verification:** table-driven factual/comparative/temporal tests, diversity/score/window tests, crash recovery, full
existing Agent runtime regression.

## T6: Evaluate Candidate Policies

**Files:** AgentControl contracts/service/executor/report, evaluator script, tests.

**Depends on:** T3, T5.

**Steps:** accept optional safe policy id; persist exact version/fingerprint; pass internally generated temporary
config to the fixed evaluator; execute its AgentRunner with that config; reject mismatch, arbitrary fields/paths,
secrets, non-finite values, and stale policy state.

**Verification:** fixed evaluator 60/60 for default and candidate, zero provider calls, worker cleanup and activation
gate tests.

## T7: Add Strict Policy HTTP Interfaces

**Files:** policy schemas/routes/router and API tests.

**Depends on:** T3, T6.

**Steps:** expose bounded catalog/detail/active/diff/simulation and draft/activate/rollback; add candidate evaluation
binding; map conflicts without raw SQL/path/config leakage.

**Verification:** API happy/error/adversarial matrix, production no-demo-fallback, response contract validation.

## T8: Build Frontend Contracts and Policy Lab

**Files:** frontend policy module/components/pages/styles/tests and discovery links.

**Depends on:** T7.

**Steps:** runtime-validate every payload; render active/history/detail/diff/simulation; create drafts; launch candidate
evaluation; enable activation only with passed matching evidence; rollback with expected-active fence; add accessible
responsive states and policy links without primary-nav growth.

**Verification:** Vitest, lint, typecheck, production build, keyboard, 390px, malformed/error/no-fallback tests.

## T9: Add Full Runtime Scenario

**Files:** V5.3 Playwright spec, strict runtime prewarm/static contracts.

**Depends on:** T8.

**Steps:** create draft → compare → simulate → fixed evaluate through Redis/RQ → activate → open Run and inspect pinned
policy/retrieval facts → rollback; verify cleanup, privacy, single nav, and honest provider boundary.

**Verification:** focused Chromium then canonical isolated strict runtime twice.

## T10: Version, Review, Release, and Push

**Files:** V5.3 docs, README, versions, CI/release surfaces, append-only logs.

**Depends on:** T9.

**Steps:** update truthful product/resume story and glossary; run full backend/frontend/migration/evaluation/security
gates; perform two-axis Standards/Spec and adversarial review; fix every finding; regenerate verified archive; push and
compare local/remote SHA.

**Verification:** clean worktree, all checklist items checked, zero open review finding, verified fresh archive, remote
SHA equality.

## Execution Order

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9 -> T10
```

## Delegated Approval Record

Every planned Module has a task and verification. Persistence precedes runtime integration; pure decisions precede
SQL; backend contracts precede frontend; focused/adversarial tests precede full E2E. No task requires real-provider
credentials or a pause for user approval.

Status: **approved for acceptance design**.
