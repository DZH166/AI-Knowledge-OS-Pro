# V5.7 实施计划（Plan）

## 复用盘点
- overview：inspect_pareto/inspect_recommendation/_trial_public_state 已有（重组即可）。
- 模板：submit() 幂等创建；RetrievalPolicyConfig 硬界兜底。
- 事件：outbox 已有事件总线先例；新表同事务追加。
- 导出：compare_evaluations（V5.2）、compare_categories（V5.6）、
  portfolio export-markdown 先例（响应形状）。
- 分享：GetRunTrace 通路 + RunTraceSchema；secrets.token_hex。

## 步骤
1. 文档四件套。
2. TDD 红：workbench_overview/templates/events/export/share 五组测试。
3. Migration 0014（两表）。
4. service：overview/_actions、template 常量 + from_template、事件写入点、
   export_comparison、share link 三方法。
5. 纯模块 report_export.py（markdown 渲染）。
6. API：6 个新端点 + schemas。
7. 转绿 → 全量回归 → 前端 → E2E → 双轴审查 → 交付。

## 风险
- R1 overview 双读不一致（trial 与 pareto 两次查询）→ 同一 session 内完成。
- R2 事件写入侵入既有方法 → 每处仅一行 _append_event 调用，事件失败不阻断
  主流程（内部 try/except 记日志）不掩盖状态变更。
- R3 分享令牌枚举 → 404 统一（不区分无效/过期/撤销）+ token 64 hex 高熵。
