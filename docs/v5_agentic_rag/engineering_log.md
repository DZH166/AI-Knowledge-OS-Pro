# 溯知 V5 Engineering Log

## Baseline

- Branch: `codex/v5-evidence-agent`
- Base commit: `d03b3d5170226b6290b41880a74e2dab171a313f`
- Base release line: V4.9 Hallmark UI on top of V4.8 runtime work
- Isolation: implementation runs in the clean Codex worktree; the user's original worktree deletion of `frontend/` is not modified.
- Planning artifacts: `spec.md`, `plan.md`, `task.md`, and `checklist.md` were self-reviewed under the user's explicit delegated approval.

### Known baseline risks

1. Documents and media/code use different evidence identities.
2. Dense search filters only by knowledge space.
3. Keyword search truncates recent rows before scoring.
4. OCR/STT reprocessing can leave old chunks and vector points active.
5. Qdrant upsert can precede durable SQL point tracking.
6. RQ heartbeat timeout can be shorter than a Provider call.
7. The current evaluator reads seeded QA logs rather than running the pipeline.
8. Frontend navigation and pages dilute the evidence workflow.
9. Frontend API payloads are trusted by TypeScript casts without runtime validation.

## Command Evidence

Command outputs are appended here as each task is executed. A command is not marked passing until its actual exit status has been observed.

### T1 — V4.9 baseline

- Environment: Python `3.13.9`, Node `24.19.0`, npm `11.17.0`. CI targets Python 3.12 and Node 20, so final acceptance must run both the local environment and CI-compatible runtimes where available.
- `python -m pytest backend/tests/test_v4_0_hybrid_retrieval.py backend/tests/test_reindex.py backend/tests/test_index_compatibility.py backend/tests/test_v3_audio_transcription.py backend/tests/test_v3_5_video_transcription.py -q`
  - Result: `10 passed, 3 warnings in 10.06s`.
  - Warning: existing production `VectorStore()` constructors attempted Qdrant compatibility checks during tests. V5 wiring must remove hidden external construction from module tests.
- `npm run typecheck`
  - Result: passed with exit code 0.
- Baseline dirty state: only `docs/v5_agentic_rag/` is untracked in the isolated V5 worktree.

### T2–T3 — SQLite integrity and concurrency

- RED: `test_v5_migrations.py` failed during collection because the planned `create_database_engine` interface did not exist.
- Resolution: introduced one engine factory used by both production and tests. Every SQLite connection now enables foreign keys, a 5-second busy timeout and WAL for file databases.
- GREEN: `python -m pytest backend/tests/test_v5_migrations.py -q` → `1 passed in 0.07s`.
- Rejected shortcut: setting PRAGMAs only in test fixtures. That would leave RQ, SSE and production sessions with different integrity behavior.

### T4–T5 — Canonical evidence migration contract and models

- RED: the populated V4.9 fixture reaches revision `0006_v3_6_unified_media_tasks` but cannot satisfy the V5 assertions because the operation, vector manifest and outbox tables do not exist yet.
- The fixture deliberately includes a document uploaded after migration 0004 and two simultaneously active media revisions/indexes. This reproduces both identity drift and stale evidence leakage instead of testing an empty database.
- Added lifecycle fields and partial uniqueness declarations to Source, SourceRevision and IndexRevision; added immutable chunk hashes and retirement timestamps.
- Added `IndexOperation`, `VectorPointManifest` and `OutboxMessage` models. SQL mapper configuration and `python -m compileall backend/app` pass.
- Remaining RED is intentional until migration 0007 performs the data repair. No migration step contacts Qdrant; legacy payload reconciliation remains an explicit post-upgrade operation.

## Engineering Decisions and Resolutions

Each non-trivial failure will be recorded with: symptom, root cause, rejected shortcuts, chosen fix, verification, and remaining limitation.

## V5 Implementation Failures and Resolutions

### Canonical retrieval initially preserved two stale paths

