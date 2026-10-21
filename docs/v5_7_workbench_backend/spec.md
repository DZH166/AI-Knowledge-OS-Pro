# V5.7 实验工作台后端（Experiment Workbench Backend）— Spec

阶段代号：`V5.7 Experiment Workbench Backend`
分支：`workbuddy/v5.7-workbench-backend`
基线：`210a9e5fed08be0af0d7afcc8d40f9970edc96f0`（V5.6，未修改）

## 0. 范围边界

V5.4A–V5.6 建成了优化器算法层（生成/评测/前沿/推荐/闭环/贝叶斯），但用户
工作流仍要自己串 API。V5.7 做**纯后端的功能层产品化**，为 V5.4B 页面铺路：

1. F1 Study 全景视图（一个端点返回工作流所需的一切）。
2. F2 Study 模板（预置实验配置一键创建）。
3. F3 Study 事件流（生命周期事件持久化 + 查询）。
4. F4 Trial 对比报告导出（Markdown）。
5. F5 Agent Run 只读分享令牌。

不做：页面视觉/CSS/图表（V5.4B）、真实模型、自动激活、空间级策略。

## 1. 功能需求

### F1 Study 全景视图

- 端点：`GET /api/v1/optimizer/studies/{study_id}/overview`
- 一个响应聚合（均为既有数据，只读重组，不改变任何状态机）：
  - study 基本信息（含 round_no、预算与用量、warm_start 链接）；
  - 每轮摘要：round_no、trial 数、完成/失败/取消计数、最佳 score_millis；
  - 全部 Trial 的紧凑行（ordinal、status、score、draft_policy_id、
    recommendation_rank、failure_code）；
  - Pareto 前沿 trial_id 列表（复用 `inspect_pareto` 逻辑，只读，不落库）；
  - 推荐候选摘要（rank、trial_id、rationale 首行、converted 与否）；
  - `actions`：当前状态下允许的操作列表（start/next-round/cancel/fail/retry/
    convert-draft 的可行性与不可行原因）——这是"工作流"的核心：前端不再
    需要自己推断按钮可用性。
- Study 不存在 → 404；无额外副作用。

### F2 Study 模板

- 端点：`GET /api/v1/optimizer/study-templates`（模板目录）
- 端点：`POST /api/v1/optimizer/studies/from-template`
  （body: request_id + template_key + label + 可选 overrides[seed/max_candidates/
  max_evaluations/warm_start_study_id]，全部 Strict 校验）
- 内置 3 个模板（服务端常量，非数据库表）：
  - `quality_first`：目标 quality_first、偏大 top_k 空间、700/300 权重；
  - `balanced`：balanced、V5.4A 默认空间、700/300；
  - `cost_first`：cost_first、偏小 top_k 空间与更低 minimum_score、300/700。
  - 每个模板声明固定的 objective/search_space/weights 与默认
    max_candidates=4、max_evaluations=8、seed=42；overrides 只允许收窄
    （min≤max 仍受 RetrievalPolicyConfig 硬界约束）。
- 转换后走既有 `submit()`（幂等、校验、审计全复用）；unknown template_key →
  404 `OPTIMIZER_TEMPLATE_NOT_FOUND`。

### F3 Study 事件流

- 表 `optimization_study_events`（0014 迁移）：
  id、study_id（FK）、event_type、round_no、payload_json、created_at；
  索引 (study_id, created_at)。event_type 枚举 CHECK：
  study_created/study_started/trial_created/trial_completed/trial_failed/
  trial_cancelled/round_started/recommendation_updated/study_completed/
  study_failed/study_cancelled/draft_converted。
- 写入点（均为既有状态变更处追加一行，同事务）：submit、start、execute
  完成/失败、cancel、fail、next-round、convert_to_draft、
  `_persist_recommendations` 首次产生 rank。
- 端点：`GET /api/v1/optimizer/studies/{study_id}/events?limit=&after=`
  （after 为事件 id 游标，升序分页；limit 1–200 默认 100）。
- 事件 payload 只含 id/类型/计数/指纹等**非敏感摘要**；reason 类文本经
  sanitize_fact。

### F4 Trial 对比报告导出

- 端点：`POST /api/v1/optimizer/studies/{study_id}/export-comparison`
  （body: trial_ids（2–3 个）、可选 include_categories bool）。
- 逻辑：取各 Trial 的 evaluation 明细（复用 `validate_evaluation_report` 的
  数据通路）+ 分类别统计，逐对生成指标 delta（方向化：higher/lower），
  连同 Hard Gate 差异、失败案例增减、分类别胜败表，渲染为确定性 Markdown
  文本（换行符统一 \n、无本地时钟、无用户自由文本——仅字段值）。
- 响应：`{study_id, markdown, sha256, generated_trial_ids}`。
- 报告经 contains_sensitive_text 检查（防泄漏）后才返回。

### F5 Agent Run 只读分享令牌

- 表 `agent_run_share_links`（0014 迁移）：
  token（64 hex，主键）、run_id（FK agent_runs）、created_at、expires_at
  （默认 +7 天）、revoked_at（可空）。
- 端点：
  - `POST /api/v1/agent-runs/{run_id}/share`（body 可选 expires_in_days 1–30，
    默认 7）→ `{token, url_path, expires_at}`；token 用 `secrets.token_hex(32)`；
  - `GET /api/v1/agent-runs/shared/{token}` → 与既有 trace 响应同构的
    RunTraceSchema（复用 `GetRunTrace` 通路），但**只读**：无任何状态变更；
    token 无效/过期/撤销 → 404（不泄露存在性）；
  - `DELETE /api/v1/agent-runs/shared/{token}` → 撤销（revoked_at 置位）。
- 分享视图与普通 trace 相同的脱敏保证（复用既有 trace 投影，无新增字段）。

## 2. 非功能需求

- N1 迁移 `0014_v5_7_workbench_backend`：两张新表 + 单 head + downgrade 对称
  + V5.6 数据保留。
- N2 全部新端点 StrictSchema 校验；报告/事件无敏感信息。
- N3 Markdown 导出纯函数化（`workbench.py` 或独立 `report_export.py` 纯模块：
  输入数据类 → markdown 文本），可测确定性。
- N4 事件写入不改变既有状态机语义（追加式）。
- N5 全量回归：既有 657 后端测试全绿、前端 105、E2E 与基线一致。

## 3. 验收标准（映射测试）

1. overview 聚合各分区且与独立端点一致（sql/api）。
2. overview actions 按状态正确（pending→start；running→cancel/fail；
   completed→next-round；有推荐→convert-draft）（sql）。
3. 模板目录 3 个且字段齐全（api）。
4. from-template 创建成功且字段来自模板（sql/api）。
5. unknown template → 404；unknown overrides 字段 → 422（api）。
6. 事件流：创建/启动/完成 Trial 产生对应事件且顺序正确（sql）。
7. 事件分页 after 游标有效（api）。
8. 事件 payload 无敏感文本（reason 注入 → redact）（sql）。
9. 导出 markdown：确定性（同输入同输出 + 同 sha256）（pure/sql）。
10. 导出含指标 delta/Hard Gate 差异/分类别表（pure）。
11. 导出拒绝 <2 或 >3 个 trial（api）。
12. 分享令牌创建/读取 trace/撤销后 404（sql/api）。
13. 过期令牌 → 404（sql）。
14. 分享 trace 与直接 trace 数据一致（sql）。
15. 迁移 0014 单 head/往返/保留（migration）。
16. 全部新端点严格校验（api）。
17. Provider 调用恒 0 不被破坏（断言）。
