# ADR 0005：dense + sparse 的 RRF 融合，中文单独评测

## 背景

纯向量检索对精确术语、代码标识符和中文短查询不稳定；纯词法检索又无法处理语义近似。中文没有空格，直接复用英文 tokenizer 会丢召回。

## 决定

- 检索同时执行 dense 与 sparse，使用 reciprocal rank fusion 合并。
- dense 结果必须能映射回当前 active revision 的 canonical chunk；映射不到就丢弃。
- 中文使用 scope-safe 的字符/词法匹配，并维护独立的中文检索评测集。
- 不默认启用 reranker；有真实 HTTP reranker 时才启用，并在报告里标注。

## 后果

- 比单路检索更稳，但候选窗口与融合参数需要评测。
- 当前词法仍是 SQL 候选遍历，不是大规模倒排索引；资料量上来后应迁移 FTS5 或独立索引。
- 中文评测 24 题只能证明当前样本，不证明开放域中文能力。