- Symptom: an exact keyword in the oldest row could disappear, and dense candidates could spend top-k slots on a retired revision before filtering.
- Root cause: the legacy keyword implementation truncated by creation time before scoring; dense search filtered only by knowledge space and applied lifecycle validity too late.
- Rejected shortcut: increasing the candidate limit. That only makes the age bug less frequent and still permits stale evidence to distort ranking.
- Resolution: sparse scoring now evaluates the full active/pinned scope, and dense filters include source/revision/index lifecycle identity before top-k. RRF, thresholding and context packing operate on the same admissible set.
- Verification: oldest exact-hit, shared threshold, active revision and pinned revision tests in `test_v5_active_retrieval.py`; evaluator fusion Recall@10 and active precision are both `1.0`.

### Vector writes needed a durable pre-write identity

- Symptom: a crash after Qdrant upsert but before a SQL commit could leave externally visible points with no database owner.
- Root cause: the previous path treated vector upsert as the start of persistence instead of an external side effect of a committed manifest.
- Rejected shortcut: best-effort delete in an exception handler. A second network failure would recreate the same untracked state.
- Resolution: stage deterministic point ids and payload digests in SQL first, then upsert, validate and atomically activate. Cancellation/failure records compensation state; the reconciler finishes incomplete cleanup and reports orphan/missing/mismatched points.
- Verification: crash-window, cancel-after-upsert, retry, failed-delete recovery and idempotent reconciler suites.
- Remaining limitation: legacy online Qdrant payloads still require an explicit post-upgrade dry-run/apply or reindex; Alembic stays SQL-only.

### Real mode silently risked looking more capable than it was

- Symptom: production wiring without an LLM could fall back to the deterministic model, making a real run look successful.
- Root cause: the recording adapter was a useful test default but the provider boundary was not enforced at the HTTP and Runner seams.
- Rejected shortcut: exposing a subtle UI label while still returning a generated result. That does not preserve a truthful production boundary.
- Resolution: real submission checks provider availability and returns a clear configuration error; a direct real-mode Runner invocation also fails the run and publishes no Artifact.
- Verification: API 503 and direct-runtime failure tests, plus adjacent API/security/recovery regression.

### Production Agent search was not using the full hybrid path

- Symptom: the upgraded Agent runtime called the canonical SQL search directly even though legacy RAG had dense+sparse fusion.
- Root cause: durable Agent work focused first on the EvidenceIndex seam and did not wire the embedding/hybrid adapter back into production construction.
- Rejected shortcut: fabricate a deterministic embedding in production. That would hide a missing Provider and mix demo/real semantics.
- Resolution: `HybridAgentSearch` computes embeddings outside the SQL session, invokes `HybridRetriever` with pinned revisions and maps results back to immutable EvidenceRefs. When no embedding is configured, it takes a labeled sparse-only path.
- Verification: focused hybrid tests assert the embed call, hybrid invocation, pinned revision filter and immutable active evidence projection (`6 passed`).

### Usage counters could turn unknown cost into a fake zero

- Symptom: model records and UI totals could display `0` even when the Provider did not report price or token usage.
- Root cause: numeric persistence fields used zero as a convenient sentinel without a parallel measurement-quality projection.
- Rejected shortcut: estimate every Provider with one universal price. That would give a precise-looking but false budget.
- Resolution: run projections and events distinguish `reported`, `estimated`, `unknown` and `partial_unknown`; missing context tokens receive a labeled conservative estimate, retries are preserved, and unknown price is not presented as measured zero.
- Verification: context hard-stop, retry propagation, reported/estimated/unknown cost tests and frontend runtime-contract tests. The deterministic evaluator reports 82 estimated calls and 0 Provider-reported cost calls.
- Remaining limitation: an exact currency ceiling cannot be guaranteed while a Provider price remains unknown.

### Claim-level provenance needed a conservative last gate

