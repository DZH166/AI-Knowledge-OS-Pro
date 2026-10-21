# V5.4A 实施计划（Plan）

## 依赖与复用盘点（已核实）

- 候选策略载体：`backend/app/modules/agent_policy/config.py` 的
  `RetrievalPolicyConfig`（frozen，字段全部 int，越界抛 ValueError），
  `policy_fingerprint()` 给出 SHA-256 指纹。
- 评测执行链：`SqlAgentControl`（outbox 写入 → `agent.evaluate` topic →
  `app.tasks.evaluation_tasks.run_agent_evaluation` → `FixedSubprocessEvaluationAdapter`
  → `validate_evaluation_report`）。优化器不复制这条链，而是：
  Trial 的评测直接作为一次携带候选快照（`policy_snapshot_json` +
  `policy_fingerprint`）的 `agent_evaluations` 行进入同一 outbox 链；
  为不干扰 V5.3 语义，优化器使用**独立 outbox topic** `agent.optimize.trial`
  和独立 RQ 函数 `app.tasks.optimizer_tasks.run_optimization_trial`，
  内部调用优化器 executor 完成 claim→运行评测→fence 写回。
- Hard Gate 与报告校验：`agent_control/report.py::validate_evaluation_report`、
  `REQUIRED_HARD_GATES`；激活门 `agent_policy/activation_gate.py` 只被 V5.3 使用。
- 队列设施：`OutboxDispatcher`（通用，topic→envelope）、`RedisRQTaskBroker`
  （topic→function 映射需新增 `agent.optimize.trial` 分支）、`app/worker.py`
  （恢复循环需挂优化器 recover）。
- Alembic：当前 head `0010_v5_3_agent_policy`，新增 `0011_v5_4_retrieval_optimizer`。

## 阶段步骤

1. **文档先行**：spec.md / plan.md / task.md / checklist.md（本目录）。
2. **纯算法 TDD**（`modules/agent_policy_optimizer/`）：
   - `contracts.py`：命令/查询/返回 dataclass；`OptimizerObjective`、
     `TrialMetrics`、`TrialOutcome`、`RecommendationCandidate` 等。
   - `objectives.py`：指标目录（方向、来源）、min-max 归一化（退化→0.5）、
     permille 权重加权 `score_millis`。
   - `candidate_generation.py`：seed 确定性候选序列（首候选=基准锚点，
     其余扰动；重复丢弃补采；搜索空间收窄 + RetrievalPolicyConfig 兜底校验）。
   - `pareto.py`：`dominates` / `pareto_frontier`（合格过滤 + 稳定排序）。
   - `recommendation.py`：从合格前沿 Trial 构建推荐候选与理由
     （改进/持平/退步逐指标 + 支配与权重解释 + 全部 SHA-256 引用）。
3. **数据模型**：`backend/app/models/optimizer.py`：`OptimizationStudy`、
   `OptimizationTrial`（约束见 spec N2），注册进 `models/__init__.py`；
   Alembic `0011_v5_4_retrieval_optimizer`（upgrade/downgrade 对称，
   不动既有表数据）。
4. **生命周期**：`service.py` `SqlAgentPolicyOptimizer`：
   - `submit`：创建 Study（幂等），预算初始为空 usage，状态 pending。
   - `start`：pending→running，生成候选、按预算创建 pending Trial + outbox 行
     （与 Trial 同事务，原子）。
   - `inspect`：列表/详情/trial 列表/trial 详情/pareto/recommendation 查询，
     pareto/recommendation 用纯函数在已完成 Trial 上即时计算。
   - `execute`（worker 调用）：fence claim（status pending→running、
     attempt+1、lease 写入）→ 调 executor（真实链路为子进程固定评测器）→
     条件 UPDATE 写回（status=running & lease_owner=self 才能写）；
     失败写 failure_code，不覆盖已完成。
   - `cancel` / `recover`。
5. **执行协调**：`executor.py` 定义 `TrialExecutor` Protocol +
   `FixedSubprocessTrialAdapter`（复用 `FixedSubprocessEvaluationAdapter`，
   注入候选快照）；`recovery.py` 提供 lease 过期接管与 Study 重驱动；
   `wiring.py` 组装生产依赖；`interface.py` 公开
   `AgentPolicyOptimizer.submit/inspect/execute/recover` Protocol。
6. **队列接入**：`task_broker.py` 增加 topic 映射；
   `app/tasks/optimizer_tasks.py` 新增 RQ 入口；`app/worker.py` 恢复循环挂
   优化器 recover；`api/router.py` 挂新路由。
7. **API**：`schemas/optimizer_schema.py`（StrictSchema 全家桶）+
   `api/routes_optimizer.py`。
8. **测试**（TDD，先红后绿）：
   - `test_v5_4a_optimizer_pure.py`：候选确定性/无重复/越界拒绝、归一化退化、
     支配关系、前沿稳定排序、推荐资格与理由、fence 纯逻辑。
   - `test_v5_4a_optimizer_sql.py`：幂等创建、ordinal 并发唯一、预算停机、
     取消后不创建、已完成不重跑、恢复不覆盖、晚到写回被拒。
   - `test_v5_4a_optimizer_worker.py`：RQ 任务函数、executor 快照绑定、
     指纹不一致失败。
   - `test_v5_4a_optimizer_api.py`：九条路由、未知字段/布尔/NaN/Infinity/越界/
     secret 文本拒绝、公开结果无敏感信息。
   - `test_v5_4a_optimizer_migration.py`：upgrade/downgrade 往返、V5.3 行保留、
     单 head、约束生效。
9. **回归**：全量后端（预期 582+新增）、前端 vitest、next build、
   Strict E2E（40/40）。
10. **双轴审查**：Standards Review（规范/边界/敏感信息）+
    Spec Review（18 条验收逐条对照），修复后复审。
11. **交付**：acceptance_report.md、learning_log.md / stage_delivery_log.md 追加、
    提交分支、导出 WorkBuddy Bundle + SHA-256。

## 风险与对策

- **R1 Trial 与 V5.3 evaluation 语义混淆** → Trial 挂 `mode=deterministic_recording`
  与既有报告校验完全兼容；study/trial 关系只存于优化器表，不动 agent_evaluations 结构。
- **R2 并发 ordinal 冲突** → ordinal 由 service 内串行分配 + DB
  `UNIQUE(study_id, ordinal)` 兜底；插入冲突即回滚重试有限次。
- **R3 评测耗时 × 候选数** → 预算默认小（candidates ≤ 64、evaluations ≤ 128、
  deadline 可选），worker 串行消费；评测器实测约 20s/次，测试中用 Recording executor。
- **R4 SQLite 时区/比较** → 全部 datetime 写 UTC aware，与 V5.3 `_aware` 模式一致。
