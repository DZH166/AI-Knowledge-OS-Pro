# 溯知 V5 Evidence Agent Acceptance Report

- Date: 2026-08-21
- Branch: `codex/v5-evidence-agent`
- Baseline: `d03b3d5170226b6290b41880a74e2dab171a313f`
- Product version: `V5.0 / 5.0.0`
- Evidence set: this report, `checklist.md`, `evaluation_report.json`, `acceptance_gate.json`, automated test output and the four V5 screenshots

## Outcome

V5 has a working, resume-grade Agentic RAG vertical slice: canonical immutable evidence, revision-safe hybrid retrieval, a durable Evidence Agent loop, claim-level provenance, budgets and cancellation fences, human clarification/approval, a four-zone product UI, deterministic evaluation and migration/reconciliation operations. It is no longer only a single-shot RAG chat.

Acceptance is deliberately reported as **core delivered with explicit partial boundaries**, not as full conformance to every aspirational checklist line:

- Passed with direct evidence: **54 / 76**
- Partial or not yet fully verified: **22 / 76**
- Observed failures presented as passing: **0**

The source of truth for item-level status is [`checklist.md`](checklist.md). A partial item remains unchecked even when most of it is implemented.

## Delivered Product Capabilities

### Canonical EvidenceIndex

- A single Source → SourceRevision → IndexRevision → Chunk identity model now covers document, media and code writers.
- Stage → manifest → vector upsert → validation → atomic activation prevents an incomplete new index from replacing a healthy active revision.
- Deterministic point ids, operation receipts, compensation and a dry-run/apply reconciler make SQL/vector divergence observable and recoverable.
- Active queries reject stale revisions; a run pins immutable revision scope so later re-indexing does not silently change its evidence.
- The old sparse preselection defect is fixed: the oldest exact keyword hit is no longer discarded before scoring.

### Durable Evidence Agent

- `auto`, `force_quick` and `force_agent` modes share one persisted Run/Requirement/ToolCall/ModelCall/Evidence/Gate/Event/Artifact model.
- Simple tasks keep a zero-planner quick path. Multi-source tasks produce explicit requirements and repeated evidence search/assessment steps.
- Structured model ports validate route, plan, sufficiency and synthesis output, allow at most one repair attempt, and retain token/attempt/retry/cost provenance.
- Evidence Ledger events expose a complete immutable reference, source title, excerpt and support/contradiction relation.
- Sufficiency can answer, continue with a bounded query, return a normal gap result, or persist a clarification gate. Valid `provide_input` resumes the same run and checkpoint.
- Step, tool, model-call, input/output/context token, active-time, cost and no-new-evidence budgets stop before the next external effect.
- Epoch/version fences discard Provider or search results that return after cancel, pause or a competing worker wakeup.
- Run slices and outbox delivery use atomic lease/CAS claims. Concurrent workers produce one applied transition; slow delivery renews its lease; poison messages are isolated with bounded backoff, dead-letter and an audited retry path.
- A Worker recovery pass validates persisted checkpoints, resumes interrupted read-only searches with a new epoch, and fails closed for unknown model results instead of silently replaying a potentially billed Provider call.
- Retrieved rows enter the Ledger as candidates first. Only a validated requirement-level evidence selection can promote them to `supports`, so near-top semantic candidates cannot become cited claims merely by being retrieved.
- Success and gap outcomes publish an Artifact event. Every factual claim must resolve to persisted evidence; unsupported novel numbers, names and titles trigger deterministic fallback.
- Real mode without a configured LLM fails explicitly instead of silently substituting recording output.
- Run recording ids are generated as UUIDs without shared mutable counters, and concurrent recording-run creation is covered by regression tests.
- V5.1 executes `search_evidence`, `open_evidence` and bounded `read_neighbors` as separate budgeted ToolCalls. Exact chunk and neighbor queries remain inside the Run's pinned revision, and all three read tools are safe recovery candidates after an interrupted Worker.
- Model-selected evidence becomes `supports`; unselected candidate/contextual rows become `excluded` with a durable reason and method. Neighbor rows stay `contextual` until explicitly selected, so opening context does not silently turn it into claim support.
- A versioned `modify` command can change only a draft Artifact title. It rotates the content-bound proposal digest, supersedes the old proposal and keeps the same Run/Artifact identity before a new exact approval.

### Product Experience