- Symptom: a structured model could cite an existing evidence id while introducing an unseen number, proper name or title in the claim text.
- Root cause: referential integrity alone proves where a citation points, not that its excerpt supports every assertion.
- Rejected shortcut: accept any non-empty citation list as grounded.
- Resolution: synthesis verifies immutable reference identity and applies a conservative literal-claim gate; suspicious new values cause deterministic fallback. Contradictory quantitative evidence is marked contested rather than flattened.
- Verification: unseen-number/name/title fallback, weak-partial-hit exclusion, conflict and hard-provenance tests.
- Remaining limitation: this is not a full semantic entailment model and is described as such in acceptance boundaries.

### Clarification existed in the state vocabulary but not the execution loop

- Symptom: `awaiting_input` and `provide_input` were present in contracts, but the Runner never created a durable clarification gate and could not resume a targeted requirement.
- Root cause: the first vertical slice implemented insufficiency and exact approval before connecting model sufficiency decisions to a checkpointed clarification interaction.
- Rejected shortcut: append user text only to an event. That would not update the retrieval requirement or guarantee a single-use checkpoint.
- Resolution: structured sufficiency may request one bounded question and target ordinal; Runner persists a Gate, emits `run.awaiting_input` and `interaction.required`, validates 1–500 characters, updates the same requirement, and resumes the same run at retrieve. Duplicate requests replay one receipt.
- Verification: `python -m pytest backend/tests/test_v5_agent_human_loop.py backend/tests/test_v5_agent_runtime.py backend/tests/test_v5_agent_model_runner.py backend/tests/test_v5_agent_models.py -q --basetemp=.pytest_tmp_agent_runtime_p1` → `63 passed in 4.30s`.

### Public events and frontend projection disagreed on evidence and Artifact shape

- Symptom: backend `evidence.added` initially exposed an id list while the frontend expected one full immutable evidence item; the backend used `artifact.finalized` while the client completion projection listened for `artifact.published`.
- Root cause: persistence events and public projection events evolved independently.
- Rejected shortcut: make the frontend issue extra reads for every id and infer publication from a private lifecycle event.
- Resolution: each public evidence event now carries one evidence id, source title, excerpt, relation and complete reference. Success and gap outcomes publish `artifact.published`; success retains `artifact.finalized` for internal lifecycle meaning.
- Verification: public-event runtime tests cover success and insufficient outcomes; frontend Zod schemas reject malformed evidence.

### Source links initially treated every Artifact citation as media

- Symptom: Artifact evidence links sent documents and code to `/media/sources/...`.
- Root cause: the first UI vertical slice reused the only existing unified source-detail route and did not encode source-type/locator routing as a separate module.
- Rejected shortcut: keep a universal media fallback because it produces a clickable link. A clickable wrong locator is worse than an explicit Library fallback.
- Resolution: a pure source-locator maps document pages/chunks, media timestamps and code ranges to their real viewers; unknown kinds fall back to Library. Source catalog cards use their actual source type. Artifact lists also accept a source filter through claim→evidence provenance.
- Verification: source-locator `5 passed`, catalog round-trip/backend filter tests and production Artifact Playwright locator assertion.

### Downgrade passed structurally but initially lost legacy semantics

- Symptom: `0007` could drop V5 tables and columns successfully while failing to restore legacy active flags/relationships that the upgrade had normalized.
- Root cause: the first downgrade implemented schema reversal but had no durable record of pre-upgrade V4.9 values or migration-created backfill identity.
- Rejected shortcut: reconstruct legacy state heuristically from current active rows. Post-upgrade edits make that ambiguous and risk deleting user-created data.
- Resolution: `0007` writes and finalizes a semantic downgrade journal before normalization, validates it before destructive DDL, restores V4.9-expressible values, deletes only pristine migration-created backfill, and preserves adopted/modified chains where V4.9 can represent them. Missing or corrupt journal data fails closed.
- Verification: final migration/CLI suite `9 passed in 23.14s`; direct `--roundtrip` is `ok=true` for `0008→0006→0008`, restores 6 entries, identifies 4 created entries, removes all V5 tables at 0006 and preserves the isolated fixture semantic digest `22524ab073156d44dcda9de762bebe8bb78206fb6873965099756b0bf4f484da`.
- Remaining limitation: V5-only state has no V4.9 representation and is explicitly dropped; Qdrant is not contacted by a SQL migration.

