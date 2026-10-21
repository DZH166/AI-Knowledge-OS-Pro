# 溯知 V5.3 Adaptive Policy and Retrieval Lab Acceptance Report

- Date: 2026-08-28
- Branch: `codex/v5.3-adaptive-policy-retrieval`
- Version: `V5.3 / 5.3.0`
- Provider boundary: real-model configuration intentionally unchanged; fixed evaluation made zero external calls

## Outcome

V5.3 turns retrieval policy from compiled constants into an immutable, versioned, evaluation-gated product concept.
Users can create a bounded draft, compare field changes, simulate it over persisted Run decisions, run the fixed
60-case evaluation, activate it with an optimistic concurrency fence, observe new Runs pinning the exact snapshot,
and roll back to a previously active version.

The implementation sits behind the small `AgentPolicy.submit / inspect / simulate` Interface. SQL lifecycle,
idempotency, active uniqueness, activation audit, strict configuration, adaptive decisions, comparison, and
counterfactual projection remain inside the Module.

## Delivered Capabilities

### Immutable Policy Lifecycle

- One seeded default active policy and one database-enforced active version.
- Idempotent, concurrency-safe immutable draft allocation with canonical JSON and SHA-256 fingerprint.
- Evaluation-gated activation, expected-active CAS, append-only activation audit, and audited rollback.
- Strict bounded integer configuration; no arbitrary DSL, prompt, code, command, path, provider, or unknown field.

### Run Pinning and Adaptive Retrieval

- New Runs pin policy id/version/fingerprint/config; continuation inherits its parent; legacy Runs remain readable.
- Requirement-kind Top-K for factual, comparative, and temporal work.
- Finite score threshold, per-source diversity cap, duplicate removal, and bounded neighbor context.
- Exact policy arguments and reason facts are persisted in ToolCall/Event and visible through Run Trace.

### Counterfactual Simulation and Candidate Evaluation

- Pure simulation over persisted allowlisted decisions with stable digest and explicit no-execution boundary.
- Candidate policy flows through SQL Outbox → Redis/RQ → fixed subprocess evaluator.
- Internal temporary policy file, fixed script/dataset, scrubbed environment, matching report fingerprint, 60 cases,
  and zero provider calls.
- A mismatch or failed evaluation cannot authorize activation.

### Policy Lab Product Surface

- Active policy, immutable history, bounded draft form, detail, field diff, simulation, evaluation, activation, rollback.
- Links from Evaluation Studio, evaluation detail, Run Trace, and System Observability.
- Four primary product routes remain unchanged; `/policies` maps to the existing System developer destination.

## Verification Checkpoint

| Gate | Result |
|---|---|
| Full backend regression | `582 passed, 1 skipped in 235.58s` |
| Frontend unit tests | `28 files / 105 tests passed` |
| Frontend lint/typecheck | passed |
| Next.js production build | passed, 36 static pages plus dynamic routes |
| Production dependency audit | `0 vulnerabilities` |
| Fixed candidate evaluation | `60/60`, zero external provider calls |
| Strict runtime | tokens `22736-058d00e4` and `35052-dc01de48`, each `40/40 passed` with exact cleanup |
| Alembic | one head: `0010_v5_3_agent_policy`; populated round-trip passed |
| Two-axis review | Standards `0`; Spec `0` remaining findings |
| Repository quick gate | passed, including version/docs/UI/E2E-static/CI contracts |
| Release archive | `693` tracked files; forbidden `0`; missing `0`; manifest verified; freshness current |
| GitHub branch | `codex/v5.3-adaptive-policy-retrieval`; final local/remote SHA equality verified |

Every V5.3 checklist item is closed. The archive is `AI-Knowledge-OS-Pro-V5.3-20260828.zip`; its detached SHA-256
sidecar is kept outside tracked source so documentation does not create a recursive archive-hash dependency.

## Adversarial Findings Closed During Development

- SQLite timestamps lacked UTC offsets; the policy Interface now normalizes them instead of weakening frontend ISO validation.
- An E2E assertion used already-visible copy as an activation signal; it now waits for exact POST responses.
- The Run response projector omitted a correctly persisted policy snapshot; production API integration coverage now locks it down.
- Corrupt, partial, non-canonical, or fingerprint-mismatched snapshots fail before search or evaluation.
- Concurrent activation with the same expected active id produces one winner and one bounded conflict.
- Production policy request failures render an explicit error and never use seeded/demo data as fallback.
- Simulation reads only allowlisted public `tool.started` retrieval-policy facts joined to completed ToolCalls. It
  never reads private query/argument payloads, and failed attempts cannot change deltas or the simulation digest.
- Run Trace now exposes the exact pinned policy SHA-256, and strict E2E verifies both that fingerprint and adaptive
  Top-K after the Run reaches a terminal state.

## Honest Boundary

- No real LLM, embedding, OCR, vision, transcription, or rerank quality benchmark is claimed.
- Counterfactual simulation projects recorded parameter decisions only; it does not predict new evidence or text.
- Policies cannot edit prompts or execute code.
- Multi-Agent orchestration, long-term memory, multi-tenant authorization, PostgreSQL, and cloud deployment remain
  outside V5.3.
