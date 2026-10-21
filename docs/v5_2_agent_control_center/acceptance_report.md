# 溯知 V5.2 Agent Evaluation and Control Center Acceptance Report

- Date: 2026-08-27
- Branch: `codex/v5.2-agent-evaluation-control`
- Version: `V5.2 / 5.2.0`
- Provider boundary: model configuration intentionally unchanged; fixed evaluation made zero external calls

## Outcome

V5.2 turns the existing evidence-native Agent runtime into an inspectable and regression-controlled product.
A user can open a sanitized production Run trace, verify projection replay integrity, start a durable fixed
evaluation, inspect its 60 cases, compare two immutable snapshots, and receive deterministic failure triage.

The feature is implemented behind one small AgentControl Interface. SQL persistence, transactional outbox,
Redis/RQ dispatch, fixed subprocess evaluation, leases, stale recovery, report validation, trace projection,
comparison, and triage stay behind that Interface.

## Delivered Capabilities

### Run Trace and Projection Replay

- Production Run identity, event timeline, tool/model summaries, policy facts, budgets, timing, checkpoints,
  replay digest, terminal-state match, warnings, and failure triage.
- Private event payloads, model prompts, tool arguments, checkpoint state, credentials, and secret-looking values
  never enter the response. Private events remain visible only as redacted markers.
- Replay reads persisted facts only and executes zero models, tools, vector searches, or provider calls.

### Durable Evaluation Studio

- Idempotent evaluation creation with evaluation row and Outbox message in the same SQL transaction.
- Real `agent.evaluate` RQ task, bounded execution/lease time, dead-letter failure state, stale-running recovery,
  terminal immutability, and late-result fencing.
- Fixed argument-list subprocess uses only `scripts/evaluate_agentic_rag.py` and
  `evaluation/v5/cases.jsonl` in an isolated temporary directory.
- Secrets are scrubbed from the child environment; report size, regular-file status, JSON schema, dataset,
  evaluator digest, hard gates, 60 unique cases, category matrix, case/failure consistency, and zero provider
  calls are validated before persistence.

### Evaluation History and Comparison

- Evaluation catalog, queued/running/passed/failed detail, metrics, hard gates, category coverage, case table,
  failure reasons, provenance digests, status filtering, and rerun flow.
- Comparison checks schema and dataset compatibility before calculating metric/gate/case deltas.
- Comparison also discloses whether the policy fingerprint changed and shows both fingerprints, so a policy A/B
  test is never mistaken for two runs of identical decision rules.
- Verdicts are bounded to improved, stable, regressed, or incomparable; incompatible snapshots never receive
  misleading quality deltas.

### Deterministic Failure Triage

- Bounded categories for dispatch failure, Worker interruption, executor timeout/failure, malformed report,
  quality-gate failure, budget exhaustion, insufficient evidence, tool failure, provider unavailability,
  cancellation, and unknown failure.
- Each result includes sanitized supporting facts, retryability, and a concrete suggested next action.

## Verification Evidence

| Gate | Result |
|---|---|
| Pure trace/replay/comparison/triage regression | `29 passed` |
| V5.2 migration/model parity | `8 passed` |
| SQL idempotency/concurrency/late-result regression | `41 passed` combined focused checkpoint |
| Worker/executor/outbox regression | `41 passed` combined focused checkpoint |
| API strict-input/privacy regression | `39 passed` combined focused checkpoint |
| Backend full regression | `536 passed, 1 skipped in 236.78s` |
| Frontend lint | passed, zero warnings |
| Frontend typecheck | passed |
| Frontend unit tests | `25 files / 98 tests passed` |
| Next.js production build | passed, 35 static pages plus dynamic routes |
| Production dependency audit | `0 vulnerabilities` |
| Alembic | one head: `0009_v5_2_agent_control` |
| Populated migration round-trip | `0009→0006→0009`, semantic legacy digest preserved |
| Fixed evaluation | `60/60`, all hard gates passed, external provider calls `0` |
| Strict runtime run 1 | token `18664-deccddad`, `36 passed (1.2m)` |
| Strict runtime run 2 | token `24528-b972f20c`, `36 passed (1.2m)` |
| Secret scan | tracked files, findings `0` |
| Quick quality/CI contract | passed |

The two strict runs used independent frontend/backend ports, SQLite databases, Redis queues, Qdrant
collections, Worker names, and container names. Both removed all owned processes, containers, databases,
WAL files, and SHM files. An earlier adversarial run failed on an over-narrow E2E expectation and also cleaned
all resources; the product correctly returned `insufficient_evidence`, and the regression now covers all four
legal terminal states.

## Adversarial Review Closed During Development

- Public allowlisted fields carrying embedded secret values are redacted, not merely trusted by field name.
- Missing comparison metrics and mismatched gate sets produce `incomparable`, not `stable`.
- Concurrent starts and executions converge to one evaluation and one executor call.
- Outbox failure rolls back evaluation creation atomically.
- Expired Worker leases become explicit failures; late executor results cannot overwrite them.
- Outbox database state and logs redact secret-looking broker errors.
- Child evaluation environment removes provider secrets; reports must be regular bounded files.
- The child environment now uses a minimal allowlist and explicitly disables every known provider credential;
  AWS, Google, GitHub, database, and unknown secret variables are excluded by default.
- The Run goal and policy values pass secret-shape sanitization, and private events cannot contribute policy facts.
- Report JSON and numeric fields reject `NaN`, positive infinity, and negative infinity as malformed instead of
  storing a false or unserializable quality result.
- Metric validation/comparison and metric labels/units now read centralized catalogs instead of scattered strings.
- HTTP interfaces reject arbitrary modes, commands, datasets, paths, output locations, unsafe ids, and extras.
- Frontend contracts cross-check case counts, category totals, failure ids, pass rates, gates, provider boundary,
  event counts, redaction counts, and replay sequence claims.
- Keyboard, error, no-demo-fallback, mobile overflow, reduced motion, URL comparison state, table captions, and
  navigation budgets are covered.

The first post-review full run exposed two release-scan failures and one timing-sensitive lease test. The release
scanner correctly rejected a secret-shaped test literal, so the fixture now remains adversarial without resembling a
stored credential. The lease test now observes actual SQL lease renewal instead of assuming a background thread runs
within a fixed sleep; it passed eight times while a production frontend build competed for CPU.

## Honest Boundary

- This does not configure or benchmark a real LLM, embedding, OCR, vision, transcription, or rerank provider.
- The 60-case result proves deterministic architecture, safety, persistence, recovery, and regression behavior;
  it is not a claim about real-model answer quality.
- Replay reconstructs persisted projection facts. It never replays historical model/tool/external side effects.
- Multi-Agent orchestration, policy editing, arbitrary dataset upload, multi-tenant authorization, PostgreSQL,
  cloud deployment, and public GitHub Release publication remain outside V5.2.

## Release Evidence

`AI-Knowledge-OS-Pro-V5.2-20260827.zip` contains 651 tracked source files. The release checker reported forbidden
files `0`, missing files `0`, a verified per-file manifest, and current source freshness. The archive SHA-256 is
stored in `AI-Knowledge-OS-Pro-V5.2-20260827.zip.sha256` so the source documentation does not recursively change
the digest it describes.
