# 溯知 V5 Evidence Agent Tasks

Status legend: `✅` = 有实现与可重复证据；`◐` = 主体完成，但仍有明确未完成的验收边界。未标识的任务不视为完成。

## File List

### Create

| Operation | File | Responsibility |
|---|---|---|
| Create | `backend/app/models/outbox.py` | Transactional outbox records and leases |
| Create | `backend/app/models/evidence_index.py` | IndexOperation and VectorPointManifest |
| Create | `backend/app/models/agent_run.py` | AgentRun, Step, ToolCall, Checkpoint and Interaction |
| Create | `backend/app/models/agent_evidence.py` | Requirement, Evidence, Claim and Artifact provenance |
| Create | `backend/app/models/agent_event.py` | Append-only run event journal |
| Create | `backend/app/modules/evidence_index/__init__.py` | EvidenceIndex exported interface |
| Create | `backend/app/modules/evidence_index/contracts.py` | Index commands, queries and immutable projections |
| Create | `backend/app/modules/evidence_index/service.py` | Deep indexing and search implementation |
| Create | `backend/app/modules/evidence_index/sql_store.py` | SQL lifecycle and projection implementation |
| Create | `backend/app/modules/evidence_index/sparse_adapter.py` | FTS5 and CJK sparse indexing |
| Create | `backend/app/modules/evidence_index/reconciler.py` | Cross-store dry-run/apply repair |
| Create | `backend/app/modules/evidence_index/wiring.py` | Production and deterministic module factories |
| Create | `backend/app/modules/evidence_agent/__init__.py` | EvidenceAgent exported interface |
| Create | `backend/app/modules/evidence_agent/contracts.py` | Commands, queries, events and outcomes |
| Create | `backend/app/modules/evidence_agent/service.py` | submit/inspect/follow deep implementation |
| Create | `backend/app/modules/evidence_agent/state_machine.py` | Pure lifecycle reducer |
| Create | `backend/app/modules/evidence_agent/controller.py` | Quick and bounded Agent slices |
| Create | `backend/app/modules/evidence_agent/budget.py` | Budget accounting and stop rules |
| Create | `backend/app/modules/evidence_agent/tools.py` | Allowlisted tools and effect guard |
| Create | `backend/app/modules/evidence_agent/sql_store.py` | Run projection, journal and checkpoint persistence |
| Create | `backend/app/modules/evidence_agent/wiring.py` | Runtime dependency factories |
| Create | `backend/app/services/agent_model.py` | Structured, deterministic and recording model adapters |
| Create | `backend/app/services/outbox_dispatcher.py` | Idempotent outbox publication and lease recovery |
| Create | `backend/app/schemas/agent_schema.py` | HTTP Agent schemas |
| Create | `backend/app/schemas/evidence_schema.py` | Evidence and Artifact HTTP schemas |
| Create | `backend/app/api/routes_agent_runs.py` | Run command/query/event/SSE routes |
| Create | `backend/app/api/routes_evidence.py` | Evidence resolution and reconcile routes |
| Create | `backend/app/tasks/agent_tasks.py` | One-slice Agent RQ task |
| Create | `backend/app/tasks/evidence_index_tasks.py` | Index and reconcile RQ tasks |
| Create | `backend/alembic/versions/0007_v5_evidence_index.py` | Canonical evidence lifecycle migration/backfill |
| Create | `backend/alembic/versions/0008_v5_agent_runtime.py` | Agent runtime persistence migration |
| Create | `backend/tests/test_v5_evidence_index_lifecycle.py` | Active revision and immutability behavior |
| Create | `backend/tests/test_v5_index_saga.py` | Crash/cancel/retry consistency behavior |
| Create | `backend/tests/test_v5_index_reconciler.py` | Orphan/missing/payload repair behavior |
| Create | `backend/tests/test_v5_active_retrieval.py` | Sparse/dense/RRF/active-only retrieval behavior |
| Create | `backend/tests/test_v5_agent_models.py` | Agent constraints and structured model behavior |
| Create | `backend/tests/test_v5_agent_runtime.py` | Quick/agent loop and terminal outcomes |
| Create | `backend/tests/test_v5_agent_human_loop.py` | Clarification/approval/resume/cancel behavior |
| Create | `backend/tests/test_v5_agent_worker_recovery.py` | Outbox/RQ replay, lease and cancel fence behavior |
| Create | `backend/tests/test_v5_agent_sse.py` | Cursor, reconnect and reset behavior |
| Create | `backend/tests/test_v5_agent_api.py` | HTTP contracts and error semantics |
| Create | `backend/tests/test_v5_agent_security.py` | Prompt injection and protected tool behavior |
| Create | `backend/tests/test_v5_migrations.py` | V4.9 data upgrade/downgrade round trip |
| Create | `frontend/modules/evidence-agent/contract.ts` | Zod schemas and derived types |
| Create | `frontend/modules/evidence-agent/evidence-agent.ts` | Three-entry frontend interface and factory |
| Create | `frontend/modules/evidence-agent/http-sse-adapter.ts` | HTTP/SSE production adapter |
| Create | `frontend/modules/evidence-agent/recording-adapter.ts` | Deterministic UI/demo adapter |
| Create | `frontend/modules/evidence-agent/run-controller.ts` | Cursor, reducer, reconnect and React subscription |
| Create | `frontend/modules/evidence-agent/research-catalog.ts` | Runs/Artifacts catalog adapter |
| Create | `frontend/modules/evidence-agent/source-locator.ts` | Page/time/code locator links |
| Create | `frontend/modules/evidence-agent/contract.test.ts` | Contract validation tests |
| Create | `frontend/modules/evidence-agent/run-controller.test.ts` | Event/reconnect/controller tests |
| Create | `frontend/app/workbench/page.tsx` | Research goal entry route |
| Create | `frontend/app/runs/page.tsx` | Run catalog route |
| Create | `frontend/app/runs/[runId]/page.tsx` | Run workspace route |
| Create | `frontend/app/library/page.tsx` | Unified source library route |
| Create | `frontend/app/library/sources/[id]/page.tsx` | Revision-aware source viewer |
| Create | `frontend/app/artifacts/page.tsx` | Artifact catalog route |
| Create | `frontend/app/artifacts/[artifactId]/page.tsx` | Structured Artifact reader route |
| Create | `frontend/components/workbench/Workbench.tsx` | Goal/scope composer |
| Create | `frontend/components/workbench/Workbench.module.css` | Composer-local styles |
| Create | `frontend/components/runs/RunWorkspace.tsx` | RunView composition root |
| Create | `frontend/components/runs/PlanTimeline.tsx` | Requirements and step timeline |
| Create | `frontend/components/runs/EvidenceLedger.tsx` | Support/contradiction/gap view |
| Create | `frontend/components/runs/HumanDecisionPanel.tsx` | Clarification and exact approval view |
| Create | `frontend/components/runs/BudgetMeter.tsx` | Accessible usage limits |
| Create | `frontend/components/runs/RunWorkspace.module.css` | Responsive run layout |
| Create | `frontend/components/evidence/EvidenceInspector.tsx` | Revision/hash/locator inspector |
| Create | `frontend/components/evidence/EvidenceInspector.module.css` | Rail/sheet inspector styles |
| Create | `frontend/components/artifacts/ArtifactDocument.tsx` | Claim and gap renderer |
| Create | `frontend/components/artifacts/ArtifactDocument.module.css` | Artifact reading styles |
| Create | `frontend/components/library/LibraryWorkspace.tsx` | Space/source/revision catalog |
| Create | `frontend/components/ui/Dialog.tsx` | Accessible focus-managed dialog |
| Create | `frontend/components/ui/StatusAnnouncer.tsx` | Throttled run status announcements |
| Create | `frontend/eslint.config.mjs` | ESLint 9 configuration |
| Create | `frontend/e2e/agent-golden-flow.spec.ts` | Full evidence research flow |
| Create | `frontend/e2e/agent-citation-locators.spec.ts` | Page/time/code citation behavior |
| Create | `frontend/e2e/agent-resume-cancel.spec.ts` | Reconnect, HITL, cancel and budget behavior |
| Create | `evaluation/v5/cases.jsonl` | Categorized evaluation cases |
| Create | `evaluation/v5/corpus/README.md` | Corpus provenance and fixture contract |
| Create | `scripts/evaluate_agentic_rag.py` | Full-pipeline baseline/Agent evaluator |
| Create | `scripts/check_v5_acceptance.py` | Machine-readable V5 gate |
| Create | `scripts/migrate_v5_evidence_data.py` | Post-Alembic Qdrant payload/reindex migration |
| Create | `scripts/verify_v5_migration.py` | Populated database migration verifier |
| Create | `scripts/reconcile_evidence_index.py` | Safe dry-run/apply repair CLI |
| Create | `docs/v5_agentic_rag/engineering_log.md` | Engineering difficulties and resolutions |
| Create | `docs/v5_agentic_rag/checklist.md` | Observable acceptance checklist |
| Create | `docs/v5_agentic_rag/acceptance_report.md` | Actual evidence from final acceptance |

