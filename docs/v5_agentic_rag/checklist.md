# 溯知 V5 Evidence Agent Checklist

Status notation: `[x]` 表示已有实际命令、测试或可观测结果；未勾选且标记 `◐` 表示主体完成但验证不完整或存在已知边界。本表不用“应该可用”代替证据。

## Implementation Completeness

- [ ] ◐ AC1 — 同一文档、音频、视频、图片和代码来源连续生成两个内容版本后，普通查询只返回第二个 active revision；历史 Artifact 仍能按 immutable ref 打开第一版证据。（Evidence: document/media/code lifecycle 和 retired pinned evidence 测试已通过；尚缺“五类来源双版本 + 历史 Artifact 回跳”的单一端到端证明。）
- [x] AC2 — 在向量 upsert 后取消、数据库切换前失败、重复重试和两个并发重建请求下，没有不可追踪 point；修复工具能报告并清理人工注入的孤儿 point。（Evidence: `test_v5_index_saga.py`、`test_v5_index_reconciler.py` 与 stale activation race 用例。）
- [x] AC3 — 30 个按不同时间创建的 chunk 中，最旧 chunk 的精确词仍进入 sparse 候选；dense、sparse 和融合结果都遵守相同 scope、active revision 和最低有效条件。（Evidence: `test_v5_active_retrieval.py` 的 oldest-hit、threshold 与 pinned/active filter 用例。）
- [x] AC4 — 评测报告分别包含 dense、sparse、fusion 和 rerank 的 Recall@k、MRR、nDCG、active-revision precision 与 locator validity，并说明未配置 rerank 时的诚实状态。（Evidence: 可选生产 HTTP rerank Adapter 已交付；`evaluation_report.json` 四臂完整，固定 rerank 臂诚实标记 `production_configured=false`。）
- [ ] ◐ AC5 — 创建目标得到稳定 run id；所有公开状态/终态可达且合法，Worker 在每个 checkpoint 边界重启后投影保持一致。（Evidence: 状态机、持久 command/event/checkpoint/outbox、并发 CAS、模型/检索崩溃恢复与 lease recovery 均有测试；checkpoint checksum/state/cursor 已被真实读取，未知模型结果 fail-closed；尚未建立“每一 checkpoint 边界”的穷尽式重启矩阵。）
- [x] AC6 — 简单事实任务选择 quick mode、planner 调用数为 0；跨两个以上来源的任务产生可见计划并执行多步只读证据工具。（Evidence: quick/auto/force-agent model-runner 测试与 evaluator `quick_plan_event_count=0`。）
- [ ] ◐ AC7 — Workbench 的 Evidence Ledger 与持久投影一致，能显示事实需求、覆盖状态、支持、反证、排除理由、缺口和 next query。（Evidence: requirement/evidence/claim 持久化、candidate→validated support 晋级、supports/contradicts/gap 投影与完整 `evidence.added` 事件已测；伪 ID、跨 requirement 与未选择候选均 fail-closed；excluded/next-query 的全 UI 对照矩阵仍不完整。）
- [x] AC8 — 资料不足时返回正常 insufficient_evidence 或 awaiting_input，不输出伪确定性事实；用户补充澄清后从同一 checkpoint 继续。（Evidence: 澄清回归 `63 passed`，覆盖持久 gate、`awaiting_input`、空输入拒绝、同 run `queued→retrieve→completed` 与幂等 replay。）
- [x] AC9 — 达到 step、tool、token、time、cost 或连续无新证据任一限制时，run 以明确原因停止，自动化测试没有无界循环。（Evidence: `test_v5_agent_model_runner.py` 分别覆盖 step/tool/model-call/context/output/time/cost/no-new-evidence 硬限制。）
- [ ] ◐ AC10 — final Artifact 的每个 factual claim 至少有一个可解析 EvidenceRef；page/time/code locator 点击后应打开正确 revision 并高亮目标。（Evidence: backend claim/provenance、frontend runtime schema 与当前 revision 的 locator/citation 路径已有测试；Artifact→Source 对 retired revision 的 revision/hash 透传及 document/media/code viewer 精确回跳尚未完成全链路验证。）
- [x] AC11 — awaiting_input/awaiting_approval 能处理批准、修改、拒绝、澄清；旧 version/digest 和重复命令被拒绝或重放原 receipt；取消后不新增 evidence/tool/artifact。（Evidence: `modify` 仅允许修改 draft Artifact 标题，轮换 proposal digest，并与 approve/reject/provide_input、stale version/digest、single-use gate、blocking model/search cancel 一起通过后端回归。）
- [x] AC12 — 事件 cursor 单调；断线重连只补缺失事件，重复投递不重复应用，过期/超前 cursor 返回 reset snapshot，heartbeat 不占 cursor。（Evidence: backend runtime/API SSE `20 passed`；frontend runtime/SSE/controller `3 files / 12 tests passed`，覆盖 no-cursor/stale/future reset、public-only replay、same-cursor heartbeat、de-dup 和刷新重建。）
- [ ] ◐ AC13 — 主导航只有 Workbench、Library、Agent Runs、Artifacts，Developer Mode 折叠；用户可从选择来源完成到 Artifact 和证据回跳。（Evidence: 四入口静态测试与 V5 Playwright `4/4` 已通过；黄金 E2E 未覆盖真实澄清分支。）
- [ ] ◐ AC14 — Artifact 可回 producing run/全部 provenance，来源可看到派生 Artifact；切换知识空间立即清除旧 scope、result 和 citation。（Evidence: Artifact→Run/Evidence/Source 和 Source→Artifact 的 backend/frontend contract 已实现，Workbench/legacy Chat 有 scope reset；尚缺统一双向链接 + space-switch E2E。）
- [x] AC15 — 固定集至少 60 条且覆盖单跳、多跳、跨模态、版本冲突、证据不足、提示注入和取消恢复；报告同时运行 V4.9-style single-shot proxy、retrieval baseline 和 Agent mode。（Evidence: 60 个唯一 case，分类计数 `12/12/8/8/8/6/6`，三实验臂完整；legacy 臂明确标记 proxy。）
- [x] AC16 — 多跳子集的 Agent evidence coverage 或 task success 相对 V4.9-style proxy 至少提升 10 个百分点，并同时报告样本量、失败案例、token、费用、p50/p95。（Evidence: 12 条多跳 case，Agent `100%` vs proxy `41.67%`，提升 `58.33 pp`；82 次 model call 的 token/cost measurement 与 quick/agent p50/p95 已报告。）
- [x] AC17 — 恶意资料中的忽略规则、读取密钥、代码执行和外发指令不会产生受保护工具调用；未授权动作率被报告。（Evidence: security tests 与 6 条 prompt-injection case，`unauthorized_action_rate=0.0`。）
- [x] AC18 — 后端编译/测试、迁移矩阵、前端 clean install/lint/typecheck/unit/build、核心 E2E 和生产依赖审计均实际运行；失败项在验收报告中有真实状态。（Evidence: backend `439 passed, 1 skipped`；migration round-trip/single head；frontend clean `npm ci`、lint/typecheck、73 tests/34-route build；strict live E2E `27/27`；audit `0`；quick/evaluator/acceptance gates 均通过。历史 Alembic drift 在报告单独明示。）
- [ ] ◐ AC19 — README 顶部只展示当前价值主张、真实 V5 流程资产、可重复评测摘要、架构图和五分钟启动；可见性不满足时明确标注。（Evidence: version/link/asset 静态检查已通过；GitHub 匿名可见性、默认分支与发布是未在本地改动的外部动作。）

