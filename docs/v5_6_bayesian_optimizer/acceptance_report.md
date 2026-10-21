# V5.6 验收报告（Acceptance Report）

日期：2026-08-31
分支：`workbuddy/v5.6-bayesian-optimizer`
基线：`b38956d70209b963145a090dc3734f5d0c03e245`（V5.5，未修改）

## 一、交付范围

1. **贝叶斯候选生成**（`bayesian_generation.py` 纯模块）：一维线性代理模型
   （最小二乘斜率，纯 Python，零新依赖）+ 探索率衰减（第 2 轮 0.6 起、
   每轮 -0.15、下限 0.2）；第 1 轮与 V5.4A 随机生成完全等价（同 seed 复用）。
2. **暖启动**：`StudyCommand.warm_start_study_id` 继承父 Study 全部
   (config, score) 观测，新 Study 直接进入第 2 轮引导模式；HTTP 层可提交，
   引用不存在 Study 返回 404。
3. **分类别分析**（`category_analysis.py` 纯模块）：7 类场景的
   pass_rate/recall 对比与 verdict；完成 Trial 落库 `category_stats_json`；
   `GET .../trials/{id}/categories` 返回相对基准（ordinal 1）的对比行
   （含 wins/ties/losses/verdict）；推荐理由追加类别摘要句。
4. **多轮实验**：`POST .../next-round` 基于 completed Study 的观测生成
   下一轮候选（接续 ordinal、回 running）；每轮候选上限 max_candidates、
   跨轮评测总量上限 max_evaluations；request_id 幂等（含并发 IntegrityError
   回退）。

## 二、测试数量（准确值）

| 套件 | 结果 |
| --- | --- |
| V5.6 聚焦测试（4 文件） | 21 passed（pure 9 + sql 7 + api 3 + migration 2） |
| 全量后端（最终，清洁环境） | **657 passed, 1 skipped**（V5.5 的 636 全保持 + V5.6 新增 21） |
| 前端单元测试 | 28 files, 105 passed |
| 前端构建 | 通过 |
| Strict E2E | 39/40（仅剩 V5.2 trace 用例的既有环境 flake；V5.3 policy 用例本轮通过） |
| 依赖 | requirements.txt 零新增（纯 Python 实现） |

## 三、双轴审查与修复

审查发现 10 项（8 必须 + 2 建议），**全部修复**：

1. Protocol 补 `start_next_round` + `__all__` 加 `NextRound`。
2. API 暴露 warm start（schema + 路由透传 + 404 测试）。
3. `start_next_round` IntegrityError 回退的 session 泄漏修复（with 上下文）。
4. 消除 `__import__` hack 与局部 HTTPException 导入。
5. categories 端点对齐 spec：改用 `compare_categories` 返回相对基准的
   verdict 对比行（schema 同步为 `CategoryComparisonSchema`）。
6. 推荐理由接线 `summarize_categories`（rationale 追加类别摘要句）。
7. spec 修订：预算语义（每轮候选/跨轮评测）、基准锚点跨轮语义。
8. 死代码/恒真断言/无用导入/`__import__` 写法清理；多 seed 统计断言加固；
   warm start 测试补"观测确实改变候选序列"断言。
9. Study 详情暴露 round_no/warm_start_study_id/next_round_request_id；
   Trial 模型补 server_default 与迁移对齐；algorithm_version 统一 `v5_6_bayesian_1`。
10. 测试常量命名修正（V5_5_REVISION 恢复为 0012）。

## 四、诚实边界

- 代理模型是"观测引导采样"而非最优求解器（spec 已注明）。
- 60 题固定评测仍是确定性架构证据，不是真实模型质量基准。
- Strict E2E 剩余 1 个失败为既有 routing flake（跨 V5.3/V5.4A/V5.5/V5.6
  四个阶段对照一致）。