### Modify

| Operation | File | Responsibility |
|---|---|---|
| Modify | `backend/app/models/source.py` | Lifecycle fields, hashes, relationships and constraints |
| Modify | `backend/app/models/document.py` | Canonical Source relationship and legacy projection status |
| Modify | `backend/app/models/__init__.py` | Register V5 metadata |
| Modify | `backend/app/db/session.py` | Foreign keys, WAL and busy timeout |
| Modify | `backend/app/services/ingestion_service.py` | Submit document RevisionDraft; soft retire |
| Modify | `backend/app/services/media_service.py` | Submit media RevisionDraft |
| Modify | `backend/app/services/code_repository_service.py` | Submit code RevisionDraft |
| Modify | `backend/app/services/media_task_service.py` | Separate processing and index activation states |
| Modify | `backend/app/services/hybrid_retriever.py` | Compatibility facade over active EvidenceIndex search |
| Modify | `backend/app/services/vector_store.py` | Structured filters, scroll, retrieve and payload patch |
| Modify | `backend/app/services/rerank_provider.py` | Configurable real HTTP rerank adapter |
| Modify | `backend/app/services/providers.py` | Structured LLM result and usage metadata |
| Modify | `backend/app/services/llm_service.py` | Validated structured generation |
| Modify | `backend/app/services/rag_service.py` | Quick compatibility Adapter and immutable refs |
| Modify | `backend/app/services/task_broker.py` | TaskEnvelope publication and Agent/index support |
| Modify | `backend/app/tasks/ingestion_tasks.py` | Delegate canonical indexing |
| Modify | `backend/app/worker.py` | Outbox dispatch and expired lease recovery |
| Modify | `backend/app/api/router.py` | Register V5 routes |
| Modify | `backend/app/core/config.py` | Agent, outbox, rerank, SSE and budget settings |
| Modify | `backend/.env.example` | V5 configuration examples |
| Modify | `backend/tests/conftest.py` | Filterable vector, broker and model fakes |
| Modify | `backend/requirements.txt` | Pin/declare required runtime and test dependencies |
| Modify | `frontend/app/page.tsx` | Root redirect to Workbench |
| Modify | `frontend/app/layout.tsx` | 溯知 metadata and skip link |
| Modify | `frontend/app/globals.css` | Shared focus, safe-area and base layout rules |
| Modify | `frontend/components/AppShell.tsx` | Four-zone IA and Developer Mode |
| Modify | `frontend/components/KnowledgeChat.tsx` | Space reset and true Run cancellation compatibility |
| Modify | `frontend/components/CitationPanel.tsx` | Legacy Evidence Inspector wrapper |
| Modify | `frontend/components/DocumentUploader.tsx` | Library-controlled upload scope and callbacks |
| Modify | `frontend/components/ui.tsx` | Accessible labels and tab semantics |
| Modify | `frontend/services/api.ts` | Mark legacy and add safe compatibility helpers |
| Modify | `frontend/types/api.ts` | Optional revision/hash legacy mapping |
| Modify | `frontend/next.config.ts` | Legacy redirects and SSE-safe proxy behavior |
| Modify | `frontend/.env.local.example` | Adapter/proxy configuration |
| Modify | `frontend/package.json` | Lint, unit test and runtime validation scripts/deps |
| Modify | `frontend/package-lock.json` | Reproducible dependency graph |
| Modify | `frontend/playwright.config.ts` | Recording, desktop and mobile projects |
| Modify | `frontend/e2e/citation-jump.spec.ts` | Verify target highlight, revision and hash |
| Modify | `frontend/e2e/demo-smoke.spec.ts` | Four-zone core and legacy compatibility smoke |
| Modify | `frontend/DESIGN.md` | V5 IA and evidence visual semantics |
| Modify | `.github/workflows/ci.yml` | V5 migrations, lint, unit, eval and E2E gates |
| Modify | `README.md` | Evidence-first V5 narrative and measured results |

