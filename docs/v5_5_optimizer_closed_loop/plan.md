# V5.5 实施计划（Plan）

## 复用盘点（已核实）

- V5.3 `SqlAgentPolicy.submit(CreatePolicy)` 已提供幂等 draft 创建
  （`agent_policy_commands.request_id` 唯一回放 + POLICY_IDEMPOTENCY_CONFLICT）。
- `compare_policy_configs(left, right)`（agent_policy/comparison.py）产出
  `PolicyConfigComparison(compatible, incompatibility_reasons, changes)`。
- `GetActivePolicy()` 单 Active 查询已有；wiring `get_agent_policy()` 可注入。
- V5.4A service 已有 `_qualify_rows`/`pareto_frontier`/`inspect_recommendation`
  可复用来判定"是推荐候选"。
- outbox 行复活逻辑在 `recovery.py::_redrive_running_studies` 已有雏形（按 study），
  retry 需要按 trial 收敛。

## 步骤

1. 文档（spec/plan/task/checklist）。
2. TDD 红：`test_v5_5_optimizer_loop_sql.py`（convert/diff/settle/retry/fail）、
   `test_v5_5_optimizer_loop_api.py`（三端点 + 校验）、
   `test_v5_5_optimizer_loop_migration.py`（0012）。
3. Migration 0012：trial 加 `draft_policy_id`（FK + UNIQUE）、`request_id`（UNIQUE 可空）。
4. contracts：`ConvertRecommendation`、`RetryTrial`、`FailStudy`、
   `DiffTrialAgainstActive` 查询与返回类型。
5. service：`convert_to_draft` / `diff_trial_against_active` /
   `_maybe_settle` / `retry_trial` / `fail_study`。
6. API：三端点 + schemas。
7. 测试转绿 → 全量回归 → 前端回归 → E2E 对照。
8. 双轴审查修复 → 文档收尾 → 提交推送 → Bundle。

## 风险与对策

- R1 转换与 V5.3 命令表耦合 → 只调 `submit(CreatePolicy)`，不直接写
  agent_policy_versions，保持审计/幂等由 V5.3 负责。
- R2 retry 与 fence 交互 → retry 只清 pending 前置状态，fence 语义不变；
  outbox 行用 dedupe_key 原样复活，RQ job_id 不变可能残留旧 job——接受
  （RQ SimpleWorker 对重复 job_id 的 enqueue 失败不影响 outbox 重投递）。
- R3 settle 判定与既有 budget-completed 逻辑冲突 → 统一收敛到 `_maybe_settle`，
  替换 `_complete_trial` 内的旧判定，行为兼容（单 trial 预算场景回归覆盖）。
