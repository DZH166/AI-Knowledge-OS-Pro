# V5.3 Adaptive Policy and Retrieval Lab Checklist

## Implementation Completeness

- [x] Policy catalog has exactly one active default and immutable bounded versions. (Verification: direct lifecycle
  and database-constraint checks.) [AC1; AC2]
- [x] Draft commands are idempotent/concurrency-safe and reject executable, unknown, secret-looking, non-finite, or
  out-of-range inputs without writes. (Verification: adversarial command matrix.) [AC1]
- [x] Activation requires a matching passed fixed evaluation and expected active id; rollback is audited and
  restores a previously active version. (Verification: happy/stale/mismatch/concurrent lifecycle matrix.) [AC2]
- [x] New and continued Runs preserve exact policy identity, fingerprint, and snapshot across later activation,
  recovery, refresh, and replay. (Verification: compare direct rows, views, events, and trace.) [AC3]
- [x] Runtime retrieval applies requirement top-k, finite score threshold, per-source diversity, and bounded neighbor
  context from the pinned policy. (Verification: table-driven recording adapters and persisted calls.) [AC4]
- [x] Policy comparison and simulation produce deterministic diffs/deltas/digests with an explicit counterfactual
  boundary and no private facts. (Verification: repeated projections and serialized secret scan.) [AC5]
- [x] Candidate evaluation records and executes the exact policy fingerprint with 60 cases and zero provider calls.
  (Verification: fixed worker report and mismatch injection.) [AC6]

## Integration

- [x] EvidenceAgent reads active policy in a short SQL session before Run creation and never across external work.
  (Verification: exploding session/provider adapters and transaction probes.) [N8]
- [x] AgentRunner recovery and execution fences remain correct with adaptive tool arguments. (Verification: crash at
  prepare/execute/commit and late-result tests.) [AC3; AC4]
- [x] Policy evaluation travels through SQL Outbox → Redis/RQ → fixed worker → immutable snapshot, and activation
  consumes only the matching passed snapshot. (Verification: real Redis integration.) [AC2; AC6]
- [x] Legacy Runs/evaluations remain readable and populated migration round-trip preserves V5.2 semantics.
  (Verification: `0010→0009→0010` plus full legacy digest.) [N3; N5]
- [x] Production errors never fall back to the seeded/default/demo policy or fabricated simulation.
  (Verification: force 4xx/5xx/malformed payloads.) [F10]

## Build and Test

- [x] Backend compile, Ruff, focused V5.3 tests, adjacent Agent/evaluation recovery tests, and full suite pass. [AC8]
- [x] Frontend lint, typecheck, unit tests, production build, and production dependency audit pass. [AC7; AC8]
- [x] One Alembic head, model parity, populated round-trip, fixed 60-case evaluation, and acceptance gate pass. [AC8]
- [x] Secret, encoding, docs-link, version, CI, repository-clean, and release-safety gates pass. [AC8]

## End-to-End Scenarios

- [x] Create draft → compare → simulate → fixed evaluate → activate → open new Run → inspect pinned adaptive facts →
  rollback, using real Redis/RQ/Qdrant/backend/frontend/Chromium. [AC7]
- [x] Keyboard-only Policy Lab and 390px viewport remain operable with one active navigation item. [AC7]
- [x] Canonical isolated strict runtime passes twice and removes exact owned processes, containers, DB/WAL/SHM files.
  [AC8]

## Delegated Approval Record

Every acceptance criterion maps to observable checks. The checklist covers happy paths, immutability, invalid input,
concurrency, crash recovery, evaluation mismatch, privacy, migration, accessibility, full runtime, cleanup, and release.

Status: **approved for development**.