## T1: Record and verify the clean V4.9 baseline ✅
**Files:** `docs/v5_agentic_rag/engineering_log.md`
**Depends on:** None
**Steps:**
1. Record branch, commit, dirty files, Python/Node versions and known baseline failures.
2. Run targeted backend and frontend baseline commands without modifying implementation.
**Verification:** `git diff --check`; log contains exact commands and outputs.

## T2: Write failing SQLite runtime safety test ✅
**Files:** `backend/tests/test_v5_migrations.py`
**Depends on:** T1
**Steps:**
1. Add behavior test asserting foreign keys, busy timeout and concurrent-safe journal settings.
2. Confirm it fails on V4.9 session configuration.
**Verification:** Run the single test; expect RED for missing pragmas.

## T3: Enable SQLite integrity settings ✅
**Files:** `backend/app/db/session.py`, `backend/tests/test_v5_migrations.py`
**Depends on:** T2
**Steps:** Implement connection listener for foreign keys, WAL where applicable and busy timeout.
**Verification:** Rerun T2 test; expect GREEN.

## T4: Write failing canonical revision migration test ✅
**Files:** `backend/tests/test_v5_migrations.py`
**Depends on:** T3
**Steps:** Seed representative V4.9 Document/Chunk, media revisions and stale active rows; assert canonical Source, one active revision/index and preserved legacy readability after upgrade.
**Verification:** Run the test against current head; expect RED because 0007 is absent.

## T5: Add evidence lifecycle and outbox models ✅
**Files:** `backend/app/models/source.py`, `backend/app/models/document.py`, `backend/app/models/evidence_index.py`, `backend/app/models/outbox.py`, `backend/app/models/__init__.py`
**Depends on:** T4
**Steps:** Add hashes, retirement fields, operation/manifest/outbox tables and uniqueness/index declarations.
**Verification:** `python -m compileall backend/app`; metadata contains every new table.

## T6: Implement 0007 structural and data migration ✅
**Files:** `backend/alembic/versions/0007_v5_evidence_index.py`, `scripts/verify_v5_migration.py`
**Depends on:** T5
**Steps:** Create structures, normalize active rows, backfill canonical document revisions and implement downgrade without external Qdrant calls.
**Verification:** T4 becomes GREEN; `alembic upgrade head`, downgrade to 0006 and re-upgrade succeed on a populated temporary DB.

## T7: Define EvidenceIndex contract through a failing interface test ✅
**Files:** `backend/app/modules/evidence_index/contracts.py`, `backend/app/modules/evidence_index/__init__.py`, `backend/tests/test_v5_evidence_index_lifecycle.py`
**Depends on:** T6
**Steps:** Add immutable commands/queries/projections and a RED test for command/query/search behavior without exposing ORM records.
**Verification:** Test imports contract but fails for missing implementation.

## T8: Implement sparse Adapter tracer bullet ✅
**Files:** `backend/app/modules/evidence_index/sparse_adapter.py`, `backend/tests/test_v5_active_retrieval.py`
**Depends on:** T7
**Steps:** Test oldest exact hit and CJK tokens first, then implement FTS5 row maintenance and ranking.
**Verification:** 30-chunk oldest-hit test is GREEN.

## T9: Add structured dense filters ✅
**Files:** `backend/app/services/vector_store.py`, `backend/tests/conftest.py`, `backend/tests/test_v5_active_retrieval.py`
**Depends on:** T8
**Steps:** Write RED active revision/index filter test, then add MatchAny/filter/scroll/retrieve/set-payload support to real and fake adapters.
**Verification:** Stale dense point cannot occupy returned top-k.

## T10: Persist staging manifest before upsert ✅
**Files:** `backend/app/modules/evidence_index/sql_store.py`, `backend/app/modules/evidence_index/service.py`, `backend/tests/test_v5_index_saga.py`
**Depends on:** T9
**Steps:** RED test upsert crash window, then persist staging revision/chunks/index/manifest/outbox and deterministic point ids before external calls.
**Verification:** After injected crash every external point id remains tracked and old revision stays active.

## T11: Activate new revision only after validation ✅
**Files:** `backend/app/modules/evidence_index/service.py`, `backend/tests/test_v5_evidence_index_lifecycle.py`
**Depends on:** T10
**Steps:** Test double processing, then implement count/payload/fingerprint validation and atomic active pointer swap.
**Verification:** Only new revision is query-visible; old one is retired after success.

