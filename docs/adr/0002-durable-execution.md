# ADR 0002：用 outbox + checkpoint + execution fence 实现可恢复执行

## 背景

Agent run 跨越检索、模型、工具和人工审批。请求断开、Worker 崩溃或用户取消后，迟到的结果不能写回，否则状态会被污染。

## 决定

- 状态变更先落 SQLite，再通过 transactional outbox 派发。
- 每个 run 保存 checkpoint；恢复从最后一个已提交步骤继续，而不是从头重跑。
- 命令带 idempotency key；重复提交返回同一结果。
- 取消推进 epoch；迟到结果携带旧 epoch，写入前被 fence 拒绝。
- 对未知模型结构 fail-closed，不做静默猜测。

## 后果

- 需要更多表和测试，但恢复/取消行为可证明。
- SQLite 单机事务足够；多实例部署需要把 lease/CAS 迁移到 Postgres 或独立协调服务。
