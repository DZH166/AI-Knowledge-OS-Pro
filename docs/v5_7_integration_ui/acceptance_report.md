# 溯知 V5.7 Integration Workbench Acceptance Report

## 结论

V5.7 把 WorkBuddy 交付的 V5.4A–V5.7 后端优化器接入当前产品，并完成前端实验工作台、Run Trace 只读分享、数据库升级兼容和对抗性修复。优化器只运行本地确定性评测，推荐最多生成 Draft，不自动激活策略。

## 已验收能力

- Study / Trial 全生命周期、累计预算、确定性候选和多轮 Bayesian Optimization。
- 策略与评测 Fingerprint 严格绑定；真实 latency 与 60 个精确案例事实持久化。
- Pareto、分类胜负、推荐理由、配置 Diff 和确定性 Markdown 对比报告。
- Outbox、Lease、Fence、恢复、迟到结果拒绝；迁移会回填 V5.6 仍保存的最后一条 next-round 收据，V5.7 起完整保存每条收据。
- 后端声明的 Action、完整 Trial 指标、模板只收窄预算、事件分页和脱敏。
- 独立 AgentRunShare 模块、7 天只读链接、复制、撤销和过期语义。
- `/policies/optimizer` 与 `/policies/optimizer/{studyId}` 无假数据降级工作流。
- Optimizer Facade（优化器统一入口）已把报告、工作台投影、Trial 检查、草稿转换和终止命令拆给独立协作者。

## 最终验证证据

| Gate（质量门） | Result（结果） |
| --- | --- |
| Backend full regression（后端全量回归） | `681 passed, 1 skipped` |
| Optimizer focused regression（优化器聚焦回归） | `99 passed` |
| Frontend unit（前端单元测试） | `32 files / 114 tests passed` |
| Frontend lint / typecheck / build（代码规范、类型、生产构建） | 全部通过；Next.js 生成 37 个静态页面并保留动态路由 |
| Dependency audit（依赖漏洞扫描） | `0 vulnerabilities` |
| Fixed evaluation（固定评测） | `60/60`，全部 Hard Gate 通过，`external_provider_calls=0` |
| Alembic（数据库迁移链） | 单一 Head：`0015_v5_7_integration` |
| Strict E2E（真实服务端到端测试） | `43/43` 连续两次通过 |
| Strict run tokens（隔离运行标识） | `33076-80ffeecb`、`43720-a78a94be` |
| Runtime cleanup（运行资源清理） | 每轮精确移除前端、后端、3 Worker、Redis、Qdrant、SQLite/WAL/SHM |
| Standards / Spec review（规范/需求双轴复审） | `0 / 0 findings` |
| Release Archive（发布归档） | `789 files`，forbidden/missing 均为 0，Manifest 与 Freshness 通过 |
| GitHub branch（远端分支） | `codex/v5.7-integration-ui` 已推送并建立 upstream（上游跟踪） |

归档哈希以仓库外的 `.sha256` sidecar（旁路校验文件）为准；它不写回归档内部，避免哈希自引用。

## 产品边界

- 未配置真实大模型质量基准，不宣称固定评测等于线上模型效果。
- 优化器无法调用激活接口；Draft 到 Active 必须经过既有人工硬门。
- 当前默认单用户本地工作区，不把 SQLite 演示环境描述为生产集群。