## T12: Make cancel/retry idempotent ✅
**Files:** `backend/app/modules/evidence_index/service.py`, `backend/tests/test_v5_index_saga.py`
**Depends on:** T11
**Steps:** Test cancel after upsert and repeated command ids; implement cancellation fence, compensation state and dedupe receipts.
**Verification:** Repeated retry creates no duplicate revision or point.

## T13: Implement reconciler dry-run and apply ✅
**Files:** `backend/app/modules/evidence_index/reconciler.py`, `scripts/reconcile_evidence_index.py`, `backend/tests/test_v5_index_reconciler.py`
**Depends on:** T12
**Steps:** Test orphan/missing/payload mismatch; implement report-only default and explicit apply repairs.
**Verification:** Dry-run changes nothing; apply converges and second dry-run reports clean.

## T14: Implement RRF and context packing ◐
**Status:** active/pinned scope 下的 dense/sparse RRF、融合后统一 threshold、chunk identity 去重与 revision/index/chunk 生命周期过滤已实现并有定向测试；显式 context packing、source-diversity quota 与 token-budget packing 尚未实现或验证，因此本任务不能标记为完整。
**Files:** `backend/app/services/hybrid_retriever.py`, `backend/app/modules/evidence_agent/search_adapter.py`, `backend/tests/test_v5_active_retrieval.py`
**Depends on:** T13
**Steps:** Test dense/sparse rank fusion, threshold, de-duplication, source diversity and token budget; implement compatibility facade.
**Verification:** 独立 RRF、统一 threshold、oldest sparse hit、active/pinned filter 与去重行为已通过；source diversity 和 token/context packing 仍是明确缺口。

## T15: Add real optional rerank Adapter ✅
**Status:** 已实现独立 rerank port、可选 HTTP Provider、超时/错误处理、诚实 disabled 边界与 deterministic recording 评测臂。默认运行与固定报告未配置真实 reranker，因此不宣称真实模型重排质量。
**Files:** `backend/app/services/rerank_provider.py`, `backend/app/core/config.py`, `backend/.env.example`, `backend/tests/test_v5_active_retrieval.py`
**Depends on:** T14
**Steps:** Add recording contract test, HTTP Adapter, timeout/error handling and honest disabled mode.
**Verification:** Recording adapter changes order; disabled mode emits no fabricated score.

## T16: Implement evidence resolve and neighbors ◐
**Status:** pinned search 可解析 retired immutable evidence，EvidenceRef 可校验 revision/hash/locator；独立 ResolveEvidence/ReadNeighbors 查询及 Agent Runner 的 neighbor tool 执行链尚未完整落地。
**Files:** `backend/app/modules/evidence_index/service.py`, `backend/tests/test_v5_evidence_index_lifecycle.py`
**Depends on:** T15
**Steps:** Test hash/locator mismatch and same-revision window; implement ResolveEvidence/ReadNeighbors queries.
**Verification:** Wrong revision/hash is rejected; valid page/time/code windows are stable.

## T17: Route document ingestion through EvidenceIndex ✅
**Files:** `backend/app/services/ingestion_service.py`, `backend/app/tasks/ingestion_tasks.py`, `backend/tests/test_v5_evidence_index_lifecycle.py`
**Depends on:** T16
**Steps:** Test document reprocess and soft retire; create canonical Source/RevisionDraft while maintaining legacy Chunk projection.
**Verification:** Two document versions satisfy AC1 and legacy document detail remains readable.

## T18: Route media processing through EvidenceIndex ✅
**Files:** `backend/app/services/media_service.py`, `backend/app/services/media_task_service.py`, `backend/tests/test_v5_evidence_index_lifecycle.py`
**Depends on:** T17
**Steps:** Replace direct activation/upsert with RevisionDraft command and separate processing/index status.
**Verification:** Repeated OCR/STT retires all old chunks/indexes and preserves locator behavior.

## T19: Route code ingestion through EvidenceIndex ✅
**Files:** `backend/app/services/code_repository_service.py`, `backend/tests/test_v5_evidence_index_lifecycle.py`
**Depends on:** T18
**Steps:** Replace direct vector writes with RevisionDraft and preserve file/line/symbol locators.
**Verification:** Reingested repository only exposes latest revision and exact code lines.

## T20: Extend Provider result contracts ✅
**Files:** `backend/app/services/providers.py`, `backend/app/services/llm_service.py`, `backend/app/services/agent_model.py`, `backend/tests/test_v5_agent_models.py`
**Depends on:** T19
**Steps:** RED structured output/usage test, then add LLMResult and Pydantic validated structured generation with one repair attempt.
**Verification:** Invalid JSON ends explicitly after one repair; usage metadata is retained.

## T21: Add Agent runtime persistence migration ✅
**Files:** `backend/app/models/agent_run.py`, `backend/app/models/agent_evidence.py`, `backend/app/models/agent_event.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/0008_v5_agent_runtime.py`, `backend/tests/test_v5_migrations.py`
**Depends on:** T20
**Steps:** RED schema/invariant test, create runtime tables and downgrade path.
**Verification:** 0006→head→0006→head round trip succeeds with V4.9 data.

## T22: Implement pure Agent state machine ✅
**Files:** `backend/app/modules/evidence_agent/contracts.py`, `backend/app/modules/evidence_agent/state_machine.py`, `backend/app/modules/evidence_agent/__init__.py`, `backend/tests/test_v5_agent_models.py`
**Depends on:** T21
**Steps:** Test legal/illegal transitions and normal insufficient outcome before implementing reducer.
**Verification:** Illegal transitions are rejected without side effects.

