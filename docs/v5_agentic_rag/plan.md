# 溯知 V5 Evidence Agent Plan

## Architecture Overview

V5 采用两个高 depth module 和一组薄 Adapter：

1. `EvidenceIndex` 负责来源 revision、chunk、sparse/dense 索引、激活/退役、检索、证据解析和跨存储修复。
2. `EvidenceAgent` 负责命令幂等、运行状态机、计划、证据工具、Evidence Ledger、充分性判断、预算、人工交互、Artifact 和事件流。
3. FastAPI、RQ Worker、旧 Chat、前端 HTTP/SSE 和离线评测仅作为 Adapter，不拥有核心状态转换。

外部 Agent interface 固定为三个入口：

```python
class EvidenceAgent(Protocol):
    def submit(self, command: AgentCommand) -> CommandReceipt: ...
    def inspect(self, query: AgentQuery) -> QueryResult: ...
    def follow(self, run_id: RunId, after: Cursor | None = None) -> Iterator[RunUpdate]: ...
```

前端 Adapter 将它收敛成 `start / observe / act`，Workbench 不感知 RQ、Qdrant、SQLAlchemy Session、模型 Provider 或工作流节点。

系统不在本周期引入多 Agent，也不把 LangGraph 类型放入 interface。运行编排先使用项目内显式、可测试的持久状态机；未来如接入 LangGraph，只能作为 `EvidenceAgent` implementation 内部替换项。

### Runtime flow

```text
OpenRun
  -> pin active revisions
  -> route quick | agent
  -> persist RunAccepted + checkpoint
  -> enqueue

quick:
  search -> synthesize -> verify claims -> publish artifact

agent:
  plan required facts
  -> search/open/neighbors
  -> update Evidence Ledger
  -> assess sufficient | search_more | clarify | insufficient
  -> bounded loop
  -> synthesize claims
  -> claim-evidence verification
  -> repair or publish artifact

SignalRun:
  clarification | approval | reject | cancel | resume
  -> optimistic version check
  -> persist command/event/checkpoint
  -> enqueue when runnable
```

### Evidence indexing flow

```text
PreparedEvidence
  -> create staging revision/chunks/index record
  -> assign deterministic point ids and content hashes in SQL
  -> commit tracked staging state
  -> embed + upsert dense points + write sparse rows
  -> validate counts/fingerprint
  -> atomically activate new revision and retire old revision
  -> query immediately excludes retired revision
  -> best-effort old-point cleanup
  -> reconciler repairs interrupted cleanup and orphan/staging points
```

旧索引在新索引验证成功前不会删除。Qdrant 写入前 point id 已在数据库持久化，因此取消或进程崩溃不会再制造“数据库完全不知道”的向量。

## Core Data Structures and Interfaces

### Evidence identity

```python
@dataclass(frozen=True)
class EvidenceRef:
    source_id: int
    revision_id: int
    chunk_id: int
    content_hash: str
    locator: Locator

@dataclass(frozen=True)
class Locator:
    kind: Literal["page", "time", "code", "region", "text"]
    page_number: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    region: tuple[float, float, float, float] | None = None
```

Invariant：`revision_id + chunk_id + content_hash + locator` 在加入一个 run 后不可修改。`source.active_revision_id` 变化不会改变已有 run 已 pin 的 EvidenceRef。

### EvidenceIndex interface

```python
class EvidenceIndex(Protocol):
    def command(self, command: IndexCommand) -> IndexCommandReceipt: ...
    def query(self, query: IndexQuery) -> IndexProjection: ...
    def search(self, request: EvidenceSearch) -> EvidencePage: ...
```

`command()` 接受 `BuildRevision | ReindexRevision | CancelIndexOperation | ReconcileIndex`。它隐藏 staging、embedding、Qdrant、FTS、激活、退役、补偿和清理；调用方只提交来源、parser metadata 和标准化 `RevisionDraft`。调用方不能直接调用 activate。

`query()` 接受 `GetIndexOperation | ResolveEvidence | ReadNeighbors | GetReconcileReport`，返回不可变 projection，不暴露 ORM 或 Qdrant record。

`search()` 接收已 pin 的 revision/index 范围、query、source filters、top-k、threshold 和 neighbor window。实现执行：

