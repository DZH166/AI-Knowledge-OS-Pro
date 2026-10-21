# V5.5 验收清单（Checklist）

## A. 闭环能力
- [ ] A1 推荐候选可一键转 draft（状态=draft、指纹一致、幂等）。
- [ ] A2 转换绝不激活（active 策略前后不变 + 源码零 activate 引用）。
- [ ] A3 候选 vs Active 逐字段 diff 可查询。
- [ ] A4 Study 收尾正确：全 completed→completed；全失败→failed。
- [ ] A5 失败 Trial 可 retry（outbox 复活、预算约束）。
- [ ] A6 显式 fail 终止运行中 Study。

## B. 数据与迁移
- [ ] B1 0012 迁移单 head、往返对称、V5.4A 数据保留。
- [ ] B2 新列约束（UNIQUE draft/request_id）在真实库生效。

## C. 边界与安全
- [ ] C1 纯算法模块仍零基础设施 import。
- [ ] C2 新端点严格校验（extra=forbid/StrictInt/越界/secret）。
- [ ] C3 输出经 sanitize，无敏感信息。

## D. 回归
- [ ] D1 聚焦测试全绿；全量后端 ≥615 全绿。
- [ ] D2 前端 105 全绿、构建通过。
- [ ] D3 Strict E2E 与 V5.4A 基线结果一致（38/40 flake 不新增）。

## E. 交付
- [ ] E1 文档齐全；日志追加。
- [ ] E2 提交推送 GitHub；Bundle + SHA-256 导出。
