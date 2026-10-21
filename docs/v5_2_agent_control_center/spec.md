# V5.2 Agent Evaluation and Control Center Spec

## Background

V5.1 already persists Agent runs, public/private events, tool calls, model-call summaries, checkpoints,
immutable evidence, fixed deterministic evaluation reports, and runtime health signals. These facts are
currently split across run pages, system observability, JSON reports, and command-line gates. A reviewer
can see that the system works, but cannot use one product surface to explain why a run behaved as it did,
replay its persisted history, compare evaluation snapshots, or triage a failure.

V5.2 turns those existing engineering facts into a product-grade Agent control center. It remains fully
usable without real model credentials and must never relabel deterministic recording evidence as a real
provider benchmark.

## Goals

- Make each production Agent run explainable from persisted facts without exposing private prompts.
- Make deterministic evaluation runs durable, repeatable, comparable, and visible in the product.
- Classify failures with deterministic evidence and an actionable next step.
- Preserve the four primary product routes while adding an expert control surface reachable from Runs.
- Produce portfolio evidence that demonstrates Agent evaluation, observability, recovery, and regression control.

## Functional Requirements

- F1: A user can open a persisted Agent run trace containing its identity, phases, public events, redacted
  private-event markers, tool-call summaries, model-call summaries, policy versions, budget usage, and timing.
- F2: The system can replay a run's persisted event history without executing a model or tool, report replay
  integrity, and compare the replayed terminal projection with the stored Run state.
- F3: A user can start an idempotent fixed deterministic evaluation. The request is persisted before dispatch,
  progresses through queued/running/passed/failed states, and is executed by the existing durable worker path.
- F4: Every evaluation snapshot preserves dataset identity, evaluator identity, policy fingerprint, provider
  boundary, aggregate metrics, hard gates, case results, failure ids, timestamps, and an honest error record.
- F5: A user can list and inspect evaluation snapshots, filter by status, rerun the fixed evaluation, and view
  category-level and case-level failures without reading a raw JSON file.
- F6: A user can compare two completed evaluation snapshots. The comparison reports metric deltas, hard-gate
  changes, new/resolved failing cases, policy/dataset compatibility, and a deterministic regression verdict.
- F7: Agent run failures and evaluation failures are classified into a bounded taxonomy with supporting facts,
  retryability, and a suggested next action. Unknown states remain explicitly unclassified.
- F8: The control-center UI provides an evaluation catalog, evaluation detail, comparison workflow, and a
  run-trace page. It distinguishes production data from deterministic evaluation data in Chinese-first copy.
- F9: Run and evaluation pages link to the new control surfaces without adding another primary navigation item.
- F10: The fixed evaluation remains executable with zero external provider calls and refuses unsupported modes,
  arbitrary dataset paths, arbitrary commands, and unsafe output locations.

## Non-Functional Requirements

- N1: Trace and evaluation interfaces expose allowlisted summaries only; raw prompts, credentials, complete
  private event payloads, and secret-looking environment values must never be returned.
- N2: Commands are idempotent by request id. Duplicate dispatch, concurrent execution, stale worker leases,
  and worker interruption must converge to one truthful evaluation state.
- N3: Evaluation execution uses an isolated temporary database and fixed repository dataset. It must not mutate
  the user's knowledge base, Agent runs, evidence index, or configured providers.
- N4: Catalog responses are bounded; large case payloads are returned only from detail interfaces.
- N5: SQLite remains supported. Schema changes require one Alembic head and verified upgrade/downgrade/upgrade.
- N6: Existing V5.1 Agent, EvidenceIndex, Workbench, Runs, Library, Artifacts, SSE, and strict runtime behavior
  must remain backward compatible.
- N7: Pages must support keyboard operation, visible focus, semantic status/error regions, narrow mobile layouts,
  and reduced-motion preferences already established by the product.
- N8: The implementation must add tests proportional to persistence, dispatch, sanitization, replay, comparison,
  failure, accessibility, and end-to-end risk.
- N9: Generated evaluation databases and temporary reports stay in ignored temporary directories and are cleaned
  after both success and handled failure.

## Out of Scope

- Real LLM, embedding, OCR, transcription, vision, or rerank configuration and benchmarking.
- Multi-Agent orchestration, autonomous external writes, arbitrary tool/plugin execution, or MCP integration.
- Editing prompts or policies from the UI.
- Uploading arbitrary evaluation datasets or executing arbitrary filesystem paths.
- Multi-tenant authentication, RBAC, PostgreSQL migration, cloud deployment, or public GitHub Release publication.
- Re-executing historical external side effects; replay is projection replay over persisted facts only.

## Acceptance Criteria

- AC1: A terminal production run opens a trace whose identity, ordered events, calls, policy facts, timings, budget,
  and terminal state agree with persisted records; private payloads are redacted.
- AC2: Projection replay performs zero model/tool/provider calls, produces a stable digest, and reports whether
  the replayed terminal state matches the stored state.
- AC3: Two duplicate evaluation-open requests create one evaluation id; the durable worker completes it once or
  leaves an explicit recoverable/failed state after an injected failure.
- AC4: A completed evaluation detail shows 60 unique cases, the fixed dataset/evaluator digests, zero external
  provider calls, all aggregate metrics, gates, categories, and case outcomes.
- AC5: Comparing compatible snapshots produces correct metric deltas and case-set changes; incompatible dataset
  snapshots never receive a misleading quality verdict.
- AC6: Injected dispatch, worker, malformed-report, and stale-running failures each receive a deterministic failure
  category, supporting fact, retryability flag, and suggested action.
- AC7: The evaluation catalog, detail, comparison, and run trace are keyboard-operable, mobile-safe, and never
  silently fall back to recording/demo data after a production request fails.
- AC8: Existing full backend/frontend, migration, deterministic evaluation, strict Redis/Qdrant/worker browser,
  release-safety, and documentation gates pass after V5.2 changes.

## Delegated Approval Record

The user explicitly delegated document approval to Codex and requested uninterrupted execution. Self-review found:

- Every F requirement maps to at least one AC criterion.
- Model configuration, multi-agent behavior, policy editing, arbitrary execution, and deployment are excluded.
- The scope fits one implementation cycle by using the existing fixed evaluator and durable worker infrastructure.
- Adversarial cases cover privacy leakage, duplicate requests, stale workers, incompatible comparisons, malformed
  reports, production-data mutation, and demo fallback.

Status: **approved for technical design**.