- The primary IA is Workbench, Library, Agent Runs and Artifacts; legacy operations live under Developer Mode.
- Workbench selects the space, source scope, run mode, deliverable and budgets.
- Run Workspace renders plan progress, Evidence Ledger, budget measurement, approval/cancel controls and a persisted clarification form.
- Artifact pages expose producing-run and claim-level provenance. Document/page, media/timestamp and code/line locators route to the corresponding source view.
- Library sources can open a filtered list of derived Artifacts; the backend filter joins Artifact claims to their evidence source.
- Public payloads are parsed through runtime schemas before entering RunController; reconnect de-duplication and explicit reset projection are covered on the client.
- SSE now handles no-cursor, stale and future cursors with reset snapshots, emits cursor-neutral transport heartbeats, filters private events, and rebuilds Ledger/interaction state after a production-page refresh.
- Run Workspace translates evidence relations into Chinese, displays exclusion reasons and explains `Proposal Digest` as the approval fingerprint. Recording navigation now rebuilds plan/Ledger events from its durable journal instead of showing a correct status with an empty projection.

### Evaluation and Operations

- A fixed 60-case corpus covers 12 single-hop, 12 multi-hop, 8 cross-modal, 8 version-conflict, 8 insufficient-evidence, 6 prompt-injection and 6 cancel/recovery cases.
- The evaluator runs EvidenceIndex stage/upsert/activate, `HybridAgentSearch` with pinned-snapshot RRF, Agent submit/advance and claim verification through module interfaces. It records 100 embedding queries and 143 vector searches, and does not read seeded QA logs.
- Alembic `0007` and `0008`, migration preflight/verification and reconciler CLIs are present. The `0007` downgrade journal restores V4.9-expressible semantics and fails closed before destructive DDL when the journal is invalid.
- CI contains backend, frontend, browser, quality/evaluation and release jobs.
- A real optional HTTP rerank adapter is available behind configuration. The default runtime and Agent branch of the fixed report deliberately keep it unconfigured; only the independent rerank arm uses the labeled deterministic feature-overlap adapter.

## Measured Evaluation

The current report is `deterministic_recording`, uses a fixed synthetic corpus, makes **0 external Provider calls**, and is not a real-model quality benchmark.

| Retrieval arm | Recall@10 | MRR | nDCG@10 | Active precision | Locator validity |
|---|---:|---:|---:|---:|---:|
| Dense deterministic hashing | 0.9964 | 1.0000 | 0.9932 | 1.0000 | 1.0000 |
| SQLite sparse | 0.9130 | 0.9710 | 0.9129 | 1.0000 | 1.0000 |
| RRF fusion | 1.0000 | 1.0000 | 0.9976 | 1.0000 | 1.0000 |
| Recording rerank | 0.9964 | 1.0000 | 0.9899 | 1.0000 | 1.0000 |

The Agent experiment uses pinned-snapshot dense/sparse RRF with rerank disabled. The independent rerank arm is explicitly labeled `production_configured=false`; it proves the adapter/evaluation contract, not production reranker quality.

| Experiment | Samples | Task success | Multi-hop samples | Multi-hop success |
|---|---:|---:|---:|---:|
| V4.9-style single-shot proxy | 46 | 78.26% | 12 | 41.67% |
| Retrieval-only | 46 | 100% | 12 | 100% |
| Evidence Agent | 60 | 100% | 12 | 100% |

- Multi-hop lift versus the labeled proxy: **+58.33 percentage points**.
- Citation completeness: **100%**; immutable evidence identity: **100%**.
- Unauthorized action rate: **0%**; recovery scenarios: **6 / 6**.
- Quick latency: p50 **63.71 ms**, p95 **86.82 ms**. Agent latency: p50 **139.49 ms**, p95 **256.93 ms**.
- Model accounting: **82 calls / 82 attempts**, 8,023 input/context tokens, 4,650 output tokens. Cost is labeled **estimated**, not Provider-reported; 82 estimated-cost calls, 0 reported-cost calls, 0 unknown-cost calls.
- Machine acceptance gate: `passed`; all declared checks true; `failures=[]`.

## Command Evidence

### Backend and migrations

