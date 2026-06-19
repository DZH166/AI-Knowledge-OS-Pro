# V2.5 Version Learning Package

版本学习包不再依赖硬编码 `V2_PACKAGE`。

新流程：

1. 运行 `python scripts/generate_learning_package.py --version V2.5`。
2. 脚本收集 Git 状态、变更文件、后端路由和测试摘要。
3. 生成 `docs/v2_5_learning_package_draft.json`。
4. 后端 `POST /api/learning/packages/generate-draft` 读取草稿。
5. 用户确认后追加 `docs/learning_log.md` 和 `docs/stage_delivery_log.md`。
