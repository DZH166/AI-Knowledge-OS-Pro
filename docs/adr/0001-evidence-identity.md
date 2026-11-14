# ADR 0001：用不可变 revision/index/chunk 表示证据身份

## 背景

普通 RAG 只保存 `source_id + page`。来源更新、重跑或同一文档多版本时，旧回答的引用会指向新内容，无法证明“当时依据的是哪一版”。

## 决定

- 每次摄取创建新的 `SourceRevision`，旧 revision 不原地覆盖。
- 索引写入绑定 `IndexRevision`；chunk 保存 revision、content hash、locator。
- Artifact / citation 固定 revision、chunk、hash 与 locator，而不是只存 source。
- 数据库唯一约束保证每个 Source 最多一个 active revision / active index revision。

## 后果

- 旧 Artifact 可以在来源更新后继续回放到原 revision。
- 存储与查询更复杂，需要补偿、对账和孤儿检查。
- 不适合“只保留最新文本”的极简场景；这是为可审计性付出的成本。
