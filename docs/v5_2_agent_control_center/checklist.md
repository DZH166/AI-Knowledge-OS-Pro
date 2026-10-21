# V5.2 Agent Evaluation and Control Center Checklist

## Implementation Completeness

- [x] Trace shows persisted identity, ordered timeline, calls, policy facts, budget, timing, replay integrity,
  terminal state, and triage. (Verification: compare trace response with direct seeded persistence facts.) [AC1]
- [x] Every private event is represented only by a redacted marker and no response contains prompt/API-key fixtures.
  (Verification: seed adversarial secrets in private payloads and scan serialized responses.) [AC1; N1]
- [x] Projection replay performs zero model/tool/provider calls and returns a stable digest plus stored-state match.
  (Verification: use exploding adapters/counters and repeat the replay.) [AC2]
- [x] Evaluation start is idempotent and persists an outbox message atomically. (Verification: duplicate and concurrent
  requests produce one evaluation/outbox identity.) [AC3]
- [x] Evaluation terminal snapshots are immutable and preserve complete provenance/metrics/gates/cases/errors.
  (Verification: execute valid/malformed/failed reports and attempt terminal rewrites.) [AC4]
- [x] Comparison reports correct deltas, gate changes, failure-set changes, compatibility, and verdict.
  (Verification: table-driven compatible, regressed, improved, identical, missing-metric, and incompatible fixtures.) [AC5]
- [x] Failure triage covers dispatch, worker interruption, executor timeout, malformed report, failed gates, and unknown.
  (Verification: inject each failure and assert facts/retryability/action.) [AC6]

## Integration

- [x] `agent.evaluate` travels through SQL outbox → dispatcher → RQ → worker → terminal snapshot exactly once.
  (Verification: real Redis integration plus duplicate wake-up and dead-letter tests.) [AC3; AC6]
- [x] Stale running evaluations become explicit interrupted failures and can be rerun as a new snapshot.
  (Verification: expire a lease, invoke recovery twice, and rerun.) [AC3; AC6]
- [x] Evaluator temporary database/report paths are isolated, cleaned, and never mutate the application database.
  (Verification: before/after semantic digest and filesystem residue checks.) [N3; N9]
- [x] HTTP inputs cannot select arbitrary modes, commands, datasets, or paths. (Verification: adversarial route matrix.) [F10]
- [x] Production request failures never fall back to recording/demo data. (Verification: force 4xx/5xx/malformed bodies.) [AC7]
- [x] Existing Run/Artifact/Evidence/SSE and strict runtime contracts remain compatible. (Verification: focused and full regression.) [N6]

## Build and Test

- [x] Alembic has one head and populated upgrade/downgrade/upgrade preserves expected legacy data. (Verification:
  run migration matrix and `verify_v5_migration.py --roundtrip`.) [N5]
- [x] Backend compile, Ruff, focused V5.2 tests, and full backend suite pass. (Verification: run documented commands.) [AC8]
- [x] Frontend lint, typecheck, unit tests, production build, and production dependency audit pass. (Verification:
  run npm gates.) [AC7; AC8]
- [x] Fixed 60-case deterministic evaluation and acceptance gate still pass with zero external calls. (Verification:
  regenerate a temporary report and run the acceptance checker.) [AC4; AC8]
- [x] Secret, encoding, docs-link, version, CI-contract, repository-clean, and release-safety checks pass. (Verification:
  run quick/release gates.) [AC8]

## End-to-End Scenarios

- [x] Start fixed evaluation → observe queued/running → complete 60 cases → open detail → inspect provenance and gates.
  (Verification: real Redis/RQ Chromium scenario.) [AC3; AC4; AC7]
- [x] Run two snapshots → compare → see stable/improved/regressed or explicit incomparable verdict with correct deltas.
  (Verification: browser scenario plus direct API fixture comparison.) [AC5; AC7]
- [x] Complete Agent Run → open trace → replay agrees with stored terminal state → private event remains redacted.
  (Verification: live worker browser scenario.) [AC1; AC2; AC7]
- [x] Keyboard-only evaluation/trace navigation and 390px viewport remain usable with one active navigation item.
  (Verification: Playwright accessibility/mobile scenario.) [AC7]
- [x] Canonical isolated Redis/Qdrant/worker/browser runtime passes twice and cleans exact owned resources.
  (Verification: run `python scripts/run_demo_e2e.py --strict` twice.) [AC8]

## Delegated Approval Record

- All AC criteria map to observable checks.
- The checklist includes happy paths, privacy, concurrency, failure, migration, cleanup, accessibility, and full E2E.
- No item relies on a real provider or an unbounded/manual-only assertion.

Status: **implementation and verification complete**.