- SQLite FTS5 sparse 召回；中文文本写入 CJK bigram 辅助 token。
- Qdrant dense 召回，并强制过滤 space/source/revision。
- Reciprocal Rank Fusion，避免混合不可比较的原始分数。
- 可选真实 HTTP rerank Adapter。
- 统一 threshold、去重、MMR/来源多样性和 context budget。

`ReconcileIndex` 比较 SQL point manifest、FTS row 与 Qdrant point，默认 dry-run；显式 apply 才修复缺失 payload、过期 point、孤儿 point、卡住 staging revision 和待清理 retired revision。

### Agent command interface

```python
AgentCommand = OpenRun | SignalRun

@dataclass(frozen=True)
class OpenRun:
    command_id: str
    goal: str
    space_id: int
    source_ids: tuple[int, ...]
    deliverable: DeliverableSpec
    effort: Literal["quick", "standard", "deep"]
    budget: RunBudget
    policy: ActionPolicy

@dataclass(frozen=True)
class SignalRun:
    command_id: str
    run_id: str
    expected_version: int
    signal: Clarify | Approve | Amend | Reject | Cancel | Resume
```

相同 `command_id` 重复提交返回原 receipt。`expected_version` 不匹配返回显式 conflict，不静默覆盖。

### Agent query interface

```python
AgentQuery = GetRun | ListRuns | InspectEvidence | GetArtifact | ListArtifacts
```

Query 读取 materialized projection，不重放完整事件日志。长事件通过 `follow()` 或分页 HTTP endpoint 获取。

### Run lifecycle

数据库 `AgentRun.phase` 与 `AgentRun.outcome` 分离：

```text
phase:
queued -> routing -> planning -> gathering -> assessing
       -> awaiting_input | awaiting_approval | paused
       -> synthesizing -> verifying -> ended

outcome when ended:
answered | insufficient_evidence | budget_exhausted |
cancelled | technical_failure
```

状态转换由一个纯 in-process reducer 验证。非法转换不会写入 projection 或事件。

### Evidence Ledger

```python
EvidenceLedger = {
  requirements: Requirement[],
  evidence: EvidenceRecord[],
  covered_requirement_ids: set[str],
  gaps: EvidenceGap[],
  contradictions: Contradiction[],
  excluded: ExcludedEvidence[],
  next_queries: str[]
}
```

Evidence relation 为 `supports | contradicts | contextual | excluded`。Evidence 只保存必要摘要与 immutable ref；完整内容由 `EvidenceIndex.resolve()` 按权限读取。

### AgentModel internal port

```python
class AgentModel(Protocol):
    def route(self, task: ResearchTask, inventory: SourceInventory) -> RouteDecision: ...
    def plan(self, task: ResearchTask, inventory: SourceInventory) -> ResearchPlan: ...
    def assess(self, task: ResearchTask, ledger: EvidenceLedger) -> SufficiencyDecision: ...
    def synthesize(self, task: ResearchTask, ledger: EvidenceLedger) -> ArtifactDraft: ...
```

Adapters：

- `StructuredLLMAgentModel`：包装现有 Real LLM Provider，要求 JSON/Pydantic 校验；格式错误仅允许一次明确 repair。
- `DeterministicAgentModel`：Demo、测试和 CI 使用，按固定规则生成可重复计划、决定和 claims，明确标记为 Demo。
- `RecordingAgentModel`：评测 fixture 可重放真实调用记录，不访问外部网络。

AgentModel 不执行工具，只返回受 schema 约束的计划、查询、充分性决定和草稿。Runtime 只执行注册表中允许的工具。

### Tool effects and approval

```python
ToolEffect = Literal["read", "write", "external_send", "execute"]
```

本周期生产工具仅包括只读的 `search_evidence`、`open_evidence`、`read_neighbors` 和 `list_sources`。Runtime 同时实现通用 effect guard，并使用受保护 fake tool 验证：

- `read` 在 scope 内自动执行。
- 其他 effect 生成 `awaiting_approval` interaction。
- Approval 绑定 tool id、版本、参数 digest、effect 和单次 invocation。
- 参数或工具版本变化后旧 approval 失效。
- 来源文本永远不能创建或批准 interaction。