| Command | Observed result | Evidence status |
|---|---|---|
| `python -m pytest backend/tests -q --basetemp=.pytest_tmp_backend_v51_final` | `444 passed, 1 skipped in 150.71s` | Final V5.1 full backend regression covering bounded evidence reads, excluded relations, modify approval and the three-tool recovery matrix. |
| V5.1 EvidenceIndex/Agent/runtime/model/human-loop/API/recovery focused suite | `93 passed in 38.53s` | Tool ordering, immutable neighbor scope, exact approval rotation, cancellation fences and recovery evidence. |
| `python -m pytest backend/tests/test_v5_agent_human_loop.py backend/tests/test_v5_agent_runtime.py backend/tests/test_v5_agent_model_runner.py backend/tests/test_v5_agent_models.py -q --basetemp=.pytest_tmp_agent_runtime_p1` | `63 passed in 4.30s` | Post-fix clarification, Ledger event, published Artifact, budget and runtime evidence. |
| `python -m pytest backend/tests/test_v5_agent_api.py backend/tests/test_v5_agent_security.py backend/tests/test_v5_agent_worker_recovery.py -q --basetemp=.pytest_tmp_agent_runtime_p1_adjacent` | `10 passed in 7.93s` | Post-fix adjacent API/security/recovery evidence. |
| Agent hybrid-search focused suite | `6 passed` | Production Agent wiring invokes hybrid retrieval and preserves pinned revision scope; sparse-only fallback is explicit when embeddings are unavailable. |
| `python -m pytest backend/tests/test_v5_migrations.py backend/tests/test_v5_migration_clis.py -q --tb=short` | `9 passed, 27 warnings in 21.73s` | Post-fix downgrade journal, fail-closed validation and CLI evidence. |
| Post-`alembic.ini` migration warning regression | `5 passed`, 0 warnings | `path_separator=os` removed the 27 configuration warnings without changing migration behavior. |
| `python scripts/verify_v5_migration.py --roundtrip` | exit `0`, `ok=true`; `0008→0006→0008`; first/second upgrade equal | Latest isolated fixture semantic digest before/after is `22524ab073156d44dcda9de762bebe8bb78206fb6873965099756b0bf4f484da`; restore entries 6, created entries 4, V5 tables absent at 0006. |
| `python -m alembic heads` | `0008_v5_agent_runtime (head)` | Passed; one head. |
| `python -m alembic check` | non-zero historical metadata operations | Not presented as passing; see boundaries. |
| `python -m pytest backend/tests/test_v5_agent_runtime.py backend/tests/test_v5_agent_api.py -q --basetemp=.pytest_tmp_agent_sse_final` | `20 passed` | No-cursor/stale/future reset, legal-cursor replay, private-event filtering and same-cursor non-journaled heartbeat. |
| Agent crash recovery focused suite | `10 passed` | Checkpoint validation, interrupted search recovery, unknown-model-result fail-closed behavior, latest-event cursors and concurrent claim CAS. |
| Outbox/Worker/Runtime focused suite | `33 passed` | Atomic claim, lease renewal, poison isolation, bounded retry/dead-letter and unique worker ownership. |
| Evaluator + acceptance focused tests | `2 passed in 11.91s` | Report provenance and tamper rejection covered using an isolated pytest basetemp. |
| Quick quality gate | passed | Final quick gate completed after the full regressions. |

### Frontend and browser

| Command or scope | Observed result |
|---|---|
| clean `npm ci` | 441 packages installed from lockfile; exit `0` |
| `npm run lint` | exit `0` |
| `npm run typecheck` | exit `0` |
| `npm run test:unit` | `17 files / 76 tests passed` |
| SSE/runtime/controller focused unit selection | `3 files / 12 tests passed` |
| `npm run build` | Next `15.5.23`, exit `0`, 34 routes generated |
| Strict live E2E | `27 / 27 passed in 38.7s`; durable backend demo run completed through the live Worker |
| V5.1 targeted Playwright | `2 / 2 passed` | Recording journal projection and production excluded-relation UI passed after the V5.1 fixes. |
| Current strict E2E rerun | `21 / 31 passed`; not presented as a pass | The local process did not provide `NEXT_PUBLIC_API_BASE_URL`, so backend-dependent media/chat/observability/live-worker cases failed or timed out. The two V5.1 product-loop cases were then rerun independently and passed. |
| Live Qdrant degradation observation | Qdrant returned `502`; canonical sparse fallback still produced a resolvable citation |
| `npm audit --omit=dev --audit-level=high` | `0 vulnerabilities` |

### Release verification