### Evaluation numbers required provenance labels, not only higher scores

- Symptom: a strong deterministic result could be misread as a historical V4.9 rerun or real-LLM benchmark.
- Root cause: baseline, Provider and corpus labels were easy to omit while summarizing metrics.
- Rejected shortcut: present the proxy lift as a general production quality improvement.
- Resolution: the report records corpus digest, module pipeline, deterministic hashing/recording providers, external call count, production reranker state, cost measurement quality and the `proxy_not_historical_runtime` label. The acceptance gate rejects missing or changed provenance.
- Verification: 60 unique cases, all hard gates true, `external_provider_calls=0`, report/gate focused tests `2 passed`, multi-hop Agent `100%` versus labeled proxy `41.67%`.

### Optional rerank needed a real adapter without changing honest defaults

- Symptom: the architecture exposed a rerank seam and a recording evaluation arm, but production could only be disabled; that proved fusion behavior, not a callable real-provider boundary.
- Root cause: the first delivery prioritized deterministic retrieval correctness and left the external HTTP contract unimplemented.
- Rejected shortcut: label the recording scorer as production reranking or enable an endpoint implicitly.
- Resolution: added a configurable HTTP rerank adapter with bounded timeout, validated results and explicit failure/disabled behavior. Default runtime and the fixed deterministic report remain unconfigured.
- Verification: provider-boundary/focused retrieval tests and the final `364 passed` backend suite.
- Remaining limitation: no production endpoint/credentials were supplied, so there is no real-provider quality or latency claim.

### SSE recovery originally handled replay but not cursor invalidation

- Symptom: a legal cursor replayed missing events, but no-cursor, pruned/stale or future cursors could not force a safe projection reset; an idle connection also had no transport heartbeat.
- Root cause: the first follow loop treated every numeric cursor as a valid journal position and coupled every outgoing frame to a persisted event.
- Rejected shortcut: write heartbeat rows into the event journal. That would consume cursor ids and create false domain activity.
- Resolution: no-cursor, stale and future positions emit reset snapshots; legal positions emit only later public events. Heartbeat is a same-cursor transport frame, is never journaled and is ignored by the frontend event projection. Production bootstrap reconstructs Ledger and the active interaction after refresh.
- Verification: backend runtime/API SSE `20 passed`; frontend runtime/SSE/controller `3 files / 12 tests passed`; final frontend unit `13 files / 53 tests passed`.

### Recording ids were deterministic but unsafe under concurrency

- Symptom: deterministic recording runs used a shared incrementing id source, which could collide or become order-dependent under concurrent creation.
- Root cause: test convenience leaked into a runtime adapter that can receive concurrent UI submissions.
- Rejected shortcut: protect the counter with a process-local lock. That still makes ids dependent on process lifetime and ordering.
- Resolution: recording run ids now use UUIDs while command receipts remain idempotent by request id.
- Verification: concurrent recording regression plus the final frontend `53 tests` and backend `364 passed` suites.

### Live Qdrant failure exercised the truthful fallback

- Symptom: strict live E2E observed a real Qdrant `502` response.
- Root cause: the external vector service was unavailable; this was an infrastructure response rather than an application fixture.
- Rejected shortcut: mark the service healthy or fabricate dense results so the browser flow stays green.
- Resolution: production Agent search uses the canonical sparse path when dense infrastructure is unavailable, retaining immutable revision identity and a resolvable citation.
- Verification: strict live E2E `27/27 passed`; the degraded run still returned a canonical citation and the durable demo Run completed through the live Worker.

### Retrieval candidates needed an explicit support decision

- Symptom: a semantically near-top retrieval candidate could be treated as covered merely because it was returned, while an early lexical gate could also discard a useful synonym before structured assessment.
- Root cause: candidate discovery and claim support shared one relation, so retrieval relevance was confused with entailment.
- Rejected shortcut: restore the lexical pre-filter or cite every near-top row. Both make metrics look cleaner while breaking evidence semantics.
- Resolution: retrieval persists candidates; quick mode promotes only direct fixed-corpus support, and Agent mode requires a validated requirement-level `evidence_selections` decision. Fake, missing and cross-requirement evidence ids fail closed. Synthesis and ClaimEvidence consume only promoted `supports`/`contradicts` rows.
- Verification: focused adversarial tests, `-k v5_agent` regression and the 60/60 evaluator with the Agent reranker disabled.