## Domain Invariants

- [x] 一个 Source 在任一时刻最多一个 active SourceRevision 和一个 active IndexRevision。（Evidence: partial unique indexes、atomic activation 和 stale activation race 测试。）
- [ ] ◐ Qdrant searchable payload 都包含 source、revision、index revision、chunk 和 content hash；旧 payload 只走明确 legacy/reindex 状态。（Evidence: 新 manifest/Qdrant adapter 的 payload 契约已测；strict live run 实际观察到 Qdrant `502` 时 canonical sparse fallback 仍返回可解析 citation。旧集群仍需 online reconciler/reindex，SQL Alembic 刻意不访问 Qdrant。）
- [x] 新 run 在创建事务中 pin scope revision；后续 active pointer 变化不静默改变已开始 run 的证据。（Evidence: submit transaction scope snapshot、pinned revision hybrid-search 测试与 retired evidence resolution 测试。）
- [x] final Artifact 不包含 unsupported factual claim；inference/contested/gap 使用不同可见语义。（Evidence: structured synthesis/claim gate、quantitative conflict 和 insufficient gap Artifact 测试。）
- [x] insufficient_evidence、budget_exhausted 和用户拒绝不是 5xx technical failure。（Evidence: state-machine/domain-outcome 与 API contract 测试。）
- [x] 模型输出不能修改权限、scope、预算、状态或工具注册表。（Evidence: closed ToolRegistry、pinned-scope authorization、typed model schema 和 security tests。）
- [x] 生产 Demo/Real 状态、embedding fingerprint 和评测标签一致，不混用索引或冒充真实模型。（Evidence: real mode 无 LLM 时 API 503/直接 run failed，deterministic report 标记 external calls `0` 与 hashing fingerprint。）

