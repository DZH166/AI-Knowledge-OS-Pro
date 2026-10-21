# V5.2 Agent Evaluation and Control Center Plan

## Architecture Overview

Create one deep `agent_control` Module behind a small command/query Interface. Callers learn only three operations:

1. submit a deterministic evaluation command;
2. inspect control-center queries (evaluation catalog/detail/comparison or run trace);
3. execute/recover one persisted evaluation from the worker seam.

The SQL implementation hides persistence, idempotency, report validation, comparison, replay projection,
sanitization, policy fingerprinting, failure triage, lease handling, and outbox creation. Evaluation execution is a
real internal Seam with two Adapters: a fixed subprocess Adapter for production/local runtime and a recording
Adapter for tests. The external Interface is also the test surface.

```text
Routes / RQ task
       │
       ▼
AgentControl Interface
       │
       ├── SQL state + outbox + leases
       ├── RunTraceProjector (pure internal implementation)
       ├── EvaluationComparator (pure internal implementation)
       ├── FailureTriage (pure internal implementation)
       └── EvaluationExecutor port
               ├── FixedSubprocessEvaluationAdapter
               └── RecordingEvaluationAdapter
```

## Core Data Structures and Interfaces

### Commands

- `StartEvaluation(request_id, label)` — fixed deterministic dataset/mode only.
- `ExecuteEvaluation(evaluation_id, worker_id)` — claim one lease and execute at most one snapshot.
- `RecoverEvaluations(now)` — fail expired running leases with an explicit interruption category.

### Queries

- `ListEvaluations(status, limit)` — bounded summaries.
- `GetEvaluation(evaluation_id)` — metrics, gates, provenance, categories, cases, triage.
- `CompareEvaluations(left_id, right_id)` — compatibility plus deltas/regression verdict.
- `GetRunTrace(run_id)` — sanitized trace and deterministic projection replay result.

### Persisted Evaluation

`AgentEvaluation` stores identity, request id, label, deterministic mode, status, dataset/evaluator/policy
fingerprints, bounded summary JSON, full report JSON, error/triage fields, attempt, lease, and timestamps.
The full fixed report is immutable after a terminal state.

### Trace Projection

The projector consumes existing `AgentRun`, `AgentEvent`, `AgentToolCall`, `AgentModelCall`, `AgentCheckpoint`,
`AgentGate`, and relevant Outbox rows. It returns allowlisted payloads, redacted markers, derived durations,
policy facts, replay digest/integrity, and failure triage. It never calls the Agent Controller, model, tools, or providers.

## Module Design

### `agent_control` Module

**Responsibility:** Own durable evaluation control and read-only run explanation.

**Public interface:** `submit(command)`, `inspect(query)`, `execute(command, executor)`, `recover(command)`.

**Dependencies:** SQLAlchemy session factory; injected `EvaluationExecutor` only for execution.

### Evaluation Executor Seam

**Responsibility:** Produce one fixed deterministic report in an isolated directory.

**Interface:** `run(evaluation_id) -> EvaluationExecutionResult` with validated report and cleanup evidence.

**Adapters:** Fixed subprocess Adapter and test recording Adapter.

### API Module

**Responsibility:** Validate HTTP inputs and map Module contracts to response schemas.

**Interface:** start/list/detail/compare evaluation routes and one run-trace route.

### Frontend Control Module

**Responsibility:** Runtime-validate control-center contracts and hide transport/polling details.

**Interface:** `startEvaluation`, `listEvaluations`, `getEvaluation`, `compareEvaluations`, `getRunTrace`.

### Product Pages

**Responsibility:** Present evaluation catalog/detail/comparison and run trace in Chinese-first, accessible UI.

**Interface:** URL state and rendered user actions only; no persistence knowledge.

## Module Interactions

### Evaluation Start and Completion

```text
POST evaluation
  -> SQL transaction inserts AgentEvaluation + OutboxMessage
  -> dispatcher publishes agent.evaluate
  -> RQ task claims evaluation lease
  -> fixed executor runs isolated deterministic evaluator
  -> report validator rejects dishonest/malformed output
  -> terminal immutable snapshot is committed
  -> UI polling observes passed/failed state
```

### Trace and Replay

```text
GET run trace
  -> load persisted rows
  -> sanitize/redact
  -> project ordered timeline
  -> compute replay digest and stored-state match
  -> classify failure from bounded facts
  -> return one trace document
```

### Comparison

```text
GET comparison(left,right)
  -> require two terminal snapshots
  -> check dataset/schema compatibility
  -> compute metrics/gates/case-set delta
  -> classify improved/stable/regressed/incomparable
```

## File Organization

### Backend

- `backend/app/models/agent_evaluation.py`
- `backend/app/modules/agent_control/{contracts,interface,service,executor,trace,comparison,triage,wiring}.py`
- `backend/app/schemas/agent_control_schema.py`
- `backend/app/api/routes_agent_control.py`
- `backend/app/tasks/evaluation_tasks.py`
- `backend/alembic/versions/0009_v5_2_agent_control.py`
- focused tests under `backend/tests/test_v5_2_*.py`

### Frontend

- `frontend/modules/agent-control/{contract,client,presenter}.ts` and tests
- `frontend/components/agent-control/*`
- `frontend/app/evaluations/page.tsx`
- `frontend/app/evaluations/[evaluationId]/page.tsx`
- `frontend/app/runs/[runId]/trace/page.tsx`
- `frontend/e2e/v5-2-agent-control.spec.ts`

### Documentation and Release

- `docs/v5_2_agent_control_center/*`
- README/version/release/CI surfaces and append-only delivery logs

## Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module shape | One deep AgentControl Interface | Keeps SQL, replay, comparison, execution, and triage local. |
| Evaluation execution | Existing fixed evaluator via argument-list subprocess | Reuses reviewed evaluator without importing scripts into application packages or enabling arbitrary commands. |
| Executor variation | Production subprocess + recording test Adapter | Two real Adapters justify the Seam and provide deterministic tests. |
| Dispatch | Existing transactional outbox and RQ worker | Preserves durable publish/retry behavior already verified in V5.1. |
| Evaluation data | Immutable terminal snapshot in SQLite | Enables history and comparison without depending on temporary files. |
| Replay meaning | Projection replay only | Avoids replaying models, tools, or external effects while proving persisted-history integrity. |
| Privacy | Allowlist public payload keys; redact every private payload | Makes leakage prevention structural rather than copy-based. |
| Comparison | Fixed metric registry and compatibility gate | Prevents arbitrary JSON arithmetic and misleading cross-dataset verdicts. |
| UI placement | Links from Runs and Developer Mode; no fifth primary route | Preserves the clean four-route product shell. |
| Provider boundary | Deterministic mode only, zero external calls required | Honors the user's explicit exclusion of real-model configuration. |

## Delegated Approval Record

- Every F requirement has an architectural home.
- The AgentControl external Interface stays small; executor variation is behind an internal Seam.
- SQL, worker, HTTP, and frontend dependencies are acyclic.
- Adversarial review rejected direct script parameters, raw JSON passthrough, prompt exposure, synchronous HTTP
  evaluation, historical side-effect replay, and a fifth primary navigation route.

Status: **approved for task breakdown**.