### Budget and stop rules

`RunBudget` 固定 `max_steps`、`max_tool_calls`、`max_model_tokens`、`max_wall_seconds`、`max_cost`。每个 Provider/Tool 前后都检查取消与预算。

停止条件：

- Evidence requirements 已覆盖且 verifier 通过。
- 达到任一硬预算。
- 连续两轮没有新增 immutable EvidenceRef。
- 没有可执行 next query。
- 用户拒绝必要动作且不存在只读替代路径。
- 用户取消。

预算耗尽与证据不足是正常 outcome；技术依赖失败才是 `technical_failure`。

### Event and cursor contract

`AgentEvent` 使用每个 run 单调递增的 sequence，数据库唯一约束 `(run_id, sequence)`。

主要事件：

```text
RunAccepted, ModeSelected, PlanProposed, StepStarted, StepCompleted,
ToolRequested, ToolCompleted, EvidenceAdded, EvidenceExcluded,
CoverageChanged, ContradictionDetected, InteractionRequired,
InteractionResolved, BudgetChanged, ArtifactPublished,
RunCancelled, RunEnded, TechnicalFailureRecorded
```

`follow()` 无 cursor 时先返回 snapshot，再返回增量；有 cursor 时只返回后续事件。HTTP SSE 使用 `id:` 写 cursor，并发送 heartbeat。事件采用 at-least-once 投递，前端按 `event_id` 去重；cursor 已压缩时返回 `reset snapshot`。

事件不保存隐藏 chain-of-thought，只保存计划、操作摘要、证据引用、结构化决定、预算与错误。

## Module Design

### EvidenceIndex module

**Responsibility:** 统一所有文档、媒体和代码来源的 revision-safe 索引生命周期与证据检索。

**Public interface:** `command / query / search`。

**Dependencies:** SQLAlchemy Session factory、Embedding port、VectorStore Adapter、Rerank port、clock、cancellation probe。SQL/FTS/Qdrant 是 implementation 内部 seam。

Implementation 要点：

- 新文档上传时同时创建 `Source(document_id=...)`。
- 文档、媒体和代码 parser 均转换成 `RevisionDraft`，不再自行激活 revision。
- point id 使用 UUIDv5，由 index_revision/chunk/embedding fingerprint 决定。
- `VectorPointManifest` 在任何外部 upsert 前保存预期 point id 与 payload digest。
- `OutboxMessage` 在同一 SQL 事务记录下一步；RQ 仅提供 at-least-once 执行，所有 effect 以 dedupe key 幂等。
- `MultimodalChunk.content_hash` 独立保存 SHA-256。
- active revision/index 通过 Source 指针和数据库 partial unique index 双重约束。
- FTS row key 与 EvidenceRef 一一对应。
- Legacy `Chunk` 继续作为兼容投影，但新 Agent 只消费 canonical multimodal evidence。
- 文档删除默认 retire/soft-delete；已有 Agent provenance 时不得直接物理 purge。

### EvidenceAgent module

**Responsibility:** 持久运行、命令/查询/事件 interface、状态机、Agent 循环、预算、审批、Artifact 与 provenance。

**Public interface:** `submit / inspect / follow`。

**Dependencies:** Session factory、EvidenceIndex、AgentModel、TaskBroker、clock、id generator。运行时内部 reducer、planner policies、ledger、verifier 不暴露 seam。

Implementation 要点：

- `submit(OpenRun)` 在一个事务中 pin revisions、写 command/run/event/checkpoint，再 enqueue。
- Queue 不可用时 command 仍有可恢复状态；dispatcher 可重新投递未 dispatch run。
- 每个 RQ job 只执行一个有界 slice；每个 step 后提交 checkpoint/event/outbox，再投递下一 slice。Worker 重试从安全 checkpoint 继续。
- 同一步工具调用使用 invocation digest 幂等。
- 取消后 in-flight Provider 返回值被丢弃，且不会再持久化新 step/evidence/artifact。
- 简单 quick mode 不创建 planning step。

### AgentModel adapters

**Responsibility:** 将 Provider 文本输出转换成受验证的 route/plan/assessment/artifact domain objects。