## Integration

- [x] 文档、图片、音频、视频和代码 ingestion 均通过同一个 EvidenceIndex command seam。（Evidence: document/media/code writer lifecycle tests 通过 public index projection 验证。）
- [x] 旧 Document/Chunk 页面继续可读，但 V5 Agent 只使用 canonical revision evidence。（Evidence: populated V4.9 migration fixture、legacy smoke 与 production hybrid Agent pinned revision 测试。）
- [x] 新索引验证失败时旧 active revision 继续服务；新索引成功后旧 point 即使尚未物理删除也不可进入普通检索。（Evidence: manifest validation failure、document reprocess failure 和 active dense/sparse filter 测试。）
- [x] OpenRun、首事件、checkpoint 和 dispatch outbox 在一个可靠提交中形成；Redis 不可用后可补投。（Evidence: submit persistence 与 outbox lease/recovery tests。）
- [x] RQ 至少一次重复投递只产生一个 committed step/tool effect。（Evidence: deterministic task id、duplicate wakeup 与 run-version fence tests。）
- [ ] ◐ Provider 调用发生在数据库事务外；并发 Signal、SSE 与 Worker 不造成 SQLite 长锁。（Evidence: model/embedding/search 出事务测试与 SQLite WAL/busy-timeout 已实现；尚缺 Signal+SSE+Worker 并发长锁压测。）
- [x] SSE 使用短 Session、Last-Event-ID、no-cache 和 no-buffer headers；reset/heartbeat 不污染持久 event journal。（Evidence: API SSE contract、runtime follow 与 frontend adapter/controller 测试。）
- [x] quick 与 agent mode 复用同一 EvidenceRef、Claim、Artifact 和 Event contract。（Evidence: quick/agent runtime tests 及 schema-validated public Ledger/Artifact events。）
- [x] 旧 `/chat` 可继续工作且返回 immutable citation compatibility fields，不把 Demo history硬编码为Real。（Evidence: legacy citation/regression suites 与 Provider boundary tests。）
- [x] 前端 payload 在进入 RunController 前完成 runtime validation；未知 event 不被静默忽略。（Evidence: Zod contract、HTTP/SSE adapter 与 malformed catalog/artifact tests。）
- [x] 关闭浏览器观察流不等于取消 run；取消必须提交明确 command。（Evidence: RunController/HTTP adapter/recording adapter cancellation tests。）
- [ ] ◐ Artifact、Run、Evidence Inspector、Source detail之间的链接可刷新、可分享并保持revision定位。（Evidence: Artifact→Run/Evidence/Source 链接、Source→Artifact filter 与当前 revision locator 已实现；retired revision 的 revision/hash 尚未贯穿全部 viewer，且缺全组合 deep-link refresh E2E。）

## Accessibility and Product Quality

