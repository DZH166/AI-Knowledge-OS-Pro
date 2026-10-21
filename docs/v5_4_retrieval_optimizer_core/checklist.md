# V5.4A 验收清单（Checklist）

逐项核对，全部通过才算阶段完成。

## A. 核心能力

- [x] A1 可创建 Optimization Study（基准策略/目标/候选上限/评测上限/搜索空间/权重/seed）。
- [x] A2 候选生成：确定性、无重复、不越界、唯一 SHA-256 指纹、相同 seed 同序。
- [x] A3 Trial 持久化执行：SQL Outbox → Redis/RQ → 固定 60 场景评测器 → 持久化结果；
      HTTP 请求内不运行评测。
- [x] A4 多目标评分：6 项指标（含 provider_calls=0）、原始+归一化指标、权重、
      理由、算法版本全部持久化；score 为毫秒整数。
- [x] A5 Pareto Frontier：支配判定、合格过滤、稳定排序、纯函数。
- [x] A6 推荐引擎：六项资格门 + 前沿成员 + 完整理由 + 全链 SHA-256 引用；
      不含任何激活路径。
- [x] A7 取消/恢复：取消后不再派生 Trial；已完成不重跑；lease 过期可接管；
      重复消息不重复写结果；晚到 Worker 被 fence 拒绝；预算停机。
- [x] A8 API 九条路由 + 严格校验（未知字段/布尔整数/NaN/Infinity/越界/自由文本/
      provider 参数/secret 文本全部拒绝）。

## B. 数据与迁移

- [x] B1 新表 optimization_studies / optimization_trials，约束齐全。
- [x] B2 Alembic 0011 单 head；upgrade→downgrade→upgrade 往返成功。
- [x] B3 V5.3 行（policy/evaluation/agent run）在迁移后仍可读，数据不丢。

## C. 边界与安全

- [x] C1 纯算法模块不 import SQLAlchemy/Redis/RQ/FastAPI/HTTP。
- [x] C2 公开 API 结果经过 sanitize/校验，无 prompt、路径、secret 泄漏。
- [x] C3 external_provider_calls 恒为 0 且报告校验强制。
- [x] C4 优化器代码无激活调用路径（推荐 ≠ 上线）。
- [x] C5 无 API Key、无真实模型配置。

## D. 测试与回归

- [x] D1 18 条验收测试全部落位并通过。
- [x] D2 全量后端：636 passed, 1 skipped（基线 582+1 之上新增 54）。
- [x] D3 前端单测：28 files / 105 tests 通过；next build 成功。
- [x] D4 Strict E2E：40/40 通过。
- [x] D5 固定评测：60/60；依赖漏洞扫描 0。

## E. 交付物

- [x] E1 docs/v5_4_retrieval_optimizer_core/ 六份文档。
- [x] E2 learning_log.md / stage_delivery_log.md 追加段。
- [x] E3 提交至 workbuddy/v5.4a-retrieval-optimizer-core。
- [x] E4 WorkBuddy Bundle 与 SHA-256 导出。
