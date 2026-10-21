# V5.4A 离线检索策略优化器核心 — Spec

阶段代号：`V5.4A Offline Retrieval Optimizer Core`
分支：`workbuddy/v5.4a-retrieval-optimizer-core`
基线提交：`062cf05cd23631488704915b62b6cbf1b6a22802`（`codex/v5.3-adaptive-policy-retrieval`）

## 0. 范围边界

本阶段只交付优化器核心算法、SQL 数据模型、后台执行链路与 API。不交付任何视觉页面；
页面视觉、截图审查、CSS 与多媒体界面由另一个 Agent 负责（V5.4B）。
本阶段禁止配置真实模型、禁止添加 API Key、禁止自动激活任何推荐策略。

## 1. 功能需求

### F1 Optimization Study（优化实验）

用户可创建一次优化实验（Optimization Study），指定：

- 基准策略 `base_policy_id`（必须存在、必须是当前 Active 或至少是合法策略行）。
- 优化目标 `objective`（`quality_first` | `balanced` | `cost_first`）。
- 最大候选数量 `max_candidates`（1–64）。
- 最大评测次数 `max_evaluations`（1–128）。
- 搜索空间 `search_space`（每个可调参数的 min/max，必须在 RetrievalPolicyConfig 安全区内）。
- 质量与成本权重 `weights`（质量权重 + 延迟权重，非负，和大于 0）。
- 随机种子 `seed`（0–2^31-1，决定候选生成顺序，保证可复现）。

Study 状态机：`pending → running → completed | cancelled | failed`。
相同 `request_id` 重复提交返回既有 Study（幂等回放），不同负载报
`OPTIMIZER_IDEMPOTENCY_CONFLICT`（409）。

### F2 Candidate Generation（候选策略生成）

纯函数模块 `candidate_generation.py`：

- 只能修改 `factual_top_k`、`comparative_top_k`、`temporal_top_k`、
  `minimum_score_millis`、`max_hits_per_source`、`neighbor_before`、`neighbor_after`。
- 以 V5.3 `RetrievalPolicyConfig`（frozen dataclass，`agent_policy/config.py`）为载体；
  候选配置直接用 `RetrievalPolicyConfig.__post_init__` 的安全约束校验，
  并以调用方传入的搜索空间进一步收窄。
- 生成策略：以 seed 初始化 `random.Random(seed)`，对每个可调维度在搜索空间内采样；
  第一个候选固定为基准策略本身（作为对照锚点），随后生成扰动候选。
- 硬性要求：结果确定；无重复配置（重复即丢弃再补采）；参数不越界；
  每个候选有唯一 SHA-256 指纹（复用 `policy_fingerprint`）；
  相同输入与 seed 产生完全相同的候选序列；
  候选策略绝不写入 `active` 状态（本阶段根本不创建 agent_policy_versions 行，
  候选只以快照 JSON + 指纹形式存在于 Trial 上；激活只可能走 V5.3 已有人工接口，
  而优化器代码不调用它）。

### F3 Durable Trial Execution（可持久化候选试验）

每个候选对应一个 Optimization Trial（单次候选试验），通过现有 durable 链路执行：

```
SQL Outbox（topic=agent.optimize.trial）
  → OutboxDispatcher（租约认领）
  → Redis/RQ（function=app.tasks.optimizer_tasks.run_optimization_trial）
  → FixedSubprocessEvaluationAdapter（固定 60 场景评测器，--policy-config 注入候选快照）
  → 持久化评测结果（agent_evaluations 行 + trial 指标回填）
```

- 禁止在 HTTP 请求内联运行评测。
- Trial 通过 `evaluation_id` 关联一行真实的 `agent_evaluations`
  （复用 V5.2/V5.3 的完整报告校验、Hard Gate、敏感文本拦截）。
- Trial 状态机：`pending → running → completed | failed | cancelled`。
- 预算：Study 记录 `budget_json`（max_candidates / max_evaluations / deadline_at）与
  `budget_usage_json`（created_trials / started_evaluations）；达到任一上限即停止生成新 Trial，
  Study 转入 `completed`。

### F4 Multi-objective Scoring（多目标评分）

