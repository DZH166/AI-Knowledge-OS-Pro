# V5.3 Adaptive Policy and Retrieval Lab Plan

## Architecture Overview

Add one deep `agent_policy` Module behind a small command/query/simulation Interface. Routes, EvidenceAgent, the
evaluation worker, and tests learn policy results, not SQL lifecycle mechanics. A policy config is bounded data and
is interpreted by a pure internal decision implementation shared by runtime and counterfactual simulation.

```text
Policy Lab / EvidenceAgent / AgentControl
                 │
                 ▼
         AgentPolicy Interface
                 │
     ┌───────────┼────────────┐
     ▼           ▼            ▼
 SQL lifecycle  Pure policy  Counterfactual
 + audit        decisions    projection
     │           │            │
     └──── policy snapshot ────┘
                 │
                 ▼
       AgentRunner / evaluator
```

## Core Data Structures and Interfaces

### Policy Configuration

`RetrievalPolicyConfig` is a frozen strict schema with:

- `schema_version = 1`;
- `factual_top_k`, `comparative_top_k`, `temporal_top_k`;
- `minimum_score_millis`;
- `max_hits_per_source`;
- `neighbor_before`, `neighbor_after`.

All values have small explicit ranges. A pure `RetrievalDecisionPolicy` chooses the top-k for a requirement kind,
filters ordered hits by score and source diversity, and returns the neighbor window plus policy audit facts.

### Commands

- `CreatePolicy(request_id, label, base_policy_id, config)` — insert one new immutable draft version.
- `ActivatePolicy(request_id, policy_id, expected_active_policy_id, evaluation_id)` — evaluation-gated CAS activation.
- `RollbackPolicy(request_id, policy_id, expected_active_policy_id)` — reactivate a previously active version.

### Queries

- `ListPolicies(status, limit)` — bounded summaries.
- `GetPolicy(policy_id)` / `GetActivePolicy()` — full safe config and lifecycle facts.
- `ComparePolicies(left_id, right_id)` — field-level diff.
- `SimulatePolicy(run_id, policy_id)` — pure counterfactual projection over persisted facts.

### Persisted Records

- `AgentPolicyVersion` stores policy family/version, immutable canonical config/fingerprint, lifecycle state,
  lineage, and timestamps.
- `AgentPolicyCommand` stores request id, payload hash, command type, and receipt for idempotency.
- `AgentPolicyActivation` stores every activation/rollback, previous/new policy ids, evidence evaluation id, action,
  and timestamp.
- `AgentRun` gains nullable legacy-safe policy identity/fingerprint/snapshot fields; every new Run writes all fields.
- `AgentEvaluation` gains a policy-version reference while retaining the immutable policy fingerprint.

## Module Design

### `agent_policy` Module

**Responsibility:** Own policy configuration validation, immutable versions, active lifecycle, audit, comparison,
counterfactual simulation, and pure retrieval decisions.

**Public interface:** `submit(command)`, `inspect(query)`, `simulate(query)`.

**Dependencies:** SQLAlchemy session factory. It has no model, vector, provider, subprocess, or HTTP dependency.

### EvidenceAgent Integration

**Responsibility:** Pin the active policy snapshot when opening a Run and preserve the parent snapshot on continuation.

**Interface change:** Internal constructor receives an `ActivePolicyPort`; external `EvidenceAgent` Interface and
existing HTTP body remain backward compatible.

### AgentRunner Integration

**Responsibility:** Read only the Run's pinned snapshot, derive adaptive retrieval decisions, record exact tool
arguments and public policy facts, then apply score/source/window rules outside provider configuration.

**Interface change:** No new external method. Internal pure policy implementation replaces hard-coded top-k/window.

### AgentControl Evaluation Integration

**Responsibility:** Resolve an optional safe policy id at evaluation submission, persist its exact fingerprint/config,
and give the fixed executor that snapshot. The executor writes one fixed temporary policy file and invokes only the
reviewed evaluator with an internally constructed argument list.

