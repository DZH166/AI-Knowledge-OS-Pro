# V5.6 实施计划（Plan）

## 复用盘点

- V5.4A `generate_candidates`（第 1 轮直接复用）；`TUNABLE_FIELDS`、搜索空间校验。
- V5.5 `_maybe_settle`/预算结构；`StudyCommand` 扩展 warm_start_study_id。
- V5.2 报告逐案例（`ValidatedEvaluationReport.cases`）→ `_complete_trial` 处计算
  category_stats；`EXPECTED_CATEGORY_COUNTS` 7 类目录。
- 观测来源：trial 的 `metrics_json`（score_millis）+ `config_json`。

## 步骤

1. 文档四件套（本目录）。
2. TDD 红：pure（bayesian/category）、sql（warm start/next-round/category 落库）、
   api（categories/next-round/校验）、migration（0013）。
3. 纯模块：`bayesian_generation.py`（线性代理 + 探索衰减）、`category_analysis.py`。
4. Migration 0013：trials + category_stats_json/round_no；studies + round_no/
   next_round_request_id/warm_start_study_id。
5. service：观测读取、next_round、warm start、category_stats 写回、推荐理由增强。
6. API：2 端点 + schemas。
7. 转绿 → 全量回归 → 前端 → E2E 对照 → 双轴审查 → 交付。

## 风险

- R1 贝叶斯过拟合 60 题 → 探索率下限保底（不低于 0.2），保证多样性。
- R2 代理模型非最优 → 定位为"观测引导采样"而非最优求解；spec 明确。
- R3 ordinal 接续并发冲突 → UNIQUE(study_id, ordinal) 已有，next-round 在
  事务内 max(ordinal)+1 分配。
