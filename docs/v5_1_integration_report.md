# 溯知 V5.1 Integration and Release Report

- Date: 2026-08-26
- Branch: `codex/v5.1-integration-control`
- Baseline: `cf6438968822b43898c99166103449fb3bcc54c3`
- Version: `V5.1 / 5.1.0`
- Integrated tracks: Agent Intelligence, Product Experience, Runtime/Strict E2E

## Outcome

V5.1 is release-ready at the local integration level. The Evidence Agent decision upgrade, product
redesign, durable runtime and isolated end-to-end orchestration are integrated. The canonical runtime
has completed two consecutive real Redis/RQ + Qdrant runs with all 32 browser scenarios passing.

No real LLM, embedding or rerank credentials were configured in this stage. Every runtime manifest
declares `provider_mode=demo`; model-provider quality is therefore not claimed.

## Integrated Capabilities

### Agent Intelligence

- Continuation Run creates an idempotent follow-up from an Evidence Gap Report while preserving lineage.
- Tool selection records policy version, gap state and reason codes for search/open/neighbors.
- Conflict resolution prevents a model from silently choosing a winner between contested facts.
- Confidence calibration caps contested, single-source and independently corroborated claims conservatively.
- Deterministic entailment gates reject numeric, negation, polarity, scope and entity mismatches.

### Product Experience

- Workbench, Runs, Library and Artifacts form the four primary product routes.
- Run, Evidence Ledger, Inspector and Artifact copy is Chinese-first and includes inline explanations.
- Title editing, digest rotation, approval, keyboard focus restoration and mobile behavior are covered.
- Artifact → Claim → Evidence → Revision → Source deep links preserve exact hashes and locators.

### Runtime and Strict E2E

- Every run allocates isolated frontend/backend ports, SQLite database, Redis queue, Qdrant collection,
  worker name and container names.
- The live Agent scenario progresses through the production Redis/RQ worker and transactional outbox.
- RQ-compatible job identifiers now use only letters, numbers, underscores and hyphens.
- Qdrant is pinned to `qdrant/qdrant:v1.18.0`, aligned with the installed client.
- Twenty-one Next.js route groups are prewarmed before four parallel browser workers start.
- Cleanup targets only owned child processes, exact containers and the run-scoped database files.

## Verification Evidence

| Gate | Result |
|---|---|
| Backend full regression after code review | `457 passed, 1 skipped in 168.33s` |
| Runtime/worker/outbox focused regression after hardening | `31 passed` |
| Code-viewer stress regression | `24/24 passed` with four parallel workers |
| Frontend lint | passed |
| Frontend typecheck | passed |
| Frontend unit tests | `19 files / 81 tests passed` |
| Next production build | passed, 34 routes |
| Production dependency audit | 0 vulnerabilities |
| Fixed deterministic evaluation | 60/60 cases, status passed |
| V5 acceptance gate | passed, failures empty |
| Strict runtime run 1 | token `46296-bd464280`, `32 passed (34.1s)` |
| Strict runtime run 2 | token `29968-5960400f`, `32 passed (33.0s)` |
| Post-review strict runtime | token `45556-58d8dcf9`, `32 passed (35.9s)`, structured final verdict passed |
| Local release archive | 602 files, forbidden 0, missing 0, manifest verified, freshness current |

The two strict runs used different ports, databases, queues, Qdrant collections, worker names and
container names. Both runs removed their owned processes, containers and SQLite sidecars.

## Honest Boundary

- Model configuration was intentionally excluded from this stage.
- No real provider benchmark, paid API success or production cloud deployment is claimed.
- The current default remains a single-user local workspace; multi-tenant authorization and quotas
  are outside V5.1 scope.

## Release Boundary

Public version surfaces, CI packaging commands and local release tooling now target `V5.1 / 5.1.0`.
GitHub Release publication remains a separate repository-owner action after the branch is pushed and
the remote CI run is green.