**Public interface:** `AgentModel` 内部 port。

**Dependencies:** 现有 `LLMService`/provider、Pydantic schemas、recording store。

### TaskBroker adapter

**Responsibility:** 在现有 RQ 中投递 Agent Run，并支持排队取消和恢复扫描。

**Public interface:** 扩展现有 TaskBroker 为通用 `publish(TaskEnvelope)`，保留旧 enqueue 方法作为兼容 Adapter；RedisRQ 与 deterministic inline 是两个实际 Adapter。

**Dependencies:** Redis/RQ；测试使用 inline adapter。

### HTTP/SSE adapter

**Responsibility:** 将 FastAPI request 映射为 command/query，将 `follow()` 映射为 SSE，不包含状态机逻辑。

**Public interface:**

```text
POST /api/v1/evidence-runs
GET  /api/v1/evidence-runs
GET  /api/v1/evidence-runs/{id}
POST /api/v1/evidence-runs/{id}/commands
GET  /api/v1/evidence-runs/{id}/events
GET  /api/v1/evidence-runs/{id}/stream
GET  /api/v1/evidence-runs/{id}/evidence
GET  /api/v1/artifacts
GET  /api/v1/artifacts/{id}
POST /api/v1/evidence-index/reconcile
```

### Workbench frontend module

**Responsibility:** 提交目标、观察 RunView、处理唯一 attention、展示 Evidence Ledger/Artifact，并支持引用定位。

**Public interface:** `frontend/modules/evidence-agent` 导出 `start / inspect / observe / act` 和 `useEvidenceRun`；生产 HTTP/SSE 与 recording/in-memory 是两个 Adapter。

**Dependencies:** HTTP/SSE Adapter、runtime contract parser、Next Router。

React 页面只消费 `RunView`，不拼装 domain state。`RunController` 负责 cursor、重连、event 去重、snapshot reset、取消和命令幂等，并通过 `useSyncExternalStore` 向页面发布窄投影。

### Evaluation module

**Responsibility:** 运行真实 pipeline，输出 baseline/retrieval/agent 对照、失败案例和环境标签。

**Public interface:** `scripts/evaluate_agentic_rag.py --mode demo|real --dataset ... --output ...`。

**Dependencies:** 同一个 EvidenceIndex/EvidenceAgent interface；Demo 使用 deterministic adapters，Real 必须验证 Provider readiness。

## Module Interactions

### Create and execute run

1. Workbench `start()` POST OpenRun。
2. Route Adapter 调用 `EvidenceAgent.submit()`。
3. Agent 在事务内 pin active revisions、保存 AgentCommand/AgentRun/AgentEvent。
4. TaskBroker 投递 RQ；失败保留 `dispatch_pending`，后台 dispatcher 可补投。
5. Worker 通过 factory 构造同一 EvidenceAgent implementation，执行 checkpoint。
6. Runtime 调 AgentModel 和只读 evidence tools。
7. EvidenceIndex 返回 immutable refs；Runtime 更新 Ledger 和事件。
8. Runtime 发布 Artifact/Claims/ClaimEvidence 并终止 Run。
9. SSE Adapter 将有序增量发送给 Workbench。

### Clarification or approval

1. Runtime 写 InteractionRequired、checkpoint 和 `awaiting_*` phase 后退出 Worker。
2. Workbench attention drawer 提交 SignalRun。
3. Agent 验证 command id、run version、interaction id 与 proposal digest。
4. 合法决定持久化后重新入队；重复命令返回原 receipt。

### Revision replacement

1. Ingestion Adapter 解析新内容为 PreparedEvidence。
2. EvidenceIndex 写 tracked staging rows 与 deterministic point ids。
3. 外部索引成功后验证并激活新 revision。
4. 事务内更新 Source.active_revision_id，旧 revision/chunks/index 标记 retired。
5. 所有新 query 只使用新 revision；旧 point 延迟清理不影响查询正确性。
6. Reconciler 最终清理和报告不一致。

### Legacy compatibility

