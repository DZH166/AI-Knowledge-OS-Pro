# V5.6 验收清单（Checklist）

## A. 能力
- [x] A1 贝叶斯第 1 轮与随机等价；有观测时确定性且引导方向正确。
- [x] A2 探索率随轮次衰减（下限 0.2）。
- [x] A3 warm start 继承观测（引用不存在 → 404）。
- [x] A4 分类别统计落库并可查询；verdict 方向正确。
- [x] A5 推荐理由含类别摘要。
- [x] A6 next-round：接续 ordinal、回 running、幂等、预算 409、非 completed 409。

## B. 数据
- [x] B1 0013 单 head、往返、V5.5 数据保留、新列约束生效。

## C. 边界
- [x] C1 纯模块零基础设施 import；requirements 零新增。
- [x] C2 严格校验 + sanitize；provider 恒 0。

## D. 回归
- [x] D1 V5.7 最终后端 681 passed / 1 skipped；前端 114；Strict E2E 43/43 双跑。

## E. 交付
- [x] E1 文档/日志/提交/推送/Bundle。
