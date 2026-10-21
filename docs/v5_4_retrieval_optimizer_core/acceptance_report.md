# V5.4A 验收报告（Acceptance Report）

日期：2026-08-31
分支：`workbuddy/v5.4a-retrieval-optimizer-core`
基线：`062cf05cd23631488704915b62b6cbf1b6a22802`（V5.3，未修改）

## 一、交付范围

按任务书完成 V5.4A Offline Retrieval Optimizer Core（离线检索策略优化器核心）：
Optimization Study、Candidate Generation、Durable Trial Execution、
Multi-objective Scoring、Pareto Frontier、Recommendation Engine、
Cancellation/Recovery/Fencing、严格校验 API，以及六份阶段文档。
未开发任何视觉页面（留给 V5.4B）。

## 二、测试数量（准确值）

| 套件 | 结果 |
| --- | --- |
| V5.4A 聚焦测试（5 个文件） | 31 passed |
| 全量后端（最终验证，清洁环境） | 615 passed, 1 skipped（基线 582+1 全部保持；新增 31 条 + 2 条迁移 head 基准更新） |
| 前端单元测试 | 28 files, 105 passed（与基线一致） |
| 前端构建 | `next build` 通过 |
| Strict E2E | 38 passed / 2 failed（环境性 flake，见第四节） |
| 固定评测 | 60/60 通过，external_provider_calls = 0（直接运行评测器验证） |
| 依赖漏洞扫描 | pip-audit：No known vulnerabilities found |
| 编码检查 | check_encoding：707 个 UTF-8 文本文件通过 |

说明：全量后端 615 = V5.3 基线 582（+1 skipped 保持）+ V5.4A 新增 31 条
+ 因 Alembic head 推进而更新的 2 条既有迁移基准测试（`test_v5_migration_clis`、
`test_v5_migrations` 中的 head 断言）。

## 三、双轴代码审查

### Standards Review（编码规范审查）

- Blocker 1 项：`submit()` 在事务块外访问 commit 后的 ORM 对象
  （生产 `expire_on_commit` 默认下触发 DetachedInstanceError）。已修复：
  在事务内提取局部变量后返回。
- Major 7 项：pareto/recommendation 持久化被隐式回滚；读查询 status 类型
  错误与 `.value` 调用；搜索空间反转/超硬边界/零权重在路由层以
  OptimizerInputError 逃逸为 500；`EvaluationExecutionError` 错误码丢失；
  取消标记魔法字符串跨模块耦合；模型缺迁移已有 CHECK。全部修复。
- Minor/Nit 15 项：死代码（`expire_orphan_evaluations`、`metric_value`、
  `RunProcess`、`ExecutableOptimizer`）、N+1 查询、未用导入、内联 execute
  端点移除、recover 按 study 收敛、deadline 经 API 可设并前置检查等。
  全部修复。
- 剩余问题：0（必须修复清单已清空；Nit 级建议项 26/28 随批次落地，
  未发现遗留缺陷）。

### Spec Review（需求实现审查）

- 必须修复 5 项：
  1. `POST /trials/{id}/execute` HTTP 内联评测 → 已移除端点，执行只走
     outbox → RQ worker 路径；spec.md 已补充 start 端点说明。
  2. `recommendation_json` 恒 NULL → 已随 rank 一同持久化完整推荐理由。
  3. 评分基于完成时刻部分集合 → 引入 `_rescore_study` 全集重评分，
     先完成 Trial 的 score 在全集上保持可比。
  4. 零权重/反转边界 500 → schema `model_validator` 前置拦截，422。
  5. 迁移缺 `external_provider_calls` CHECK → 已补入 0011；
     模型补齐 `is_baseline`/`dominated` CHECK 消除 schema 漂移。
- 建议修复 3 项：cancel 允许 running Trial 跑完（含新增 SQL 测试）、
  `_canonical` 加 `allow_nan=False`、验收 #12 指纹不匹配 SQL 测试补齐。
  全部落地。
- 剩余问题：0（必须修复清单清空）。

## 四、Strict E2E 说明（诚实边界）

Strict E2E 结果为 38/40。两个失败用例：
- `v5-2-agent-control.spec.ts`「opens a terminal production Agent trace…」
- `v5-3-agent-policy.spec.ts`「creates, simulates, evaluates, activates…」

失败原因均为 agent run 状态停留在 `routing` 未达 terminal（60s 轮询超时）。
为排除本阶段回归嫌疑，将工作区完整 stash 后在**未修改的 V5.3 基线**上
重跑 Strict E2E，得到完全相同的 2 failed / 38 passed 与相同失败原因；
V5.4A 分支共复跑两次亦一致。本分支对 frontend/、e2e/ 零改动（git diff 为空）。
结论：这是本机环境相关的既有 flake（单 RQ worker 与 4 并发 Playwright
worker 下的 agent.run 推进链路时序问题），非 V5.4A 回归。
已记录于 stage_delivery_log，建议下一阶段处理运行时环境。

## 五、明确不做（本阶段边界）

- 页面视觉、CSS、图表视觉、多媒体界面 → V5.4B。
- 未查看/生成/修改任何图片、截图、视频。
- 未配置真实模型、未添加任何 API Key。
- 未自动激活任何推荐策略（推荐器无激活路径，有测试锁定）。
- 未修改 `codex/v5.3-adaptive-policy-retrieval` 分支与 V5.3 既有测试语义。

## 六、交付物清单

- 代码：`backend/app/modules/agent_policy_optimizer/`（10 文件）、
  `models/optimizer.py`、`alembic/versions/0011_v5_4_retrieval_optimizer.py`、
  `api/routes_optimizer.py`、`schemas/optimizer_schema.py`、
  `tasks/optimizer_tasks.py`，及 task_broker/outbox_dispatcher/worker/main/router 接线。
- 测试：`backend/tests/test_v5_4a_optimizer_{pure,sql,api,worker,migration}.py`。
- 文档：本目录六份；`docs/learning_log.md`、`docs/stage_delivery_log.md` 追加段。
- WorkBuddy Bundle：`releases/AI-Knowledge-OS-Pro-V5.4A-WorkBuddy.bundle`
  - SHA-256：见 `releases/AI-Knowledge-OS-Pro-V5.4A-WorkBuddy.bundle.sha256`（因哈希自引用效应，以导出时的 sidecar 文件为准）
  - 最终提交：`5356e975df19cfb4b303b10b38d0ff36321583bb`