- `/chat` 保持旧响应契约；内部可走 quick run Adapter，迁移期允许原 RAGService fallback。
- 旧页面继续可直接访问，但从主导航移除。
- 迁移为 Document 建 canonical Source/Revision/MultimodalChunk；Legacy Chunk 作为兼容投影继续供旧详情页读取。
- V4.9 Qdrant payload 由 post-upgrade reconciler 补充 source/revision/content_hash；无法修复时标记 reindex required，不伪装 ready。

## File Organization

### Backend create

```text
backend/app/models/outbox.py
backend/app/models/evidence_index.py
backend/app/models/agent_run.py
backend/app/models/agent_evidence.py
backend/app/models/agent_event.py
backend/app/modules/evidence_index/__init__.py
backend/app/modules/evidence_index/contracts.py
backend/app/modules/evidence_index/service.py
backend/app/modules/evidence_index/sql_store.py
backend/app/modules/evidence_index/sparse_adapter.py
backend/app/modules/evidence_index/reconciler.py
backend/app/modules/evidence_index/wiring.py
backend/app/modules/evidence_agent/__init__.py
backend/app/modules/evidence_agent/contracts.py
backend/app/modules/evidence_agent/service.py
backend/app/modules/evidence_agent/state_machine.py
backend/app/modules/evidence_agent/controller.py
backend/app/modules/evidence_agent/budget.py
backend/app/modules/evidence_agent/tools.py
backend/app/modules/evidence_agent/sql_store.py
backend/app/modules/evidence_agent/wiring.py
backend/app/services/agent_model.py
backend/app/services/outbox_dispatcher.py
backend/app/schemas/agent_schema.py
backend/app/schemas/evidence_schema.py
backend/app/api/routes_agent_runs.py
backend/app/api/routes_evidence.py
backend/app/tasks/agent_tasks.py
backend/app/tasks/evidence_index_tasks.py
backend/alembic/versions/0007_v5_evidence_index.py
backend/alembic/versions/0008_v5_agent_runtime.py

backend/tests/test_v5_evidence_index_lifecycle.py
backend/tests/test_v5_index_saga.py
backend/tests/test_v5_index_reconciler.py
backend/tests/test_v5_active_retrieval.py
backend/tests/test_v5_agent_models.py
backend/tests/test_v5_agent_runtime.py
backend/tests/test_v5_agent_human_loop.py
backend/tests/test_v5_agent_worker_recovery.py
backend/tests/test_v5_agent_sse.py
backend/tests/test_v5_agent_api.py
backend/tests/test_v5_agent_security.py
backend/tests/test_v5_migrations.py
```

### Backend modify

```text
backend/app/models/source.py
backend/app/models/__init__.py
backend/app/models/document.py
backend/app/db/session.py
backend/app/services/ingestion_service.py
backend/app/services/media_service.py
backend/app/services/code_repository_service.py
backend/app/services/media_task_service.py
backend/app/services/hybrid_retriever.py
backend/app/services/vector_store.py
backend/app/services/rerank_provider.py
backend/app/services/providers.py
backend/app/services/llm_service.py
backend/app/services/task_broker.py
backend/app/tasks/ingestion_tasks.py
backend/app/worker.py
backend/app/api/router.py
backend/app/core/config.py
backend/tests/conftest.py
backend/requirements.txt
```

### Frontend create

```text
frontend/modules/evidence-agent/contract.ts
frontend/modules/evidence-agent/evidence-agent.ts
frontend/modules/evidence-agent/http-sse-adapter.ts
frontend/modules/evidence-agent/recording-adapter.ts
frontend/modules/evidence-agent/run-controller.ts
frontend/modules/evidence-agent/research-catalog.ts
frontend/modules/evidence-agent/source-locator.ts
frontend/modules/evidence-agent/contract.test.ts
frontend/modules/evidence-agent/run-controller.test.ts
frontend/app/workbench/page.tsx
frontend/app/runs/page.tsx
frontend/app/runs/[id]/page.tsx
frontend/app/library/page.tsx
frontend/app/library/sources/[id]/page.tsx
frontend/app/artifacts/page.tsx
frontend/app/artifacts/[id]/page.tsx
frontend/components/workbench/Workbench.tsx
frontend/components/workbench/Workbench.module.css
frontend/components/runs/RunWorkspace.tsx
frontend/components/runs/PlanTimeline.tsx
frontend/components/runs/EvidenceLedger.tsx
frontend/components/runs/HumanDecisionPanel.tsx
frontend/components/runs/BudgetMeter.tsx
frontend/components/runs/RunWorkspace.module.css
frontend/components/evidence/EvidenceInspector.tsx
frontend/components/evidence/EvidenceInspector.module.css
frontend/components/artifacts/ArtifactDocument.tsx
frontend/components/artifacts/ArtifactDocument.module.css
frontend/components/library/LibraryWorkspace.tsx
frontend/components/ui/Dialog.tsx
frontend/components/ui/StatusAnnouncer.tsx
frontend/eslint.config.mjs
frontend/e2e/agent-golden-flow.spec.ts
frontend/e2e/agent-citation-locators.spec.ts
frontend/e2e/agent-resume-cancel.spec.ts
```

