# V5.6 验收清单（Checklist）

## A. 能力
- [ ] A1 贝叶斯第 1 轮与随机等价；有观测时确定性且引导方向正确。
- [ ] A2 探索率随轮次衰减（下限 0.2）。
- [ ] A3 warm start 继承观测（引用不存在 → 404）。
- [ ] A4 分类别统计落库并可查询；verdict 方向正确。
- [ ] A5 推荐理由含类别摘要。
- [ ] A6 next-round：接续 ordinal、回 running、幂等、预算 409、非 completed 409。

## B. 数据
- [ ] B1 0013 单 head、往返、V5.5 数据保留、新列约束生效。

## C. 边界
- [ ] C1 纯模块零基础设施 import；requirements 零新增。
- [ ] C2 严格校验 + sanitize；provider 恒 0。

## D. 回归
- [ ] D1 既有 636 后端全绿；前端 105；E2E 与基线一致。

## E. 交付
- [ ] E1 文档/日志/提交/推送/Bundle。