## T23: Implement submit command idempotency ✅
**Files:** `backend/app/modules/evidence_agent/sql_store.py`, `backend/app/modules/evidence_agent/service.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T22
**Steps:** RED duplicate OpenRun/SignalRun tests, then persist command receipt, pinned revisions, run and first event transactionally.
**Verification:** Same command id returns same receipt and one run/event set.

## T24: Implement inspect and event cursor ✅
**Status:** 持久 snapshot、单调 cursor、缺失事件回放、无 cursor/stale/future cursor reset、不消耗 cursor 且不写 journal 的 heartbeat，以及刷新后 Ledger/interaction 重建均已实现并通过前后端契约测试。
**Files:** `backend/app/modules/evidence_agent/sql_store.py`, `backend/app/modules/evidence_agent/service.py`, `backend/tests/test_v5_agent_sse.py`
**Depends on:** T23
**Steps:** Test snapshot, ordered cursor and replay; implement materialized queries and append-only events.
**Verification:** Reconnect returns only missing events and cursor order is monotonic.

## T25: Implement deterministic quick mode ✅
**Files:** `backend/app/modules/evidence_agent/controller.py`, `backend/app/services/agent_model.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T24
**Steps:** RED simple-question behavior, then implement route→search→synthesize→verify without planning step.
**Verification:** Quick run has no PlanProposed event and produces cited claims.

## T26: Implement plan and evidence tools ✅
**Status:** 多需求计划、pinned-scope hybrid search 与完整 EvidenceRef 已实现；V5.1 已让 Runner 依次执行 search_evidence、open_evidence 与 bounded read_neighbors，并写入独立 ToolCall/Event/Checkpoint。
**Files:** `backend/app/modules/evidence_agent/tools.py`, `backend/app/modules/evidence_agent/controller.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T25
**Steps:** Test complex task plan and at least two read tools; implement list/search/open/neighbors allowlist.
**Verification:** Cross-source run emits visible plan and immutable evidence refs.

## T27: Implement Evidence Ledger and sufficiency loop ◐
**Status:** 后端已持久化 requirement/evidence/claim，并覆盖 supports、contradicts、gap、候选选择/校验及 evidence 不足的正常领域结果；excluded reason 与 next-query 在 production event→前端 Ledger 的完整投影和 UI 对照矩阵尚未闭环，与 Checklist AC7 保持部分完成。
**Files:** `backend/app/modules/evidence_agent/controller.py`, `backend/app/services/agent_model.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T26
**Steps:** Test supports/contradicts/excluded/gaps and search_more/clarify/answer decisions, then implement one slice per decision.
**Verification:** 后端持久投影、关系校验与 insufficient-evidence 非 5xx 行为已有测试；excluded/next-query 的 production UI 全链路仍待补齐。

## T28: Enforce hard budgets and no-new-evidence stop ✅
**Files:** `backend/app/modules/evidence_agent/budget.py`, `backend/app/modules/evidence_agent/controller.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T27
**Steps:** Test each limit and two empty rounds, then implement accounting and terminal reasons.
**Verification:** No test can exceed configured steps/tool calls/tokens/time/cost.

## T29: Implement claim verification and Artifact provenance ✅
**Files:** `backend/app/modules/evidence_agent/controller.py`, `backend/app/modules/evidence_agent/sql_store.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T28
**Steps:** Test unsupported factual claim rejection, then persist Artifact/Claim/ClaimEvidence and gap report.
**Verification:** Every factual claim has non-empty valid EvidenceRef support.

## T30: Implement clarification and exact approval ✅
**Files:** `backend/app/modules/evidence_agent/service.py`, `backend/app/modules/evidence_agent/tools.py`, `backend/tests/test_v5_agent_human_loop.py`
**Depends on:** T29
**Steps:** RED clarify/resume, stale version, stale digest and duplicate approval tests; implement single-use interactions.
**Verification:** Modified proposal invalidates old approval; checkpoint resumes once.

## T31: Implement cancellation fence ✅
**Files:** `backend/app/modules/evidence_agent/service.py`, `backend/app/modules/evidence_agent/controller.py`, `backend/tests/test_v5_agent_human_loop.py`
**Depends on:** T30
**Steps:** Test cancel during blocking recording Provider; implement pre/post-call checks and discard returned work.
**Verification:** After cancel no new evidence, tool result or Artifact is committed.

## T32: Prove prompt-injection isolation ✅
**Files:** `backend/app/modules/evidence_agent/tools.py`, `backend/app/services/agent_model.py`, `backend/tests/test_v5_agent_security.py`
**Depends on:** T31
**Steps:** Add malicious evidence and protected fake tools; enforce effect policy and untrusted-evidence prompt framing.
**Verification:** Unauthorized action rate is zero in deterministic security cases.

## T33: Implement outbox dispatcher and bounded RQ slices ✅
**Files:** `backend/app/services/outbox_dispatcher.py`, `backend/app/services/task_broker.py`, `backend/app/tasks/agent_tasks.py`, `backend/app/tasks/evidence_index_tasks.py`, `backend/app/worker.py`, `backend/tests/test_v5_agent_worker_recovery.py`
**Depends on:** T32
**Steps:** Test duplicate delivery and expired lease, then publish deterministic TaskEnvelope and execute one slice per job.
**Verification:** At-least-once replay produces one domain effect and recovery resumes from checkpoint.

## T34: Wire production and deterministic modules ✅
**Files:** `backend/app/modules/evidence_index/wiring.py`, `backend/app/modules/evidence_agent/wiring.py`, `backend/tests/conftest.py`
**Depends on:** T33
**Steps:** Add factories for production, inline tests and recording eval without constructors creating hidden dependencies.
**Verification:** Runtime tests use public interfaces with no real Redis/Qdrant/LLM connection.