### Frontend modify

```text
frontend/app/page.tsx
frontend/app/layout.tsx
frontend/app/globals.css
frontend/components/AppShell.tsx
frontend/components/KnowledgeChat.tsx
frontend/components/CitationPanel.tsx
frontend/components/DocumentUploader.tsx
frontend/components/ui.tsx
frontend/services/api.ts
frontend/types/api.ts
frontend/package.json
frontend/package-lock.json
frontend/next.config.ts
frontend/playwright.config.ts
frontend/DESIGN.md
```

### Evaluation, CI and docs

```text
evaluation/v5/cases.jsonl
evaluation/v5/corpus/*
scripts/evaluate_agentic_rag.py
scripts/check_v5_acceptance.py
scripts/migrate_v5_evidence_data.py
scripts/verify_v5_migration.py
scripts/reconcile_evidence_index.py
.github/workflows/ci.yml
README.md
docs/v5_agentic_rag/engineering_log.md
docs/v5_agentic_rag/acceptance_report.md
```

## Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Product architecture | One evidence research Agent with quick/agent modes | Preserves focus and makes improvement measurable; multi Agent is out of scope. |
| Core Agent interface | `submit / inspect / follow` closed unions | Three entry points cover lifecycle, queries and streaming without endpoint proliferation. |
| Frontend interface | `start / observe / act` Adapter | Makes default Workbench path trivial while domain semantics stay centralized. |
| Runtime | Explicit persistent state machine | Avoids framework leakage and permits deterministic tests; LangGraph may replace implementation later. |
| Persistence | Current projection plus append-only journal | Gives audit/recovery without committing to full event-sourcing complexity. |
| Queue consistency | Transactional outbox, deterministic job ids and bounded RQ slices | Queue outage/replay is recoverable; at-least-once delivery cannot duplicate domain effects. |
| SQLite runtime | Foreign keys ON, WAL and busy timeout | Required before concurrent Agent/worker/SSE access; avoids silent dangling references and common lock failures. |
| Evidence canonical model | Source + SourceRevision + MultimodalChunk for every source type | Enables one invariant across document/media/code; legacy Chunk becomes compatibility projection. |
| Vector lifecycle | Deterministic ids, tracked staging, activate-before-retire, reconciler | Removes orphan and delete-before-rebuild failure windows. |
| Sparse retrieval | SQLite FTS5 with normalized CJK bigrams | Full active corpus retrieval without adding another external service. |
| Fusion | RRF followed by optional rerank | Rank fusion is stable across incomparable dense/sparse score scales. |
| Rerank | Configurable HTTP Adapter + recording fake | Provides a real production seam without forcing model download in CI. |
| Context packing | token budget + de-duplication + source diversity + neighbor windows | Prevents oversized code/media chunks and improves evidence coverage. |
| Agent tool control | Model proposes structured intent; runtime executes allowlisted tools | Prevents retrieved instructions from becoming executable authority. |
| Approval | Exact invocation digest, single use | Stops approval replay and parameter substitution. |
| Cancellation | pre/post external-call checks and discard after cancellation | In-flight synchronous Provider may finish, but no later state/evidence/artifact is committed. |
| Provider output | Pydantic structured objects with one repair attempt | Converts free text into explicit, testable decisions without hiding repeated failures. |
| API contracts | Pydantic OpenAPI plus frontend runtime validation | Detects payload drift at Adapter seam instead of deep in React pages. |
| Streaming | SSE with cursor, snapshot reset and at-least-once de-duplication | Fits one-way run observation and supports reconnect without WebSocket complexity. |
| UI IA | Workbench / Library / Agent Runs / Artifacts + collapsed Developer Mode | Centers the evidence workflow and removes self-referential feature sprawl. |
| Evaluation | 60+ fixed cases, demo/real labels, baseline ablations | Produces reproducible resume evidence and prevents seeded checks being called quality evaluation. |
| Testing | Vertical TDD through EvidenceIndex, EvidenceAgent and HTTP/SSE seams | Tests observable behavior and survive internal refactors. |