- The settled V5.1 source set was packaged as `AI-Knowledge-OS-Pro-V5.0-20260821.zip`: 590 tracked files, `forbidden=0`, `missing=0`, `manifest=verified`, `freshness=current`.
- SHA-256 is stored in the adjacent `.sha256` sidecar and verified by `check_release.py`; GitHub publication is not claimed.

### Static quality evidence

- UTF-8 encoding: 969 files passed; the checker also confirmed append-only preservation of 96 immutable legacy-log lines.
- Version consistency: `V5.0 / 5.0.0` passed.
- Secret scan: 443 tracked files, 0 findings.
- Frontend smoke: 29 routes and 12 navigation links passed.
- UI budget: 4 primary destinations and 8 Developer Mode destinations passed.
- Interaction scan: 103 buttons, 37 API-like actions, 3 intentionally high-risk actions with explicit confirmation/approval semantics.
- Request-cache, E2E static contract and screenshot assets passed. `python scripts/check_docs_links.py` passed across 150 documentation files, 15 local links, 3 local images and 9 Mermaid blocks.
- `git diff --check` reported no whitespace errors; Windows line-ending conversion warnings remain informational.

## Partial and Deferred Boundaries

| Boundary | Current behavior | Required follow-up |
|---|---|---|
| Production reranker | A configurable real HTTP adapter is delivered. Default runtime and the fixed evaluator leave it unconfigured; disabled mode fabricates no score and the evaluator uses a labeled recording adapter. | Configure credentials/endpoint and benchmark the HTTP Provider before claiming production rerank quality. |
| Claim verification | Deterministic entailment gate plus hard provenance checks reject unsupported numbers, names, polarity, ranges and entities. | Keep the gate conservative; a real-model factuality benchmark remains a separate evaluation task. |
| Usage and cost | Provider data is retained; missing tokens may use a labeled conservative estimate; unknown cost remains unknown. | Configure price tables/provider-reported cost where a hard currency budget must be guaranteed. |
| Production model quality | Real mode refuses to run when no LLM is configured. | Configure a real Provider and execute a separate, labeled real-model benchmark. |
| Alembic metadata drift | One head and V5 table metadata are clean. `alembic check` still sees historical 0001–0006 nullable/index/FK differences. | Reconcile historical migrations/model metadata in a separately scoped compatibility change; do not rewrite released migrations casually. |
| Legacy Qdrant payloads | Alembic is SQL-only by design; new points use canonical payloads. | Run `migrate_v5_evidence_data.py`/`reconcile_evidence_index.py` against the actual Qdrant collection, review dry-run, then apply/reindex. |
| Evaluation boundary | 60 deterministic synthetic cases, 0 external calls; the legacy comparison is a V4.9-style proxy on the V5 corpus. | Add reviewed real documents and real-model runs before making user-quality or historical-release claims. |
| Full accessibility/decision E2E | Main mobile flow, semantic controls, SSE refresh recovery and locator flows are tested. | Add keyboard-only clarification/cancel, Inspector focus, axe, stale approval and insufficient-continuation scenarios. |
| Release publication | Final local V5.0 archive passed the checker with 590 tracked files and a current verified manifest. | After merge/push, the repository owner can publish from the intended default branch; no remote publication is claimed here. |
| Public GitHub readiness | Local branch, documentation and screenshots are prepared. | Repository owner must merge/push, set the intended default branch, confirm anonymous visibility and publish a release. No such external change is claimed here. |

## Migration Safety Notes

- Downgrade journal entries distinguish restored V4.9 values, migration-created chains and V5-only state.
- A valid journal restores six legacy values and removes four pristine migration-created records in the current fixture; migration-created chains that were later adopted/modified are preserved where V4.9 can express them.
- Invalid or missing journal data fails closed before destructive schema operations; parameterized tests assert revision, schema and rows remain unchanged.
- V5-only tables, columns and rows are intentionally `drop_on_downgrade` because V4.9 has no representation for them.
- The migration never attempts to contact or roll back Qdrant. Vector payload remediation is an explicit post-upgrade operational step.

## Release Decision

The branch is a **V5 portfolio implementation with a locally verified release candidate**, with the stated boundaries. Its test evidence does not prove a fully configured production LLM/reranker deployment, a real-model quality benchmark, or public GitHub availability.

The final local archive and release checker are current. Remote merge, default-branch selection, repository visibility and GitHub Release publication remain owner-controlled external actions.