## T35: Add Agent and Evidence HTTP schemas ✅
**Files:** `backend/app/schemas/agent_schema.py`, `backend/app/schemas/evidence_schema.py`, `backend/tests/test_v5_agent_api.py`
**Depends on:** T34
**Steps:** RED contract tests for commands, normal outcomes and validation errors; implement Pydantic schemas with schema_version.
**Verification:** OpenAPI contains stable V5 unions and insufficient_evidence is 200-domain outcome.

## T36: Add command/query routes ✅
**Files:** `backend/app/api/routes_agent_runs.py`, `backend/app/api/routes_evidence.py`, `backend/app/api/router.py`, `backend/tests/test_v5_agent_api.py`
**Depends on:** T35
**Steps:** Map routes only to EvidenceAgent/EvidenceIndex interfaces and return request/run ids.
**Verification:** API integration tests pass through the same runtime seam.

## T37: Add SSE Adapter ✅
**Status:** text/event-stream、Last-Event-ID/query cursor、no-cache/no-buffer、短 Session、stale/future/no-cursor reset 与 cursor-free heartbeat contract 已实现。heartbeat 是输送层帧，不持久到 journal，也不进入 RunController 事件列表。
**Files:** `backend/app/api/routes_agent_runs.py`, `backend/tests/test_v5_agent_sse.py`
**Depends on:** T36
**Steps:** Test Last-Event-ID/query cursor, heartbeat, headers and short-lived DB sessions; implement StreamingResponse.
**Verification:** Disconnect/reconnect has no event loss and envelope middleware does not wrap SSE.

## T38: Preserve legacy quick Chat compatibility ✅
**Files:** `backend/app/services/rag_service.py`, `backend/app/api/routes_chat.py`, `backend/tests/test_v5_agent_api.py`
**Depends on:** T37
**Steps:** Map new quick EvidenceRefs into legacy ChatResponse while retaining explicit fallback during migration.
**Verification:** Existing chat contract tests and V5 quick tests both pass.