`objectives.py` 纯函数：

比较指标至少包括（方向固定）：

| 指标 | 方向 | 来源 |
| --- | --- | --- |
| case_pass_rate | higher | evaluation metrics |
| mean_source_recall | higher | evaluation metrics |
| citation_completeness | higher | evaluation metrics |
| latency（agent_p95，毫秒） | lower | evaluation metrics.latency_ms |
| retrieval window（factual+comparative+temporal_top_k 之和） | lower | 候选配置 |
| external_provider_calls | lower，且必须为 0 | evaluation provenance |

- 归一化：对每个指标在 Study 内的候选集合上做 min-max 归一化到 [0,1]
  （退化情形：所有值相同 → 归一化值取 0.5；区间跨度为 0 时不得出现除零）。
- 加权总分以毫秒整数存储（`score_millis`，0–1000），避免浮点漂移；
  权重使用 Study 保存的 `weights_json`（整数 permille，千分比）。
- 必须持久化：原始指标（`metrics_json`）、归一化指标（`normalized_metrics_json`）、
  使用的权重（Study 的 `weights_json`）、推荐理由（`recommendation_json`）、
  评分算法版本（`algorithm_version`，字符串如 `v5_4a_1`）。
- 评分不替代 Pareto 判断；推荐以 Hard Gate + Pareto 为主、评分为展示排序。

### F5 Pareto Frontier（帕累托前沿）

`pareto.py` 纯函数（不 import SQLAlchemy/Redis/HTTP）：

- `dominates(left, right)`：left 在所有指标上不比 right 差，且至少一项严格更好 → True。
  指标方向由 `objectives.py` 的目录决定（higher/lower）。
- `pareto_frontier(trials)`：返回未被任何**合格** Trial 支配的 Trial 集合。
- 合格性过滤：status=completed、评测 passed、external_provider_calls=0、
  全部 Hard Gate 通过、策略指纹与评测报告指纹一致、failure case 数为 0。
  失败、取消、未完成或数据不完整的 Trial 一律不进入前沿。
- 稳定排序：按 (score_millis 降序, created 顺序 ordinal 升序, id 升序)；
  相同输入必须产生相同输出（纯函数、无时钟、无随机）。

### F6 Recommendation Engine（推荐引擎）

`recommendation.py` 纯函数 + service 组装：

- 推荐来源必须同时满足 F5 的全部合格条件 **且** 处于 Pareto Frontier。
- 输出推荐候选（recommendation candidate），按稳定排序给出 rank。
- 推荐理由必须解释：
  - 相比基准策略（base trial）改进了什么（逐指标 delta）；
  - 哪些指标没有变化；
  - 哪些指标可能退步（若有）；
  - 为什么仍值得推荐（支配关系/总分/权重取向）；
  - 关联 Study、Trial、Policy（指纹+快照）、Evaluation、SHA-256。
- 推荐器只能输出"推荐候选"数据；模块内不存在任何激活调用路径，
  无 `activate` 引用，激活仍只能通过 V5.3 的
  `POST /api/v1/agent-policies/{id}/activate`（其自身带 60/60 评测硬门）由人工执行。

### F7 Cancellation, Recovery, Fencing（取消、恢复与围栏）

- `cancel`：仅 `pending/running` Study 可取消；取消后 executor 不再创建新 Trial，
  pending Trial 置 cancelled，running Trial 允许跑完但不影响推荐。
- `recover`：`lease_expires_at` 过期的 running Trial 可被接管重新入队；
  Study 级 `recover` 重新驱动其 outbox 消息。
- 已完成（completed/failed/cancelled）Trial 不重复执行（claim 仅在 pending 上成功）。
- 重复消息（重复 outbox 行、重复 RQ 投递）不会重复写结果：
  完成写入是带状态+lease_owner 条件的条件 UPDATE（fence），晚到的旧 Worker
  结果因 owner/status 不匹配被拒绝，不覆盖新结果。
- 过期 Lease 可以被安全接管（无条件 UPDATE 原子重置 lease_owner）。
- 预算（候选数/评测数/运行时间 deadline）耗尽后停止派生新 Trial。

