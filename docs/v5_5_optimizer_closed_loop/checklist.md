# V5.5 验收清单（Checklist）

## A. 闭环能力
- [x] A1 推荐候选可一键转 draft（状态=draft、指纹一致、幂等）。
- [x] A2 转换绝不激活（active 策略前后不变 + 源码零 activate 引用）。
- [x] A3 候选 vs Active 逐字段 diff 可查询。
- [x] A4 Study 收尾正确：全 completed→completed；全失败→failed。
- [x] A5 失败 Trial 可 retry（outbox 复活、预算约束）。
- [x] A6 显式 fail 终止运行中 Study。

## B. 数据与迁移
- [x] B1 0012 迁移单 head、往返对称、V5.4A 数据保留。
- [x] B2 新列约束（UNIQUE draft/request_id）在真实库生效。

## C. 边界与安全
- [x] C1 纯算法模块仍零基础设施 import。
- [x] C2 新端点严格校验（extra=forbid/StrictInt/越界/secret）。
- [x] C3 输出经 sanitize，无敏感信息。

## D. 回归
- [x] D1 聚焦测试全绿；V5.7 最终全量后端 681 passed / 1 skipped。
- [x] D2 前端 32 files / 114 tests 全绿、构建通过。
- [x] D3 Strict E2E 43/43 连续两次通过；旧 routing flake 已由多 Worker 隔离运行器消除。

## E. 交付
- [x] E1 文档齐全；日志追加。
- [x] E2 提交推送 GitHub；Bundle + SHA-256 导出。