## T39: Verify frontend dependency versions and add test tooling ✅
**Files:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/eslint.config.mjs`
**Depends on:** T38
**Steps:** Verify current official/npm versions, add Zod/Vitest/axe as required, replace obsolete lint script and install lockfile.
**Verification:** `npm ci`, `npm run lint`, `npm run typecheck`, empty Vitest invocation succeed.

## T40: Write RED runtime contract tests ✅
**Files:** `frontend/modules/evidence-agent/contract.ts`, `frontend/modules/evidence-agent/contract.test.ts`
**Depends on:** T39
**Steps:** Test non-empty factual support, revision/hash/locator, outcome union and unknown event rejection before schemas.
**Verification:** Tests fail before schema implementation, then pass after minimal Zod schemas.

## T41: Implement HTTP/SSE Adapter and RunController ✅
**Files:** `frontend/modules/evidence-agent/evidence-agent.ts`, `frontend/modules/evidence-agent/http-sse-adapter.ts`, `frontend/modules/evidence-agent/recording-adapter.ts`, `frontend/modules/evidence-agent/run-controller.ts`, `frontend/modules/evidence-agent/run-controller.test.ts`
**Depends on:** T40
**Steps:** RED de-dup/reconnect/reset/cancel tests, then implement adapters, versioned cursor and `useSyncExternalStore` projection.
**Verification:** Duplicate event and reconnect tests are GREEN; aborting observation does not cancel run.

## T42: Add four-zone shell and compatibility navigation ✅
**Files:** `frontend/components/AppShell.tsx`, `frontend/app/page.tsx`, `frontend/app/layout.tsx`, `frontend/next.config.ts`, `frontend/DESIGN.md`
**Depends on:** T41
**Steps:** Update brand/metadata, four primary routes, collapsed Developer Mode, exact active item and legacy redirects.
**Verification:** Static UI tests and route smoke show one active nav item and no portfolio/learning top-level entries.

## T43: Build Workbench vertical slice ✅
**Files:** `frontend/app/workbench/page.tsx`, `frontend/components/workbench/Workbench.tsx`, `frontend/components/workbench/Workbench.module.css`
**Depends on:** T42
**Steps:** Implement goal/space/source scope, folded advanced controls, validation and navigation to created run.
**Verification:** Recording adapter creates one run and space switch clears old scope/result.

## T44: Build Run Workspace ◐
**Status:** 计划、Evidence Ledger、预算、终态、批准/拒绝、取消和澄清输入 UI 已实现；“全流程纯键盘 + 澄清 + 取消”的 recording E2E 还未全部覆盖。
**Files:** `frontend/app/runs/page.tsx`, `frontend/app/runs/[runId]/page.tsx`, `frontend/components/runs/RunWorkspace.tsx`, `frontend/components/runs/PlanTimeline.tsx`, `frontend/components/runs/EvidenceLedger.tsx`, `frontend/components/runs/HumanDecisionPanel.tsx`, `frontend/components/runs/BudgetMeter.tsx`, `frontend/components/runs/RunWorkspace.module.css`
**Depends on:** T43
**Steps:** Render one RunView, semantic plan/steps, relation groups, budget, attention and terminal outcome.
**Verification:** Keyboard-only recording flow can clarify, approve/deny, cancel and reach Artifact.

## T45: Build Evidence Inspector and source locator ◐
**Status:** document/page、media/timestamp 和 code/line 的生产 URL mapping 及 locator 测试已落地；原计划中独立 Inspector dialog 的 focus trap/restore 未完整实现。
**Files:** `frontend/modules/evidence-agent/source-locator.ts`, `frontend/components/evidence/EvidenceInspector.tsx`, `frontend/components/evidence/EvidenceInspector.module.css`, `frontend/app/library/sources/[id]/page.tsx`
**Depends on:** T44
**Steps:** RED page/time/code URL mapping, then render immutable revision/hash/excerpt/claims and exact target highlight.
**Verification:** PDF page, media timestamp and numbered code line tests pass and focus restores on close.

## T46: Build Library and Artifact views ✅
**Files:** `frontend/app/library/page.tsx`, `frontend/components/library/LibraryWorkspace.tsx`, `frontend/app/artifacts/page.tsx`, `frontend/app/artifacts/[artifactId]/page.tsx`, `frontend/components/artifacts/ArtifactDocument.tsx`, `frontend/components/artifacts/ArtifactDocument.module.css`, `frontend/modules/evidence-agent/research-catalog.ts`
**Depends on:** T45
**Steps:** Add source/revision status, structured claims/gaps, producing run and bidirectional provenance links.
**Verification:** Artifact→Evidence→Source and Source→Artifact paths are observable.

## T47: Add accessible shared controls and responsive states ◐
**Status:** skip link、焦点可见、语义状态、reduced motion、mobile layout 与导航测试已实现；独立 Inspector/Dialog 的完整焦点圈定和全流程 axe/keyboard E2E 未完成。
**Files:** `frontend/components/ui/Dialog.tsx`, `frontend/components/ui/StatusAnnouncer.tsx`, `frontend/components/ui.tsx`, `frontend/app/globals.css`
**Depends on:** T46
**Steps:** Implement focus trap/restore, Escape, status throttling, skip link, labels, reduced motion and mobile sheet.
**Verification:** Keyboard/mobile Playwright assertions and automated accessibility scan pass.

## T48: Repair legacy Chat and citation gaps ✅
**Files:** `frontend/components/KnowledgeChat.tsx`, `frontend/components/CitationPanel.tsx`, `frontend/components/DocumentUploader.tsx`, `frontend/services/api.ts`, `frontend/types/api.ts`, `frontend/e2e/citation-jump.spec.ts`
**Depends on:** T47
**Steps:** Clear cross-space result, send true cancel command, map legacy citation to Evidence Inspector and verify real line/time target.
**Verification:** Existing citation test is strengthened and passes; no stale result after scope switch.

## T49: Create the fixed evaluation corpus ✅
**Files:** `evaluation/v5/cases.jsonl`, `evaluation/v5/corpus/README.md`
**Depends on:** T38
**Steps:** Add at least 60 reviewed cases across single-hop, multi-hop, cross-modal, revision conflict, insufficient, injection and recovery with independent expected refs/outcomes.
**Verification:** Dataset validator reports category counts, unique ids and valid expected locators.

## T50: Implement full-pipeline evaluator ✅
**Files:** `scripts/evaluate_agentic_rag.py`, `backend/tests/test_v5_agent_runtime.py`
**Depends on:** T49
**Steps:** Run V4.9 baseline, retrieval baseline and Agent through real module interfaces; compute retrieval/evidence/Agent/system/safety metrics with demo/real label.
**Verification:** A deterministic report is reproduced byte-for-byte except timestamps; no seeded QA-log shortcut.

## T51: Add migration and reconcile CLIs ✅
**Files:** `scripts/migrate_v5_evidence_data.py`, `scripts/verify_v5_migration.py`, `scripts/reconcile_evidence_index.py`
**Depends on:** T50
**Steps:** Implement safe preflight, dry-run defaults, explicit apply and no external access from Alembic.
**Verification:** Temporary V4.9 DB upgrades; dry-run mutates nothing; apply is idempotent.

## T52: Write recording golden E2E ◐
**Status:** Workbench → Run → approval → cited Artifact 的 recording Playwright 已通过；同一黄金流程中的 clarification 分支尚未自动化。
**Files:** `frontend/e2e/agent-golden-flow.spec.ts`, `frontend/e2e/demo-smoke.spec.ts`, `frontend/playwright.config.ts`
**Depends on:** T48
**Steps:** Cover Workbench→plan→evidence→clarify/approve→Artifact→locator→Run using deterministic recording data.
**Verification:** Desktop Chromium golden spec passes without hardcoded database ids.

## T53: Write resilience and locator E2E ◐
**Status:** document/media/code locator E2E、mobile 主流程、后端 reset/heartbeat、前端 reconnect/de-dup/reset 与生产页刷新重建已落地；仍缺 stale approval、budget/insufficient/cancel 的完整组合 E2E 矩阵。
**Files:** `frontend/e2e/agent-citation-locators.spec.ts`, `frontend/e2e/agent-resume-cancel.spec.ts`, `frontend/e2e/citation-jump.spec.ts`, `frontend/playwright.config.ts`
**Depends on:** T52
**Steps:** Cover reconnect/de-dup/reset, stale approval, cancel, budget stop, insufficient evidence, all locator kinds and mobile project.
**Verification:** Desktop and mobile Chromium specs pass.

## T54: Add V5 machine acceptance gate ◐
**Status:** evaluator provenance、60-case matrix、引用/安全/恢复/成本诚实性与实现文件门禁已通过，且 backend/frontend/migration/strict E2E 门禁已独立实跑。仍标记为部分完成，因为本地 acceptance script 本身不汇总或强制这些外部作业证据。
**Files:** `scripts/check_v5_acceptance.py`, `.github/workflows/ci.yml`
**Depends on:** T51, T53
**Steps:** Check migrations, dataset, eval provenance, backend tests, frontend lint/unit/build and E2E artifacts; simplify obsolete self-check noise where safe.
**Verification:** CI-equivalent local gate returns zero only when required evidence exists.

## T55: Run backend regression and migration matrix ◐
**Status:** provider-mode injection fallback、稳定 active-time 计量、crash recovery、Runner CAS、outbox safety 与 live-worker 修复后 backend 全量 `439 passed, 1 skipped`；Alembic single head、populated round-trip 与 warning-clean migration 回归已通过。仍标记为部分完成，因为 `alembic check` 保留 0001–0006 历史 nullable/index/FK metadata drift；V5-specific drift 为 0。
**Files:** Implementation and tests above
**Depends on:** T54
**Steps:** Run compile, focused tests, full backend suite, Alembic heads/check/upgrade/downgrade/re-upgrade and reconciler fixtures; fix every regression.
**Verification:** Actual command outputs are captured for checklist evidence.

## T56: Run frontend regression and dependency audit ✅
**Status:** clean `npm ci`、lint、typecheck、17 files / 73 tests、Next 15.5.23 production build（34 routes）、strict live E2E `27/27` 和 production audit `0 vulnerabilities` 均已通过；live Worker 场景实际完成 durable backend run。
**Files:** Frontend implementation above
**Depends on:** T55
**Steps:** Run npm ci, lint, typecheck, unit, build, strict E2E and production dependency audit; fix failures or document external advisory blockers exactly.
**Verification:** Actual outputs are captured; no “should pass” claims.

## T57: Run code review against V4.9 base ◐
**Status:** Standards/Spec 两轴初审已执行，真实 Provider 边界、hybrid Agent wiring、locator、clarification、Ledger event、迁移可逆性、SSE resilience 与 recording UUID 并发性修复已完成聚焦回归。最终 Standards/Spec follow-up 仍在运行，不预先声明无 P0/P1；neighbor tool 执行链是已接受的明示部分项。
**Files:** All changed files
**Depends on:** T56
**Steps:** Use code-review workflow for Standards and Spec axes, prioritize findings, fix accepted findings and rerun affected tests.
**Verification:** No unresolved P0/P1 and every spec discrepancy has disposition.

## T58: Execute checklist and record acceptance ✅
**Status:** 已建立验收报告，并将 backend `439 passed, 1 skipped`、frontend clean install / 73 tests / 34 routes、strict live E2E `27/27`、crash/outbox/SSE resilience、迁移与 quick/evaluator gates 按实际证据同步。46/66 项有直接通过证据，其余 20 项保留明确部分边界，没有把未验证项伪装为通过。
**Files:** `docs/v5_agentic_rag/checklist.md`, `docs/v5_agentic_rag/acceptance_report.md`, `docs/v5_agentic_rag/engineering_log.md`
**Depends on:** T57
**Steps:** Run every behavior check, record evidence, diagnose failures, fix and rerun until true or explicitly failed.
**Verification:** Report counts passed/total and links each item to authoritative output.

## T59: Refresh public presentation only from measured evidence ◐
**Status:** V5 名称、架构、四张真实流程截图、五分钟路径和确定性评测数字已落地；最终 V5.0 本地 archive 已通过检查（590 files、0 forbidden、0 missing、manifest verified、freshness current）。仍标记为部分完成，因为 GitHub 匿名可见性、默认分支、merge/push 与 Release 发布是未在本地冒充完成的所有者动作。
**Files:** `README.md`, `frontend/DESIGN.md`, V5 screenshots/recording assets if generated
**Depends on:** T58
**Steps:** Update name to 溯知, V5 architecture, five-minute start, real screenshots/GIF and evaluator numbers; never fill placeholders with invented metrics.
**Verification:** README asset/link/version checks and anonymous repository visibility check are recorded.

## Execution Order

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6
   -> T7 -> T8 -> T9 -> T10 -> T11 -> T12 -> T13 -> T14 -> T15 -> T16
   -> T17 -> T18 -> T19 -> T20 -> T21 -> T22 -> T23 -> T24
   -> T25 -> T26 -> T27 -> T28 -> T29 -> T30 -> T31 -> T32
   -> T33 -> T34 -> T35 -> T36 -> T37 -> T38
   -> T39 -> T40 -> T41 -> T42 -> T43 -> T44 -> T45 -> T46 -> T47 -> T48
   -> T49 -> T50 -> T51
   -> T52 -> T53
   -> T54 -> T55 -> T56 -> T57 -> T58 -> T59
   -> T60 -> T61 -> T62 -> T63 -> T64 -> T65
```