### F8 API（严格类型化）

`/api/v1/optimizer/...`，全部 schema 继承 `StrictSchema(extra="forbid")`，
数字字段一律 `StrictInt`/`StrictFloat`，枚举用 `Literal`：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/optimizer/studies` | 创建 Study（幂等 request_id） |
| GET | `/optimizer/studies` | Study 列表 |
| GET | `/optimizer/studies/{id}` | Study 详情（含预算用量） |
| GET | `/optimizer/studies/{id}/trials` | Trial 列表 |
| GET | `/optimizer/trials/{id}` | 单个 Trial 详情 |
| POST | `/optimizer/studies/{id}/cancel` | 取消 Study |
| POST | `/optimizer/studies/{id}/recover` | 恢复过期 Study |
| GET | `/optimizer/studies/{id}/pareto` | Pareto Frontier |
| GET | `/optimizer/studies/{id}/recommendation` | 推荐候选 |

补充：Study 的启动由 `POST /optimizer/studies/{id}/start` 驱动（创建 Trial 与
outbox 消息属于写操作，须显式触发）；Trial 的执行不存在任何 HTTP 内联端点，
只能经 outbox → Redis/RQ worker 路径运行。

必须拒绝：未知字段（extra=forbid）、布尔冒充整数（StrictInt）、
NaN/Infinity（Pydantic allow_inf_nan=False + canonical JSON allow_nan=False）、
越界数字（ge/le）、任意 Prompt/Shell/Python 代码/文件路径（无自由文本执行面；
label 走 contains_sensitive_text 清洗）、Provider 参数/API Key/Secret-looking 文本
（contains_sensitive_text + 无任何 provider 相关字段）。

## 2. 非功能需求

- N1 确定性：候选生成与 Pareto/推荐排序对相同输入幂等。
- N2 数据库约束阻止明显错误状态（状态枚举、attempt/调用数非负、score 0–1000、
  ordinal 唯一、指纹长度 64）。
- N3 迁移单 head：`0011_v5_4_retrieval_optimizer`，upgrade/downgrade 均可执行，
  V5.3 数据不丢失，旧 Policy/Evaluation/Agent Run 仍可读。
- N4 模块边界：`backend/app/modules/agent_policy_optimizer/`，
  纯算法模块不 import SQLAlchemy/Redis/RQ/HTTP/FastAPI。
- N5 不破坏 V5.3：前端单测、Strict E2E、既有 582 后端测试全部保持通过。
- N6 外部 Provider 调用恒为 0（评测器本身确定性运行，报告校验强制）。

## 3. 验收标准（映射测试要求）

对应任务书"测试要求"18 条，全部落在
`backend/tests/test_v5_4a_optimizer_{pure,sql,worker,api,migration}.py`：

1. 候选生成确定且无重复（pure）
2. 相同 seed 相同顺序（pure）
3. 越界参数拒绝（pure/api）
4. Boolean/NaN/Infinity 拒绝（api/pure）
5. 相同 request_id 不重复创建 Study（sql）
6. 并发创建 Trial 不重复 ordinal（sql）
7. 已完成 Trial 不重复执行（sql/worker）
8. 失败 Trial 不进 Pareto（pure）
9. 被支配判断正确（pure）
10. Pareto 顺序稳定（pure）
11. 推荐只来自全 Hard Gate 通过 Trial（pure/sql）
12. 指纹不一致拒绝推荐（pure/sql）
13. 推荐器不能激活策略（代码审查 + pure 断言模块无激活路径）
14. Provider 调用数必须为 0（pure/sql/api）
15. 私密 Prompt/查询/路径不入公开结果（api/pure，sanitize）
16. 取消后不再创建新 Trial（sql）
17. 崩溃恢复不覆盖已完成结果（sql/worker）
18. 晚到 Worker 结果被 Fence 拒绝（sql）

## 4. 明确不做

- 不做最终视觉页面、不做图表视觉、不改 CSS 体系。
- 不做贝叶斯优化/真实模型评测（确定性 60 场景是唯一真值来源）。
- 不自动激活推荐策略。
- 不修改 `codex/v5.3-adaptive-policy-retrieval` 分支。
