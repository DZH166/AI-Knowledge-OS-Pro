# V5.3 Adaptive Policy and Retrieval Lab Spec

## Background

V5.2 made the evidence-native Agent durable, explainable, privacy-bounded, and regression-controlled. The runtime
can plan, search, open exact evidence, read bounded neighbors, assess sufficiency, synthesize cited claims, recover
from interruption, and compare immutable evaluation snapshots. Its retrieval decisions are still compiled rules:
one fixed top-k, one fixed neighbor window, hard-coded policy versions, and no product workflow for creating,
testing, activating, or rolling back a candidate policy.

V5.3 makes decision policy a first-class, versioned product concept and lets retrieval parameters adapt to factual,
comparative, and temporal requirements. It uses the existing deterministic evaluation and trace facts; it does not
configure or claim real-provider quality.

## Goals

- Make Agent retrieval policy immutable, versioned, inspectable, testable, activatable, and safely reversible.
- Bind every new Run and evaluation to one exact policy snapshot and fingerprint.
- Adapt retrieval breadth, score filtering, source diversity, and neighbor context to requirement type.
- Simulate a candidate policy against persisted Run facts without re-executing a model, tool, or provider.
- Turn policy change into a visible baseline → candidate → evaluation → activation/rollback product workflow.

## Functional Requirements

- F1: The system maintains exactly one active default Agent policy and a bounded catalog of immutable policy
  versions with identity, version, label, configuration, fingerprint, lifecycle state, lineage, and timestamps.
- F2: A user can create an idempotent draft from the active policy or another selected version. Configuration is a
  strict bounded schema; arbitrary expressions, prompts, code, commands, paths, provider settings, and unknown
  fields are rejected.
- F3: A draft can be activated only when a completed passing fixed evaluation records the same policy fingerprint.
  Activation uses the expected current active id to prevent concurrent lost updates. A previously active version can
  be rolled back with the same concurrency fence and a durable audit record.
- F4: Every newly opened or continued Agent Run pins the current active policy id, version, fingerprint, and complete
  configuration snapshot. Later activation or rollback never changes an existing Run's behavior.
- F5: Retrieval uses the pinned policy to choose top-k by requirement kind, reject hits below a bounded score,
  enforce a per-source diversity cap, and choose bounded neighbor context. Tool arguments and public policy facts
  record the exact decision without exposing evidence text or private payloads.
- F6: A user can compare two policy versions and see field-level configuration differences plus lifecycle and
  fingerprint facts.
- F7: A user can simulate a candidate policy against one persisted Run. Simulation reports changed retrieval
  decisions, projected candidate-window and neighbor-context deltas, a deterministic digest, and an explicit
  counterfactual boundary. It performs zero model, retrieval, evidence-query, tool, provider, or write calls.
- F8: The fixed 60-case deterministic evaluation can target a safe policy id. Its worker executes with that exact
  policy snapshot and stores the matching fingerprint, while retaining the fixed script/dataset/path boundary and
  zero external provider calls.
- F9: The Policy Lab UI provides active-policy summary, bounded history, draft creation, field-level comparison,
  candidate simulation, fixed evaluation launch, guarded activation, and rollback. It remains in Developer Mode and
  does not add a fifth primary navigation item.
- F10: Run Trace and Evaluation Studio link policy ids/fingerprints to Policy Lab, and production request failures
  never fall back to demo policies or fabricated simulations.

## Non-Functional Requirements

- N1: Policy commands are idempotent by request id. Concurrent draft allocation, activation, rollback, duplicate
  dispatch, and stale expected-active ids converge to one truthful state or a bounded conflict.
- N2: Policy configuration and snapshots are canonical JSON with finite bounded integers, exact known fields, and
  SHA-256 fingerprints. Stored version content is never updated after insertion.
- N3: SQLite remains supported. Schema work keeps one Alembic head and passes populated
  upgrade/downgrade/upgrade with existing Run, evaluation, and evidence data preserved.
- N4: Policy lists, diffs, and simulations are bounded. Simulation reads allowlisted persisted facts only and never
  exposes prompts, raw private events, complete tool arguments, or secret-looking values.
- N5: Existing V5.2 EvidenceAgent, AgentControl, EvidenceIndex, Run recovery, SSE, approval, evaluation, release,
  and strict runtime contracts remain compatible.
- N6: Policy Lab is keyboard-operable, mobile-safe, uses semantic statuses and error regions, supports reduced
  motion, and keeps one active navigation item.
- N7: Tests are proportional to immutability, idempotency, concurrency, evaluation binding, runtime pinning,
  adaptive retrieval, simulation purity, privacy, accessibility, migration, and end-to-end risk.
- N8: The active policy lookup adds no provider or network call and does not keep a database transaction open across
  model, embedding, retrieval, evidence-query, or evaluator subprocess work.

## Out of Scope

- Real LLM, embedding, OCR, transcription, vision, or rerank configuration and quality benchmarking.
- Free-form policy DSL, arbitrary Python/JavaScript, prompt editing, arbitrary evaluator commands or datasets.
- Multi-Agent orchestration, autonomous external sends, plugin marketplaces, or MCP integration.
- Long-term user memory, multi-tenant authentication, RBAC, PostgreSQL, cloud deployment, or public GitHub Release.
- Predicting new model text or new evidence during simulation; counterfactual results cover deterministic policy
  decisions over facts already persisted by the selected Run.

## Acceptance Criteria

- AC1: Duplicate and concurrent draft commands create one immutable version per request, while invalid/unknown or
  out-of-range configuration is rejected without writing policy rows.
- AC2: Activation without a matching passed evaluation fails closed; activation with matching evidence changes the
  single active version once; stale concurrent activation is rejected; rollback restores a previously active version
  and records lineage/audit facts.
- AC3: Runs opened before and after activation keep different exact policy snapshots and fingerprints; recovery and
  continuation retain their pinned policy rather than reading the latest active version.
- AC4: Factual, comparative, and temporal requirements produce the configured top-k; score and per-source caps are
  deterministic; neighbor reads use the configured bounded window; trace facts match persisted tool calls.
- AC5: Policy comparison returns correct changed fields, and simulation returns a stable digest and correct projected
  deltas while exploding model/search/evidence/provider/write adapters remain untouched.
- AC6: A candidate-policy evaluation completes 60 unique fixed cases with zero provider calls and stores the exact
  candidate fingerprint; an evaluation/policy mismatch cannot authorize activation.
- AC7: A user can create a draft, compare it, simulate it, run its evaluation, activate it, observe a new Run pinned
  to it, and rollback from the Policy Lab on keyboard and 390px viewport without production-to-demo fallback.
- AC8: Full backend/frontend, migration, deterministic evaluation, strict Redis/Qdrant/RQ/browser, security,
  documentation, release, and repository-clean gates pass after V5.3 changes.

## Delegated Approval Record

The user explicitly requested uninterrupted execution and delegated per-step review and approval to Codex.
Self-review confirmed that every functional requirement maps to an acceptance criterion, the configuration is bounded
data rather than executable policy code, activation is evaluation-gated, simulation has an honest counterfactual
boundary, and model configuration, multi-agent work, memory, arbitrary tools, and deployment remain excluded.

Status: **approved for technical design**.