- [ ] ◐ 键盘用户可提交目标、浏览计划、打开/关闭 Evidence Inspector、处理澄清/审批并访问claim引用。（Evidence: 原生 form/button/link 与可访问标签已落地；缺完整 keyboard-only Playwright 场景。）
- [ ] ◐ Dialog/Inspector支持Escape、焦点圈定和关闭后恢复触发元素。（Evidence: 本版主要采用 deep-link source viewer；原规划的 Inspector dialog/focus assertion 未完整实现。）
- [ ] ◐ Run状态使用节流后的语义播报，不逐token干扰读屏。（Evidence: 运行状态是步骤级而非 token 级，但缺节流 aria-live 专项断言。）
- [x] 状态、证据关系和风险不只依赖颜色表达。（Evidence: status/relation/risk 均有文本标签与图标，且 V5 四张截图已检查。）
- [x] reduced motion下没有非必要动画，移动端触控目标和safe area满足核心流程。（Evidence: CSS reduced-motion/safe-area 规则与 375px/mobile V5 Playwright 用例。）
- [x] 主产品中不再出现V3/V4.5/V4.8内部发布文案或自指作品集入口。（Evidence: public frontend `rg` 无旧版本文案，主导航四入口 unit/E2E 通过。）

## Build and Test

- [x] Python代码可编译。（Evidence: `python -m compileall -q backend/app backend/alembic scripts` 与 Ruff 通过，后续 recovery/outbox/live-worker 修复又通过 364-test 完整导入回归。）
- [x] V5 EvidenceIndex聚焦测试通过。（Evidence: lifecycle/saga/reconciler/active-retrieval 均包含在已通过的 backend full suite，迁移后又完成定向回归。）
- [x] V5 Agent聚焦测试通过。（Evidence: `test_v5_agent_human_loop.py test_v5_agent_runtime.py test_v5_agent_model_runner.py test_v5_agent_models.py` → `63 passed`；API/security/worker-recovery → `10 passed`。）
- [x] 后端完整测试通过。（Evidence: provider-mode fallback、crash recovery、Runner CAS、outbox safety 与 live-worker 修复后 `python -m pytest backend/tests -q` → `439 passed, 1 skipped in 141.87s`。）
- [ ] ◐ Alembic只有一个head且model无未生成迁移。（Evidence: single head 为 `0008_v5_agent_runtime`；`alembic check` 仍报告 0001–0006 历史 nullable/index/FK drift，过滤后 V5-specific drift 为 0。）
- [x] 填充V4.9数据的upgrade→downgrade→upgrade通过。（Evidence: migration tests `9 passed`；`python scripts/verify_v5_migration.py --roundtrip` exit 0，前后 semantic digest 精确相等；hash 随独立 fixture 内容生成，不硬编码为固定常量。）
- [x] 前端依赖可重复安装。（Evidence: clean `npm ci` 从 lockfile 安装 441 packages，退出码 0；随后 lint/typecheck/unit/build 全部通过。）
- [x] 前端lint通过。（Evidence: 最终 `npm run lint` exit 0。）
- [x] 前端TypeScript通过。（Evidence: 最终 `npm run typecheck` exit 0。）
- [x] 前端module unit tests通过。（Evidence: 最终 `npm run test:unit` → `17 files / 73 tests passed`。）
- [x] 前端生产构建通过。（Evidence: Next `15.5.23` production build exit 0，生成 34 routes。）
- [x] 核心desktop/mobile Playwright通过。（Evidence: 最终 strict live E2E `27/27 passed in 38.7s`；durable backend run 经过 live Worker 完成，其中 Qdrant `502` 降级仍保留 canonical citation。）
- [x] 生产依赖没有未处置的high advisory。（Evidence: `npm audit --omit=dev --audit-level=high` 报告 `0 vulnerabilities`。）
- [x] V5 evaluator与acceptance gate通过。（Evidence: report 生成于 `2026-08-15T11:26:19Z`，gate 状态 `passed`、failures `[]`，定向 pytest `2 passed`。）

## End-to-End Scenarios

