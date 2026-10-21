# V5.5 检索优化器闭环（Optimizer Closed Loop）— Spec

阶段代号：`V5.5 Optimizer Closed Loop`
分支：`workbuddy/v5.5-optimizer-closed-loop`
基线：`53252cc9c4cfd34508fc483c8fbf2813d6753217`（V5.4A，未修改）

## 0. 范围边界

V5.4A 打通了"生成候选 → 评测 → 推荐"，但推荐到上线之间仍是断开的：
用户需要手工抄写配置到 V5.3 策略创建接口。V5.5 补上这一段闭环：

1. 推荐候选 → 一键转换为 V5.3 **draft** 策略（不激活）。
2. 候选与当前 Active 策略的逐字段 diff。
3. Study 收尾状态机完善：预算耗尽后正确落终态；瞬态失败 Trial 可重试；
   显式终止端点。

仍然不做：页面视觉（V5.4B 归另一 Agent）、自动激活、真实模型、贝叶斯搜索。

## 1. 功能需求

### F1 Convert To Draft（推荐候选转草稿）

- 端点：`POST /api/v1/optimizer/studies/{study_id}/recommendation/{trial_id}/convert-draft`
  （request body: `request_id` + 可选 `label`）。
- 服务方法：`AgentPolicyOptimizer.convert_to_draft(command)`。
- 安全链路（全部前置校验，任一失败 4xx）：
  1. Study 存在且 Trial 属于该 Study；
  2. Trial 状态 completed、在 Pareto 前沿、`recommendation_rank` 非空（即确实是推荐候选）；
  3. Trial `config_json` 能通过 `policy_config_from_snapshot` 严格重建且指纹等于 `config_sha256`；
  4. 通过 V5.3 `AgentPolicy.submit(CreatePolicy(...))` 以幂等方式创建
     **draft** 策略：`base_policy_id` 使用 Study 的 `base_policy_id`，
     label 默认 `Optimizer <study label> - trial <ordinal>`（可覆盖，走
     contains_sensitive_text 清洗）。
- 幂等：同一 `request_id` 重复调用返回既有 draft（replayed=true）；
  换 request_id 但 Trial 已转过 → 返回已存在的 draft（幂等去重，不创建第二行）。
- 输出：`policy_id`、`policy_version`、`status`（新建时必须为 draft；
  replay 时返回该策略**当前**生命周期状态——若 draft 此后经人工流程激活，
  replay 如实返回 active）、`policy_config_sha256`（必须等于 Trial
  `config_sha256`，否则 409）、`replayed`。
- **绝不调用 activate**；draft 到 active 仍只能走 V5.3 激活接口及其 60/60 硬门。
- Trial 行记录转换结果（`draft_policy_id`），保证一 Trial 一 draft。

### F2 Candidate Diff（候选与当前策略比较）

- 端点：`GET /api/v1/optimizer/studies/{study_id}/trials/{trial_id}/diff`
- 服务方法：`AgentPolicyOptimizer.inspect(... | DiffTrialAgainstActive)`。
- 逻辑：加载 Trial 配置（严格重建校验），取当前 Active 策略
  （V5.3 单 Active 语义），复用 `compare_policy_configs` 生成
  compatible / incompatibility_reasons / changes（field, left, right）。
- 额外输出：trial `config_sha256`、active `config_sha256`、active policy id/version，
  以及 Trial 评测指标摘要（eligible、score_millis）供上下文。
- Active 不存在（理论不可能）→ 503；Trial 配置损坏 → 422。

### F3 Study 收尾状态机（Settlement）

- `start()` 在预算内创建 Trial 后，若因预算（candidates 或 evaluations 上限）
  没能创建满候选 → 正常（评测阶段继续）。
- **新增收尾判定**（复用 `_maybe_settle`，在 cancel/execute/recover 后触发）：
  - 全部 Trial 进入终态（completed/failed/cancelled）且至少一个 completed →
    Study `completed`（混合 completed+failed 亦按 completed 收尾）。
  - 全部 Trial 终态且**没有一个** completed（全失败/全取消）→ Study `failed`。
  - 预算内仍有 pending → 保持 running。
  - 触发时机：execute 完成写回（含失败写回）事务内。
- **瞬态失败重试**：failed Trial 提供 `retry` 路径
  （`POST /api/v1/optimizer/trials/{trial_id}/retry`）：仅 failed → pending
  （清 failure_code/lease/finished_at，attempt 保留累加），并复活其 outbox 行
  （dead_letter→pending、attempt 归零；被 cancel/fail 标记的死信行不复活）。
  守卫：Trial 属于 **running** 的 Study（终态 Study 的 Trial 不可重试），
  且重试受 Study 预算约束（started_evaluations < max_evaluations，超限 409）。
- **显式终止**：`POST /api/v1/optimizer/studies/{study_id}/fail`
  （body: reason 可选）：仅 pending/running Study 可调用；置 failed、终止全部
  未完成 Trial（终态化）与未派发 outbox 行。用于操作员手动止损。
- 已有 cancel 语义不变（running 允许跑完）。

## 2. 非功能需求

- N1 转换/diff/收尾全部确定性、幂等或显式幂等（request_id）。
- N2 新增 DB 列：`optimization_trials.draft_policy_id`（FK agent_policy_versions，可空，
  一 Trial 一 draft 由 UNIQUE 保证）+ `optimization_trials.request_id`（转换幂等键，
  可空，UNIQUE）。Migration `0012_v5_5_optimizer_closed_loop`，单 head，
  upgrade/downgrade 对称，V5.4A 数据保留。
- N3 模块边界不变：纯算法零基础设施 import；激活路径仍然零引用。
- N4 不破坏 V5.4A：既有 615 后端测试全绿，前端 105 全绿，E2E 与 V5.4A 基线对照一致。
- N5 输入校验沿用 StrictSchema 全家桶；新端点同样拒绝未知字段/布尔/越界/secret。

## 3. 验收标准（18+ 条映射）

1. convert-draft 创建 draft 且 status=draft、指纹与 Trial 一致（sql/api）。
2. convert-draft 幂等：同 request_id replay；异 request_id 去重返回同一行（sql）。
3. 非 completed / 非前沿 / 非推荐 Trial 拒绝转换（sql/api）。
4. 指纹损坏的 Trial 拒绝转换（sql）。
5. convert-draft 绝不激活：断言 active 策略在转换前后不变（sql）。
6. 模块源码无 activate 路径（pure 守护测试更新）。
7. diff 返回逐字段 changes 且方向正确（left=active, right=candidate）（sql/api）。
8. diff 对损坏配置拒绝（sql）。
9. 全部 completed → study completed（sql）。
10. 全部 failed → study failed（sql）。
11. retry：failed→pending，outbox 复活，可再次执行（sql）。
12. retry 对 completed/running 拒绝（sql）。
13. 显式 fail：pending/running Study → failed，未完成 Trial 终态化（sql/api）。
14. 已终态 Study 拒绝 fail（sql）。
15. 迁移 0012：单 head、往返、V5.4A 行保留、新列约束生效（migration）。
16. API 严格校验：新端点拒绝未知字段/布尔/越界/secret 文本（api）。
17. 公开输出无敏感信息（label 清洗、sanitize）（api）。
18. Provider 调用恒 0 不被破坏（既有守护 + 新增断言）。
