# V5.7 验收报告（Acceptance Report）

日期：2026-09-01
分支：`workbuddy/v5.7-workbench-backend`
基线：`210a9e5fed08be0af0d7afcc8d40f9970edc96f0`（V5.6，未修改）

## 一、交付范围

功能层产品化（纯后端，页面归 V5.4B）：

1. **Study 全景视图**：`GET .../studies/{id}/overview` 一次聚合轮次摘要、
   Trial 紧凑行、Pareto 前沿、推荐摘要与 **actions 可行性列表**（前端无需
   自行推断按钮可用性；含预算判断与已转换检查）。
2. **Study 模板**：`GET /study-templates`（quality_first/balanced/cost_first
   三个服务端常量模板）+ `POST /studies/from-template` 一键创建（复用
   submit 幂等；base_policy_id 显式提供）。
3. **事件流**：`optimization_study_events` 表 + 12 类生命周期事件
   （study_created/started、trial_created/completed/failed/cancelled、
   round_started、recommendation_updated、study_completed/failed/cancelled、
   draft_converted 全部可达）+ 游标分页端点；payload 仅含 ID/计数/指纹摘要。
4. **对比报告导出**：`POST .../export-comparison` 确定性 Markdown
   （逐 Trial 绝对值 + 方向化 best 列、Hard Gate 差异、失败案例、
   2-Trial 分类别胜败表），sha256 校验，contains_sensitive_text 泄漏防护。
5. **Run 只读分享令牌**：`agent_run_share_links` 表（64-hex 高熵 token、
   1–30 天过期、可撤销）+ 3 端点；分享 trace 与直接 trace 同一投影、只读、
   404 不泄露存在性。

## 二、测试数量（准确值）

| 套件 | 结果 |
| --- | --- |
| V5.7 聚焦测试（2 文件） | 16 passed（sql 11 + api 5） |
| 全量后端（最终，清洁环境） | **672 passed, 1 skipped**（V5.6 的 657 全保持 + V5.7 新增 16，另 head 基准测试更新） |
| 前端单元测试 | 28 files, 105 passed |
| 前端构建 | 通过 |
| Strict E2E | 38/40（两个失败均为已知 routing 环境性 flake，与基线一致） |
| 依赖 | requirements.txt 零新增 |

## 三、双轴审查与修复

审查发现 **7 项必须修复**，全部落地：

1. 补齐缺失事件写入点（trial_failed/study_failed[显式]/draft_converted/
   trial_created/trial_cancelled 汇总/recommendation_updated 已核对）。
2. from-template 重复 study_created 事件 → 删除补写逻辑，避免重复行。
3. Protocol 补齐 7 个新方法 + 未 import 的契约名。
4. 删除死代码 `agent_policy/templates.py`。
5. `_append_event` 无效 try/except → 诚实的同事务 all-or-nothing 语义
   （docstring 同步修正）。
6. 导出 delta 与 spec 矛盾 → 修订 spec F4（绝对值 + best 列）并补
   categories 2-Trial 限制说明。
7. 3-Trial 导出静默丢弃第 3 列 → `include_categories=true` 且非 2 个
   Trial 时显式 422。

建议项同步落地：convert-draft action 仅在存在未转换推荐时可用、share body
参数默认 None、未用导入清理、SQL 测试 `__import__` 动态导入清除。

## 四、诚实边界

- 全部为后端功能；页面呈现归 V5.4B。
- 分享 trace 与直接 trace 使用同一投影与脱敏，无新增暴露字段。
- Strict E2E 的 2 个失败为既有 routing 环境性 flake（跨五阶段对照一致）。

## V5.7 Integration Revalidation（2026-09-01）

本报告前文保留 WorkBuddy 当时的历史 checkpoint（检查点），包括旧单 Worker 环境下的 routing flake；
当前发布事实以 V5.7 集成验收为准：后端 `681 passed / 1 skipped`，前端 `32 files / 114 tests`，
固定评测 `60/60` 且外部 Provider 调用为 0，Strict E2E `43/43` 连续两次通过
（tokens：`33076-80ffeecb`、`43720-a78a94be`），每轮隔离进程、容器和数据库均精确清理。
完整证据见 `docs/v5_7_integration_ui/acceptance_report.md`。