### The first strict live Worker run found two transaction-only defects

- Symptom: the first live POST failed because `agent_events` was inserted before its new Run; after that fix, the next run stalled in routing with duplicate event sequence 3 and thousands of immediate retries.
- Root cause: the ORM models expose bare foreign keys without relationships, and production SessionLocal disables autoflush. The journal read only persisted max sequence and the demo composition explicitly used zero retry delay.
- Rejected shortcut: disable SQLite foreign keys, increase the browser timeout or skip the live Worker assertion.
- Resolution: explicitly flush the new Run before its first event; allocate event sequence from both persisted and same-session pending events; use normal bounded retry delay; keep the durable live-worker scenario in strict E2E.
- Verification: FK=ON file-SQLite RED/GREEN, autoflush-disabled monotonic event test, 14 live events numbered 1..14, four outbox messages published once, and final strict E2E `27/27`.

### Durable recovery and outbox ownership had to survive process failure

- Symptom: a process death after preparing a model/search call could leave a Run and invocation permanently `running`; concurrent Runner or dispatcher claims could duplicate effects; malformed messages could kill a batch.
- Root cause: checkpoints were written but not read, Runner locking was a plain SELECT, outbox claim was SELECT→UPDATE, leases were not renewed and envelope parsing occurred outside the per-message failure boundary.
- Rejected shortcut: replay unknown model calls, rely on unique constraints as locks, or describe at-least-once delivery as exactly-once.
- Resolution: `AgentInvocationRecovery` validates checkpoint checksum/state/cursor, requeues interrupted read-only search under a new epoch and fails closed for unknown model results. Runner and outbox use atomic lease/CAS claims; slow publish renews ownership; poison messages receive bounded exponential retry, dead-letter and an explicit audited retry path.
- Verification: recovery focused `10 passed`, outbox/worker/runtime `33 passed`, V5 Agent `97 passed`, and final backend `364 passed`.

### Release packaging exposed the difference between working-tree and tracked-source evidence

- Symptom: the V5 archive check failed even though build/tests passed because newly created V5 files were missing from the package.
- Root cause: the release builder intentionally packages `git ls-files`; the reviewed V5 additions are still uncommitted and therefore absent from that set.
- Rejected shortcut: weaken the release checker or copy arbitrary untracked files into the archive. That would undermine the reproducible-source boundary.
- Resolution: keep the checker strict, stage the complete reviewed V5 source set so it participates in `git ls-files`, then rebuild and rerun the unchanged checker.
- Verification: an earlier staged-source snapshot contained 580 files and `check_release.py` reported `forbidden=0`, `missing=0`. Later review fixes changed the source set, so that ignored archive is now stale; it must be rebuilt and rechecked before final handoff and is not presented as final or remotely published release evidence.

## Review Status

The initial Standards and Spec review produced findings for real-mode fallback, production hybrid search, clarification persistence, public Ledger/Artifact events, source locators, Source→Artifact provenance, downgrade semantics, SSE recovery and recording concurrency. Those fixes have focused coverage and are included in the final backend/frontend regressions.

The latest independent Standards/Spec pass reported no P0 and five P1 finding groups:

1. media replacement retired the old active evidence before the replacement vector/index path had safely completed;
2. a next-slice wake-up could be consumed while a Run lease was still owned, and concurrent `OpenRun` calls did not share the sequential idempotency behavior;
3. concurrent EvidenceIndex staging could race on `max(revision_number) + 1` and leak a raw uniqueness failure;
4. Artifact→Source locators dropped revision/hash, so a historical Artifact could open the current viewer revision instead of its pinned retired evidence;
5. production public events and frontend projection disagreed on plan/evidence relation updates, leaving the visible plan absent or candidate relations stale.

