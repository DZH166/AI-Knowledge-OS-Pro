# Architecture Decision Records

这些 ADR 解释项目为什么这样设计，而不是只记录“用了什么技术”。面试时优先讲取舍，不要背术语。

- [0001 证据身份：revision/index/chunk/hash/locator](0001-evidence-identity.md)
- [0002 可恢复执行：outbox/checkpoint/fence](0002-durable-execution.md)
- [0003 单用户本地优先：SQLite/WAL/FULL](0003-sqlite-local-first.md)
- [0004 真实模式 fail-closed，demo 显式降级](0004-fail-closed-providers.md)
- [0005 dense + sparse RRF 与中文评测](0005-hybrid-retrieval.md)