## V5.1 Agent Closure Tasks

## T60: Add RED EvidenceIndex query tests ✅
**Files:** `backend/tests/test_v5_evidence_index_lifecycle.py`, `backend/app/modules/evidence_index/contracts.py`, `backend/app/modules/evidence_index/sql.py`
**Verification:** exact chunk and bounded same-revision neighbor tests fail before implementation, then pass.

## T61: Execute open and neighbor tools in AgentRunner ✅
**Files:** `backend/app/modules/evidence_agent/controller.py`, `search_adapter.py`, `wiring.py`, `recovery.py`, runtime tests
**Depends on:** T60
**Verification:** observable tool order is search → open → neighbors; cancellation and budget fences remain green.

## T62: Persist excluded/contextual Ledger relations ✅
**Files:** `controller.py`, model-runner tests
**Depends on:** T61
**Verification:** selected evidence becomes supports; unselected evidence becomes excluded with reason/method; neighbor evidence stays contextual unless selected.

## T63: Add versioned modify approval ✅
**Files:** contracts, state machine, service, schemas, API and human-loop tests
**Depends on:** T62
**Verification:** title modification rotates digest, invalidates old approval and preserves Run/Artifact identity.

## T64: Update frontend runtime and workspace ✅
**Files:** frontend contract/controller/recording adapter/presenter/RunWorkspace and tests
**Depends on:** T63
**Verification:** runtime validation accepts modify; UI explains relations in Chinese and shows exclusion reason.

## T65: Run acceptance and publish local commit ✅
**Depends on:** T64
**Verification:** focused tests, backend full suite, frontend lint/typecheck/unit/build and release checker pass from a clean commit.
