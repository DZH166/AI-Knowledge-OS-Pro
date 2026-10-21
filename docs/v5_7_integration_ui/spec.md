# 溯知 V5.7 Integration Workbench — Spec

## Goal

Turn the WorkBuddy V5.4A–V5.7 backend into one truthful, typed, end-to-end product stage. The integration must
repair every independent review finding before exposing the optimizer in the frontend. Real model configuration,
automatic policy activation, image generation, and cloud deployment remain out of scope.

## Backend Corrections

1. Optimizer evaluations require a non-null report policy fingerprint exactly equal to the Trial snapshot.
2. Recovering an expired Trial atomically requeues its non-cancelled Outbox row, including `published` rows.
3. `max_candidates` is a cumulative Study budget. Later rounds never repeat an observed/base fingerprint and
   idempotency replays the original receipt for every historical next-round request.
4. Validated evaluation provenance retains the real `agent_p95` latency; persisted metrics, scoring, Pareto,
   recommendation, overview, and export use it instead of a zero default.
5. Category analysis persists the exact 60 public case outcomes. It never fabricates case identity from aggregates.
6. Study events cover every specified state change and use a correct `(created_at, id)` cursor.
7. Templates expose complete immutable search-space/weight facts and accept a strict nested `overrides` object.
8. Comparison Markdown includes pairwise metric deltas, Hard Gate changes, new/resolved failures, and exact
   category win/tie/loss facts.
9. Run sharing moves behind a dedicated typed module interface; routes never access persistence internals.
10. The optimizer public interface returns typed receipts/views instead of unbounded `dict[str, object]` results.
11. Ruff, compile, migration, documentation, provider-zero, and existing regression gates pass.

## Frontend Product

### Routes

- `/policies/optimizer`: template creation and Study catalog.
- `/policies/optimizer/[studyId]`: overview, rounds, Trials, actions, events, recommendations, comparison export.
- Existing Run Trace gains create/revoke read-only share-link controls.

No new primary navigation item is added. Optimizer routes belong to the existing Policy Lab developer destination.

### Workflow

1. Load the active Agent Policy and the 3 server templates.
2. Create a Study from a template using strict bounded overrides.
3. Open the Study overview; render only server-declared action availability/reasons.
4. Start, cancel, fail, recover, or create the next round through explicit commands.
5. Inspect Trial metrics, categories, active-policy diff, Pareto membership, recommendation rationale, and draft link.
6. Select exactly 2–3 completed Trials and export deterministic Markdown.
7. Convert only an available recommendation to a draft; never activate it.
8. Create a bounded Run share link, copy its path, and revoke it.

### UX and Safety

- Strict Zod parsing rejects malformed production payloads; no demo fallback.
- Loading, empty, error, retry, pending, terminal, and partial-data states are explicit.
- URL identifies the Study. Controls use semantic buttons/links, labels, visible focus, `aria-live`, keyboard flow,
  and 390px responsive layout.
- Warm monochrome visual system; no gradients, heavy shadows, image dependency, or decorative animation.
- English technical terms are paired with concise Chinese explanations in user-facing copy.

## Acceptance

- Backend review findings: Standards 0; Spec 0 after follow-up review.
- Backend full suite and one populated `0010→head→0010→head` migration round-trip pass.
- Frontend lint/typecheck/unit/build/audit pass with new contract and view tests.
- Strict browser runtime proves template → Study → start → completed overview → comparison → recommendation →
  draft conversion, plus Run share create/read/revoke, keyboard-only and mobile operation.
- Canonical strict runtime passes twice with exact process/container/database cleanup.
- Public version, README, current architecture, resume pitch, logs, release profile and archive agree on V5.7.

Status: **approved under the user's delegated implementation authority**.