The first three groups have code fixes and focused regressions. The immutable-locator and production-projection groups are still being completed, after which both review axes and the full regressions must run again. This document therefore does **not** claim a final zero-P1 disposition.

One planned capability remains an explicit partial item rather than being silently claimed:

1. `open_evidence`/`read_neighbors` are registered read-only tools, but Runner execution and a first-class EvidenceIndex neighbor query are not complete.

The last full regression baseline is backend `364 passed`, frontend `53 tests`, a 34-route build and strict live E2E `27/27`. Those numbers predate the remaining review fixes and are superseded by the final regression entry below. The earlier 580-file archive is retained as historical context only; the current 581-file archive and checker result are recorded in the final entry below.

### Final regression and local release-candidate closure

- Provider-mode isolation now has an explicit compatibility seam: direct `AgentRunner(agent_model=...)` injection serves recording/demo test runs, while production wiring keeps `real`, `demo` and `recording` mapped explicitly. Runs without a configured real model still fail closed; offline modes retain deterministic policy behavior.
- Active-time accounting uses stable millisecond flooring so short recording calls cannot cross a budget boundary because of rounding noise; measured wall time remains authoritative over adapter-reported latency.
- Verification: V5 Agent focused runtime/model/recovery/API suite `79 passed in 20.90s`; full backend `439 passed, 1 skipped in 141.87s`; frontend `17 files / 73 tests`, lint, typecheck and Next `15.5.23` build with 34 routes all passed.
- Migration round-trip returned `ok=true` for `0008→0006→0008`; acceptance gate returned `passed` with `failures=[]`.
- Release rebuild/check passed for `AI-Knowledge-OS-Pro-V5.0-20260816.zip`: 590 tracked files, forbidden 0, missing 0, manifest verified, freshness current; the SHA-256 is retained in the generated `.sha256` sidecar.

### Remaining owner-controlled boundary

The local release candidate is verified. Public GitHub visibility, default-branch selection, merge/push and GitHub Release publication remain external repository-owner actions. Registered `open_evidence`/`read_neighbors` execution, full keyboard decision E2E and real-provider quality benchmarking remain explicitly partial scope items.

### V5.1 bounded evidence-tool and approval closure

- `GetEvidenceChunk` and `GetEvidenceNeighbors` expose immutable pinned references. Neighbor windows reject negative values and values above three, and SQL constrains every row to the center revision.
- AgentRunner accepts an optional `EvidenceQueryPort`; production injects a short-session SQL adapter. Existing direct Runner tests remain compatible when no port is supplied.
- For each requirement, one retrieved center is opened and expanded before assessment. Search, open and neighbors each reserve their own tool budget and pass through version/epoch fences, checkpoints, outbox wakeups and read-only crash recovery.
- Neighbor evidence is persisted as `contextual`; assessment may promote selected candidate/contextual rows to `supports`, while unselected rows become `excluded` with `model_not_selected` and a public relation-change event.
- Publication ToolSpec v2 includes an Artifact content digest. `modify` accepts only a non-empty title, marks the old proposal superseded, creates a new gate/digest and rejects approval with the old digest.
- The frontend translates relation codes into Chinese, shows exclusion reasons and explains Proposal Digest. Recording reload now starts from the bootstrap receipt and replays its journal so the visible projection is not empty.
- Verification: Ruff passed; focused backend `93 passed`; final full backend `444 passed, 1 skipped in 150.71s`; frontend `17 files / 76 tests`, lint, typecheck and 34-route build passed; targeted Playwright `2/2` passed.
- Honest browser boundary: the current strict all-suite run completed `21/31`; missing `NEXT_PUBLIC_API_BASE_URL` caused backend-dependent failures, so it is not reported as a passing strict gate.
- Local release closure: the settled V5.1 commit was packaged as `AI-Knowledge-OS-Pro-V5.0-20260821.zip`; the checker reported 590 tracked files, forbidden 0, missing 0, manifest verified and freshness current.
