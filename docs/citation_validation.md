# V2.5 Citation Validation

V2.5 删除了“模型没有引用时强行使用第一条检索结果”的逻辑。

规则：

- 只有答案文本里真实出现 `[1]`、`[2]` 等有效编号，才会进入 `used_citation_ids`。
- 如果检索到了资料但回答没有有效引用，`retrieval_status` 返回 `citation_validation_failed`。
- 引用会携带文档名、chunk、相似度、PDF 页码、Markdown 标题路径。
