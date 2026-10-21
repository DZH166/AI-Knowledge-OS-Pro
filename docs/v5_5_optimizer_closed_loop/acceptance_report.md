# V5.5 验收报告（Acceptance Report）

日期：2026-08-31
分支：`workbuddy/v5.5-optimizer-closed-loop`
基线：`53252cc9c4cfd34508fc483c8fbf2813d6753217`（V5.4A，未修改）

## 一、交付范围

按 V5.5 Spec 完成检索优化器闭环：

1. **Convert To Draft**：推荐候选一键转换为 V5.3 draft 策略（复用
   `SqlAgentPolicy.submit` 幂等创建；四重安全链——Study/Trial 归属、
   completed+推荐排名、**全集 Pareto 前沿成员**、指纹严格重建校验；
   并发双转换以 UNIQUE + IntegrityError 回退实现去重；绝不激活，
   有测试断言 Active 策略前后不变）。
2. **Candidate Diff**：候选 vs 当前 Active 策略逐字段比较
   （复用 `compare_policy_configs`，left=active、right=candidate，
   输出双侧 SHA-256、active 版本、Trial 指标摘要）。
3. **Study 收尾状态机**：`_maybe_settle` 统一收尾——全终态且有 completed
   → completed（混合失败也按 completed）；全失败/全取消 → failed；
   仍有 pending → running。挂载于 execute 完成/失败写回事务内。
4. **失败重试**：failed → pending（outbox 复活，cancel/fail 死信不复活）；
   守卫：仅 running Study 可重试 + 评测预算（started_evaluations <
   max_evaluations）。
5. **显式终止**：`POST .../fail` 将 pending/running Study 置 failed 并终态化
   未完成 Trial。

## 二、测试数量（准确值）

| 套件 | 结果 |
| --- | --- |
| V5.5 聚焦测试（3 文件） | 21 passed（sql 16 + api 3 + migration 2） |
| 全量后端（修复后最终，清洁环境） | **636 passed, 1 skipped**（V5.4A 的 615 全保持 + V5.5 新增 21） |
| 前端单元测试 | 28 files, 105 passed |
| 前端构建 | 通过 |
| Strict E2E | 38/40（与 V5.4A 基线完全一致的两个已知环境 flake，非本阶段回归） |

## 三、双轴审查（单代理合并执行）

- **必须修复 6 项**：retry 缺 Study 状态守卫 + outbox 复活不过滤 cancel 死信；
  convert 前沿校验退化为单 Trial（改为全集求前沿）；retry 预算约束未实现
  （补 started_evaluations 检查）；并发双转换 500（IntegrityError 回退返回既有
  draft）；类型契约失真（union + Protocol 补齐）；spec 补充混合收尾与 replay
  语义。**全部修复**。
- **建议修复**：未用 `func` 导入、死初始化、`hasattr` 死防御改 try/except、
  弱断言两条、StrictFloat、diff-损坏/越界/provider=0 等缺失用例补齐。**全部落地**。

## 四、诚实边界

- 转草稿不激活：激活仍只能走 V5.3 人工硬门。
- 页面（V5.4B）仍归另一个 Agent；本阶段仅后端与 API。
- Strict E2E 的 2 个失败为既有环境 flake（三阶段对照验证）。

## 五、最终交付标识

- 最终提交：`9d0049ee3c55d50e0b3251e4720554052ef2304d`
- GitHub 分支：`workbuddy/v5.5-optimizer-closed-loop`（已推送）
- Bundle SHA-256：见 `releases/AI-Knowledge-OS-Pro-V5.5-WorkBuddy.bundle.sha256`

## V5.7 Integration Revalidation（2026-09-01）

本报告前文保留 WorkBuddy 当时的历史 checkpoint（检查点），包括旧单 Worker 环境下的 routing flake；
当前发布事实以 V5.7 集成验收为准：后端 `681 passed / 1 skipped`，前端 `32 files / 114 tests`，
固定评测 `60/60` 且外部 Provider 调用为 0，Strict E2E `43/43` 连续两次通过
（tokens：`33076-80ffeecb`、`43720-a78a94be`），每轮隔离进程、容器和数据库均精确清理。
完整证据见 `docs/v5_7_integration_ui/acceptance_report.md`。