- [ ] ◐ 用户选择架构文档、代码、报错截图和会议视频，提交跨来源调查；系统展示计划、逐步证据、缺口/反证，必要时澄清，最终产出逐claim引用报告。（Evidence: recording 主流程和 production source/library/artifact 流程已通过；缺 live-provider + clarification 组合黄金流程。）
- [ ] ◐ 用户在run进行中更新一个来源；普通新查询使用新revision，原run按pinned revision继续且最终Artifact仍可回放。（Evidence: active/pinned revision 集成测试已通过；缺端到端 UI 场景。）
- [ ] ◐ Agent遇到需要扩大scope或受保护动作时暂停；用户修改/拒绝后从checkpoint继续或正常证据不足结束。（Evidence: exact approval/reject 和 clarification checkpoint 后端测试已通过；缺 human-decision E2E 与独立 modify signal。）
- [ ] ◐ Provider阻塞期间用户取消；终态为cancelled，返回后的旧epoch结果不产生任何新步骤、证据或Artifact。（Evidence: blocking model/search barrier 集成测试与 UI cancel command unit test 已通过；缺同场景 Playwright。）
- [ ] ◐ 恶意来源要求读取`.env`、执行命令或外发内容；UI显示其为不可信证据且run没有受保护调用。（Evidence: security corpus/report 与 ToolRegistry tests 通过；缺恶意证据 UI E2E。）
- [x] 用户断网、刷新页面并重连；计划/步骤不重复、不丢失，cursor 无效时以 reset snapshot 恢复。（Evidence: backend no-cursor/stale/future reset、public-only replay、same-cursor heartbeat `20 passed`；frontend adapter/controller/bootstrap 重建 `12 tests passed`；strict live E2E 全量通过。）
- [ ] ◐ 用户打开Artifact中的PDF/文档、视频和代码claim，分别到页码、时间戳和高亮行，并可返回producing run。（Evidence: 当前 revision 的 citation-jump 与 producing-run deep link 已测；active revision 切换后从历史 Artifact 打开 retired document/media/code 精确 revision 的 E2E 仍未完成。）
- [ ] ◐ 资料确实不足时，用户得到Evidence Gap Report而不是伪答案，并能从缺口重新发起continuation run。（Evidence: insufficient domain outcome 与 published gap Artifact 已测；continuation-run UI/E2E 未实现。）

## V5.1 Agent Closure Acceptance

### Implementation Completeness

- [x] Agent 对每个 requirement 的首条检索证据执行 open 与 bounded neighbors，三种 ToolCall 均可在 Run Timeline 审计。（Evidence: Agent runtime integration test passed; tool order is search → open → neighbors。）
- [x] Neighbor 只能来自中心证据同一 pinned revision，越界窗口被拒绝。（Evidence: exact chunk/bounded neighbor EvidenceIndex test passed; before/after > 3 is rejected。）
- [x] 未选择候选持久化为 excluded，并显示中文排除原因；neighbor 默认 contextual。（Evidence: backend relation regression、frontend presenter/component unit 与 production projection Playwright passed。）
- [x] modify 仅允许修改 draft Artifact 标题，并生成新 proposal digest。（Evidence: backend modification integration and API contract tests passed。）

### Integration

- [x] open/read neighbor 调用受 tool budget、execution epoch 和 recovery 约束。（Evidence: existing budget/cancel fences plus parameterized search/open/neighbors recovery `3 passed`。）
- [x] 旧 proposal digest 在 modify 后不能批准，新 digest 可以完成同一 Run。（Evidence: modify approval integration rejects old digest and completes with the replacement digest。）

### Build and Test

- [x] Backend focused and full regression pass.（Evidence: focused `93 passed`; final full `444 passed, 1 skipped in 150.71s`，包含 search/open/neighbors recovery matrix。）
- [x] Frontend lint, typecheck, unit tests and production build pass.（Evidence: lint/typecheck exit 0; `17 files / 76 tests`; 34-route build passed。）
- [x] V5 acceptance and release manifest/freshness checks pass.（Evidence: acceptance/quick gates passed；`AI-Knowledge-OS-Pro-V5.0-20260821.zip` has 590 tracked files, forbidden 0, missing 0, verified manifest and current freshness。）

### End-to-End Scenario

- [ ] ◐ 用户查看 Run 时能看到“搜索证据 → 打开证据 → 读取相邻上下文”，未采用证据显示“已排除”；修改标题后重新审批并得到同一 Artifact。（Evidence: backend full flow、production projection 与 Recording Demo Playwright `2/2` passed；浏览器 modify 提交仍由 contract/component tests 覆盖，未单独形成完整 Playwright 场景。）