## Requirement Coverage

| Requirements | Architectural home |
|---|---|
| F1 | EvidenceIndex canonical revision lifecycle and active constraints |
| F2 | EvidenceIndex tracked staging saga, compensation and reconciler |
| F3 | FTS/Qdrant retrieval, RRF, rerank and context packing |
| F4 | EvidenceAgent OpenRun and persistent Run projection |
| F5 | Mode router and quick/agent execution policies |
| F6 | Plan projection and allowlisted evidence tools |
| F7 | Persistent Evidence Ledger and relation model |
| F8 | Structured sufficiency decision and clarification path |
| F9 | Budget reducer, no-new-evidence stop and terminal outcomes |
| F10 | EvidenceRef, AgentClaim, ClaimEvidence, Artifact verifier |
| F11 | SignalRun, Interaction, checkpoint, cancellation and resume |
| F12 | Append-only journal, cursor contract and follow/SSE Adapter |
| F13 | Workbench frontend module and RunView projection |
| F14 | Four-zone AppShell and collapsed Developer Mode |
| F15 | Artifact/Claim/ClaimEvidence and source detail backlinks |
| F16 | Evaluation module using the same public interfaces |
| F17 | Tool effect guard, exact approval digest, prompt-injection fixtures |
| N1–N4 | 0007 migration, compatibility Adapter, deterministic/recording adapters |
| N5–N6 | AgentEvent, budget usage, separate quick/agent metrics |
| N7–N8 | accessible Workbench and runtime contract parser |
| N9–N10 | deep module interfaces and normal insufficient_evidence outcome |
| N11 | evaluation-backed README and acceptance report |

## V5.1 Agent Closure Plan

### Architecture Overview

在现有单 slice Runner 中加入一个可选的 `EvidenceQueryPort`。生产 wiring 使用 SQL EvidenceIndex query adapter；旧测试和 recording adapter 可不注入该端口，保持兼容。检索完成后，Runner 为每个 requirement 的首条搜索证据依次执行 `open_evidence` 和 `read_neighbors`，每次只执行一个外部只读调用。

### Core Interfaces

- EvidenceIndex 新增 `GetEvidenceChunk` 与 `GetEvidenceNeighbors` query；返回 immutable `PinnedEvidenceRef`，并校验 revision/chunk 归属及最大窗口。
- AgentRunner 新增可选 `evidence_query` port；工具调用沿用 AgentToolCall、预算、version/epoch fence、journal 与 outbox。
- `RequirementEvidence` 使用现有 relation 字段增加 `contextual` 与 `excluded` 语义，不新增数据库列。
- `modify` Signal 只接受 `{title}`，原 proposal 标记 superseded，并基于 Artifact 内容摘要创建新 ToolCall、Gate 与 proposal digest。

### Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Neighbor scope | 同 revision、中心 chunk 前后各最多 3 条 | 保持 pinned scope，限制上下文膨胀 |
| Tool scheduling | 每个 Runner slice 一个工具调用 | 保持 checkpoint、取消 fence 与恢复语义 |
| Context relation | `contextual`，被模型显式选择后才转 `supports` | 读取不等于事实支持 |
| Exclusion | answer decision 后未选择 candidate/contextual 转 `excluded` | 让 Ledger 说明为什么没引用 |
| Modify scope | 仅修改 draft Artifact 标题 | 避免未校验正文或 claim 被人工静默改写 |
| Proposal integrity | Artifact 内容摘要进入 publish arguments | 修改后旧 digest 自动失效 |
