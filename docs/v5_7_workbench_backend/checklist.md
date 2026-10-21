# V5.7 验收清单（Checklist）
## A. 功能
- [x] A1 overview 一端点全景 + actions 可行性。
- [x] A2 3 模板目录 + from-template 一键创建（幂等）。
- [x] A3 事件流完整覆盖生命周期 + 游标分页 + 脱敏。
- [x] A4 对比报告导出（确定性 markdown + sha256 + 类别表）。
- [x] A5 分享令牌创建/读取/撤销/过期。
## B. 数据
- [x] B1 0014 单 head、往返、V5.6 数据保留、约束生效。
## C. 边界
- [x] C1 markdown 渲染纯函数确定性；无敏感泄漏。
- [x] C2 新端点严格校验；provider 恒 0。
## D. 回归
- [x] D1 V5.7 最终后端 681 passed / 1 skipped；前端 114；Strict E2E 43/43 双跑。
## E. 交付
- [x] E1 文档/日志/提交/推送/Bundle。
