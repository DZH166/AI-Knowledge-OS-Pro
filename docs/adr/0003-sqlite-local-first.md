# ADR 0003：单用户本地优先，SQLite + WAL + FULL

## 背景

项目定位是个人研究工作台，不是多租户 SaaS。需要简单部署、可备份、可离线演示。

## 决定

- 默认 SQLite，WAL 模式，`synchronous=FULL`，开启外键约束。
- 上传文件与数据库同机保存；备份使用 SQLite online backup + SHA-256 manifest。
- 单进程 Uvicorn + RQ Worker；不假装支持多实例并发写。

## 后果

- 单用户场景简单、可携带、易恢复。
- 并发写和跨机扩展有限；公开部署前需要 Postgres、对象存储和独立队列。
- `FULL` 增加每次提交的 fsync 成本，这是为断电后提交持久性付出的代价。