### Frontend Policy Module

**Responsibility:** Runtime-validate policy catalog/detail/diff/simulation/receipt contracts and hide transport logic.

**Interface:** `listPolicies`, `getActivePolicy`, `getPolicy`, `createPolicy`, `comparePolicies`, `simulatePolicy`,
`activatePolicy`, `rollbackPolicy`, and candidate-policy evaluation launch.

## Module Interactions

### Draft to Activation

```text
create draft -> immutable policy row
             -> simulate against selected Run
             -> start fixed evaluation(policy_id)
             -> worker executes exact snapshot
             -> passed evaluation stores matching fingerprint
             -> activate(expected current id, evaluation id)
             -> one SQL transaction retires current + activates candidate + writes audit
```

### Run Pinning and Retrieval

```text
open Run -> read active policy before Run insert
         -> persist policy id/version/fingerprint/config on Run
retrieve -> load pinned config
         -> choose top-k from requirement kind
         -> search outside SQL transaction
         -> filter score + source diversity deterministically
         -> open evidence + configured neighbor window
         -> journal policy id/version/reason and exact bounded arguments
```

### Counterfactual Simulation

```text
simulate(run,candidate)
  -> load Run snapshot + requirement kinds + allowlisted completed tool summaries
  -> recompute top-k/window decisions with candidate config
  -> compare recorded and candidate decisions
  -> return deltas + stable digest + explicit no-new-model/evidence boundary
```

## File Organization

### Backend

- `backend/app/models/agent_policy.py`
- `backend/app/modules/agent_policy/{contracts,interface,config,decision,comparison,simulation,service,wiring}.py`
- `backend/app/schemas/agent_policy_schema.py`
- `backend/app/api/routes_agent_policy.py`
- `backend/alembic/versions/0010_v5_3_agent_policy.py`
- modifications to Agent Run/evaluation models, EvidenceAgent service/controller, AgentControl executor/service, fixed
  evaluator, API/router, trace, and model registry
- focused `backend/tests/test_v5_3_*.py` plus adjacent regression updates

### Frontend

- `frontend/modules/agent-policy/{contract,client,presenter}.ts` and tests
- `frontend/components/agent-policy/*`
- `frontend/app/policies/page.tsx` and `frontend/app/policies/[policyId]/page.tsx`
- links from Evaluation Studio, Run Trace, and Developer Mode
- `frontend/e2e/v5-3-agent-policy.spec.ts`

### Documentation

- `docs/v5_3_adaptive_policy_retrieval/*`, README/version/release surfaces, append-only logs

## Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module shape | One deep AgentPolicy Interface | Keeps lifecycle, config, decisions, simulation, and audit local. |
| Policy language | Strict bounded JSON data | Prevents arbitrary execution and keeps fingerprints portable. |
| Version content | Immutable row, mutable lifecycle plus append-only activation audit | Preserves exact reproducibility while supporting rollback. |
| Active lookup | Injected short-session port | Pins before Run creation and never spans external work. |
| Runtime behavior | Read pinned Run snapshot only | New activation cannot change or corrupt an in-flight Run. |
| Adaptation | Requirement-kind top-k + finite score/source/window controls | Delivers real bounded behavior without pretending to have a configured reranker. |
| Simulation | Projection over persisted allowlisted facts | Useful policy evidence without re-executing stochastic or external work. |
| Activation gate | Matching passed fixed evaluation, except audited rollback | Turns evaluation into a release control and preserves emergency reversibility. |
| Evaluator input | Internal temporary policy file only | Supports candidate evaluation without exposing arbitrary path/command input. |
| UI placement | Developer Mode, no fifth primary item | Preserves the four-entry product shell. |

## Delegated Approval Record

Self-review mapped F1–F10 to Modules and interactions, kept external Interfaces small, separated SQL sessions from
external work, and rejected executable policies, global mutable runtime reads, untested activation, simulation that
calls tools/models, arbitrary evaluator paths, and a new primary navigation item.

Status: **approved for task breakdown**.
