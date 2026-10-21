# V5.6 贝叶斯检索优化器（Bayesian Optimizer + Category Analysis）— Spec

阶段代号：`V5.6 Bayesian Optimizer`
分支：`workbuddy/v5.6-bayesian-optimizer`
基线：`b38956d70209b963145a090dc3734f5d0c03e245`（V5.5，未修改）

## 0. 范围边界

在 V5.5 闭环之上升级两块能力：**更聪明的候选生成**（贝叶斯优化）与
**更有信息量的评测产出**（分类别胜败分析）。仍然不做：页面（V5.4B）、
自动激活、真实模型、影子评估。

## 1. 功能需求

### F1 Bayesian Candidate Generation（贝叶斯候选生成）

- 新纯函数模块 `bayesian_generation.py`（零基础设施 import）。
- **代理模型**：对每个可调维度做一维线性回归的加权和
  （观测 = 历史候选配置向量 → 归一化总分），加 nucleus 扰动；
  确定性：所有"随机"来自 `random.Random(seed)`，禁止 numpy 全局随机态。
  （不引入 scipy 依赖；numpy 仅用于线性代数小规模运算，或纯 Python 实现——
  实现自选，但必须确定性且无新依赖进入 requirements.txt 之外的运行时。）
- **生成流程（multi-round）**：
  - 第 1 轮（无观测）：行为与 V5.4A 随机生成完全一致（复用 `generate_candidates`）。
  - 后续轮（有观测）：输入 = (已完成的候选配置, 归一化分数) 观测对；
    每个维度拟合分数对维度值的简单线性关系（含符号与斜率），
    沿预测改进方向在搜索空间内取点，再按递减的探索率（exploration rate，
    随轮次衰减）注入扰动；重复配置丢弃重采；基准锚点不重复生成。
- **Warm start（暖启动）**：`StudyCommand` 新增可选
  `warm_start_study_id`：创建 Study 时复制该历史 Study 的全部
  (config, score) 观测作为第 0 轮观测（只读引用，不修改旧 Study）。
  被引用 Study 必须存在；不存在 → 404。
- **确定性**：相同 (观测, 搜索空间, seed, 轮次) 必产生相同候选序列。
- 候选仍必须通过 `RetrievalPolicyConfig` 与搜索空间双重校验，指纹唯一。

### F2 Category Analysis（分类别胜败分析）

- 新纯函数模块 `category_analysis.py`：
  - 输入：一个 Trial 的逐案例结果（category, passed, source_recall, latency_ms）
    + 另一个 Trial 的同构结果（默认基准 Trial）。
  - 输出：按 7 个固定类别的对比行——`passed_delta`（胜/平/败计数）、
    `pass_rate_left/right`、`mean_source_recall_left/right`、`verdict`
    （improved/regressed/tied 按该类别通过率比较）。
  - 类别集合必须等于 `EXPECTED_CATEGORY_COUNTS` 的 7 类；输入缺类 → 报错。
- Trial 落库：`optimization_trials` 新增 `category_stats_json`（TEXT 可空），
  在 `_complete_trial` 写回时由验证报告的逐案例结果计算并持久化。
- API：`GET /api/v1/optimizer/studies/{study_id}/trials/{trial_id}/categories`
  返回该 Trial 的分类别统计（相对基准 Trial 即 ordinal 1）。
- 推荐理由增强：`RecommendationBundle` 的 rationale 追加一句类别摘要
  （improved/regressed 的类别名列表），`category_analysis.py` 提供纯函数
  `summarize_categories()`。

### F3 Multi-round Study（轮次化实验）

- Study 状态机不变（completed/failed/cancelled），但收尾后允许**派生下一轮**：
  - 新端点 `POST /api/v1/optimizer/studies/{study_id}/next-round`
    （body: request_id 幂等）：
    - 仅 completed Study 可调用；
    - 以贝叶斯生成器基于本轮全部 (config, score) 观测生成下一轮候选；
    - 新 Trial 的 ordinal 接续（不与既有 ordinal 冲突）；
    - 受 Study 总预算约束：累计 created_trials ≤ max_candidates、
      累计 started_evaluations ≤ max_evaluations（由 next-round 预检查 +
      start 时约束）；超出 → 409 `OPTIMIZER_BUDGET_EXHAUSTED`。
    - 幂等：同 request_id 返回首次结果（记录于 Study 的 `next_round_request_id`）。
  - Study 需要 `round_no`（从 1 开始）与 `parent_study_id`（可空）来追踪轮次链；
    next-round 可选择创建**子 Study**（默认）或复用当前 Study 追加 Trial——
    取"复用当前 Study 追加 Trial"（实现简单、查询自然），Study 加
    `round_no` + `next_round_request_id` 列即可。
  - completed Study 被 next-round 追加 Trial 后回到 running（合理：又有工作）。

## 2. 非功能需求

- N1 纯函数确定性（F1/F2 无时钟无全局随机）。
- N2 Migration `0013_v5_6_bayesian_optimizer`：trials 加 `category_stats_json`、
  `round_no`（默认 1）；studies 加 `round_no`（默认 1）、`next_round_request_id`
  （UNIQUE 可空）、`warm_start_study_id`（FK studies，可空）。单 head、
  downgrade 对称、V5.5 数据保留。
- N3 模块边界不变；requirements.txt 不新增依赖。
- N4 严格校验沿用；无敏感信息泄漏；Provider 调用恒 0。
- N5 全量回归不破坏：既有 636 后端测试全绿、前端 105、E2E 与基线一致。

## 3. 验收标准（映射测试）

1. 贝叶斯第 1 轮与随机生成等价（相同输入相同输出）（pure）。
2. 有观测时贝叶斯生成确定性（同 seed 同序）（pure）。
3. 观测引导：线性关系中"分数随某维度递增"时，多数候选该维度值高于空间中位（pure，统计性断言）。
4. 探索率衰减：相同观测下，高轮次候选更集中于预测最优点邻域（pure，统计性断言）。
5. 重复配置丢弃、指纹唯一、越界拒绝（pure）。
6. warm start：观测被继承，新 Study 第 2 轮即可用（sql）。
7. warm start 引用不存在 Study → 404（sql/api）。
8. category_analysis：7 类齐全、verdict 方向正确、缺类报错（pure）。
9. category_stats 落库：完成 Trial 后可查询（sql）。
10. categories 端点返回统计且基准为 ordinal 1（api）。
11. 推荐理由含类别摘要（sql）。
12. next-round：completed Study 生成接续 ordinal 的新 Trial、回 running（sql/api）。
13. next-round 幂等（同 request_id）（sql/api）。
14. next-round 预算耗尽 → 409（sql）。
15. next-round 对非 completed Study → 409（sql）。
16. 迁移 0013：单 head、往返、V5.5 数据保留、新列约束（migration）。
17. 严格校验新端点（api）。
18. Provider 调用恒 0（新增断言）。
