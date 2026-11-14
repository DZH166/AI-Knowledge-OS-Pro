# V2 开始前现状检查

检查时间：2026-06-11

## 项目位置
- 当前目录：`<HOME>\Documents\AI Knowledge OS Pro`
- 当前项目确认为 AI Knowledge OS Pro V1，不重新创建项目。

## Git 状态
- 当前分支：`master`
- 当前仓库：尚无 commit
- V1 文件均为未跟踪文件，实施 V2 时不得误删 V1 文件、学习档案或 release 包。

## 运行环境
- Python：`3.13.9`
- 项目后端虚拟环境：`<VENV>`
- Node：`<NODE_HOME>`，版本 `v24.16.0`
- npm：`11.16.0`

## 当前数据库
- SQLite 文件：`backend/data/knowledge_os.db`
- 当前表：`knowledge_spaces`、`documents`、`chunks`、`qa_logs`、`learning_logs`
- 当前业务数据：知识库、文档、chunks、问答历史为空
- 当前学习记录：`learning_logs` 有 V1 记录
- V2 必须使用迁移保留已有数据，不得删除数据库。

## 当前配置与服务
- V1 配置仍使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`CHAT_MODEL`、`EMBEDDING_MODEL`、`ALLOW_LOCAL_MODEL_FALLBACK`
- V1 存在隐式 fallback，需要在 V2 改为显式 `DEMO_MODE=true`
- Qdrant 配置为 `http://localhost:6333`
- 当前检查时 Qdrant 未运行；V1 已提供 Windows Qdrant Server 和 Docker 两种启动说明

## 当前文档
- `docs/learning_log.md`：已有 V1 学习档案，后续只追加不覆盖
- `docs/stage_delivery_log.md`：已有 V1 阶段交付记录
- `README.md`：当前包含本机路径，需要在 V2 改为 GitHub/新电脑友好版本，把本机说明移到 `docs/local_setup_windows.md`

## V2 前备份
- 备份 zip：`releases/AI-Knowledge-OS-Pro-V1-before-V2-20260611-035602.zip`
- 校验文件：`releases/AI-Knowledge-OS-Pro-V1-before-V2-20260611-035602.zip.sha256`

