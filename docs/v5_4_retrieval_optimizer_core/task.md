# V5.4A 任务清单（Task）

状态图例：`[ ]` 待办、`[x]` 完成、`[~]` 进行中。

## T1 文档

- [x] spec.md（F1–F8、N1–N6、18 条验收映射）
- [x] plan.md（复用盘点、步骤、风险）
- [x] task.md（本文件）
- [x] checklist.md（可勾选验收单）

## T2 纯算法（TDD）

- [x] contracts.py：命令/查询/结果类型
- [x] objectives.py：指标目录 + 归一化 + score_millis
- [x] candidate_generation.py：确定性候选生成
- [x] pareto.py：dominates + pareto_frontier
- [x] recommendation.py：推荐候选与理由
- [x] test_v5_4a_optimizer_pure.py 先行（覆盖验收 1–4、8–12、14、18 纯逻辑部分）

## T3 数据层

- [x] backend/app/models/optimizer.py（OptimizationStudy / OptimizationTrial）
- [x] models/__init__.py 注册
- [x] alembic 0011_v5_4_retrieval_optimizer（upgrade + downgrade）
- [x] test_v5_4a_optimizer_migration.py

## T4 生命周期与执行

- [x] service.py：submit/start/inspect/execute/cancel/recover
- [x] executor.py：TrialExecutor Protocol + FixedSubprocessTrialAdapter
- [x] recovery.py：lease 过期接管 + Study 重驱动
- [x] wiring.py / interface.py（AgentPolicyOptimizer 四方法）
- [x] test_v5_4a_optimizer_sql.py（验收 5–7、16–18）

## T5 队列与 API

- [x] task_broker.py 增加 agent.optimize.trial 映射
- [x] app/tasks/optimizer_tasks.py RQ 入口
- [x] app/worker.py 恢复循环挂优化器
- [x] schemas/optimizer_schema.py（严格校验全家桶）
- [x] api/routes_optimizer.py + router 注册
- [x] test_v5_4a_optimizer_worker.py / test_v5_4a_optimizer_api.py
      （验收 3、4、13–15 的 API 面）

## T6 回归与审查

- [x] 聚焦测试（optimizer 五个文件全绿）
- [x] 全量后端测试
- [x] 前端 vitest + next build
- [x] Strict E2E 40/40
- [x] Standards Review（代理 1）
- [x] Spec Review（代理 2）
- [x] 修复审查问题并复审

## T7 交付

- [x] acceptance_report.md
- [x] learning_log.md 追加（不改历史）
- [x] stage_delivery_log.md 追加（不改历史）
- [x] git 提交 workbuddy/v5.4a-retrieval-optimizer-core
- [x] 导出 AI-Knowledge-OS-Pro-V5.4A-WorkBuddy.bundle + SHA-256
