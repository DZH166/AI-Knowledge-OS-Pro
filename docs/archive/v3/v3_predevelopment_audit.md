# AI Knowledge OS Pro V3 前置审计

生成时间：2026-06-12 21:05:00
阶段：A. V3 前审计和备份

## 结论摘要
- 当前项目位于 `<HOME>\Documents\AI Knowledge OS Pro`，已切换到 V3 分支 `feature/v3-multimodal-knowledge-hub`。
- 当前仓库尚无任何 commit，所有项目文件仍是未跟踪状态；因此 V3 的真实 from-ref/to-ref 学习包无法基于 tag/commit 生成，必须先建立基线 commit 或 tag 后才能满足 V3 学习包要求。
- SQLite 运行数据库存在，V2.5 head 为 `0003_v2_5_product_learning`，业务资料为空，学习系统数据存在。
- V2.5 仍使用 daemon Thread 做后台处理，取消状态存在内存集合 `_cancelled_jobs`，Web 进程重启会丢失取消和运行状态。
- V2.5 重新解析/重试会先删除旧 chunks 和 Qdrant points，再尝试新解析，存在失败后旧索引不可用风险。
- V2.5 `0001_v1_baseline.py` 和 `0002_v2_schema.py` 的 downgrade 为空，不满足 V3 完整回滚要求。
- Chat session 保存了消息，但 RAG prompt 当前只使用当前问题和检索资料，没有真实传入最近 N 轮历史上下文。
- 学习包脚本当前仍写死 implemented_features、knowledge_points、面试表达等模板内容，不满足 V3 “真实 Git ref diff”要求。
- Qdrant 当前无法连接；Docker CLI 可用，但本机 Redis、FFmpeg、FFprobe 未进入 PATH。
- 前端 `npm run typecheck` 和 `npm run build` 当前通过；发布 zip 清单校验未发现运行数据库、密钥、缓存和构建产物。
- `docs/stage_delivery_log.md` 存在历史乱码段，V3 需要修复为 UTF-8 可读内容，同时保留历史语义，不覆盖学习档案。

## 1. Git 状态
- 当前分支：`feature/v3-multimodal-knowledge-hub`
- Commit：当前分支无 commit。
- Tag：未发现可用于 from-ref/to-ref 的 tag。
- 工作区：`.env.example`、`.gitignore`、`README.md`、`alembic.ini`、`backend/`、`docs/`、`frontend/`、`scripts/`、`releases/` 等均未跟踪。

## 2. 数据库版本和数据量
- 数据库：`sqlit<PROJECT_ROOT>/backend/data/knowledge_os.db`
- Alembic current：`0003_v2_5_product_learning (head)`
- 表和数据量：
  - `alembic_version`: 1
  - `chat_messages`: 0
  - `chat_sessions`: 0
  - `chunks`: 0
  - `documents`: 0
  - `ingestion_jobs`: 0
  - `knowledge_points`: 7
  - `knowledge_spaces`: 0
  - `learning_cards`: 7
  - `learning_logs`: 2
  - `learning_notes`: 0
  - `learning_progress`: 1
  - `onboarding_states`: 1
  - `qa_logs`: 0
  - `quiz_questions`: 7
  - `version_learning_packages`: 1

## 3. 备份
- V3 前数据库备份：`releases/AI-Knowledge-OS-Pro-DB-before-V3-20260612-210458.zip`
- SHA256：`e6837b5cf8a5da703cb55633e833b9c286654fd3b301b25ee89663063229e1c8`
- 备份只包含 SQLite 数据库，不包含 API Key。

## 4. Qdrant、Redis、Docker、FFmpeg
- Qdrant：`http://127.0.0.1:6333/collections` 当前无法连接。
- Docker：Docker CLI 可用，Docker Compose 可用；读取 Docker config 时出现 `Access is denied` 警告，需要后续验证 Docker Desktop 状态。
- Redis：`redis-server` 未进入 PATH；V3 应通过 Docker Compose 增加 redis 服务，避免依赖本机安装。
- FFmpeg/FFprobe：未进入 PATH；V3 应提供 `docs/local_setup_windows.md` 安装说明，并在系统能力检测中显示缺失。

## 5. Python、Node、npm
- Python：3.13.9，虚拟环境位于 `<VENV>`。
- Node：`<NODE_HOME>\node.exe`，版本 v24.16.0。
- npm：通过 `<NODE_HOME>\corepack.cmd npm --version`，版本 11.16.0。

## 6. 当前验证结果
- `python -m compileall backend/app`：通过。
- `pytest`：未能开始执行测试；失败原因是系统临时目录不可用，pytest capture 创建临时文件失败。V3 应显式创建项目隔离临时目录并设置 `TMP/TEMP/PYTEST_DEBUG_TEMPROOT`。
- `npm run typecheck`：通过。
- `npm run build`：通过。
- V2.5 release zip：128 个文件，禁入项 0 个。

## 7. Alembic 行为
- 当前 head：`0003_v2_5_product_learning`。
- `0003_v2_5_product_learning.py` 有部分 downgrade。
- `0001_v1_baseline.py` downgrade 为空。
- `0002_v2_schema.py` downgrade 为空。
- 不满足 V3：`empty -> head`、`head -> previous`、`downgrade base`、`base -> head` 的完整回滚验证。

## 8. 当前任务处理风险
- `backend/app/services/ingestion_service.py` 使用 daemon Thread：`Thread(..., daemon=True)`。
- 取消状态只存在 `self._cancelled_jobs: set[int]` 内存集合。
- `_set_job()` 只 `db.flush()`，中间进度未独立 commit，其他连接不一定实时可见。
- 后端重启后 queued/running 任务没有恢复策略。
- running 任务异常中断后没有 `interrupted` 状态识别。
- 批量删除当前逐个调用 `delete_document()`，每条独立 commit，不满足事务化批量删除要求。

## 9. 当前安全重建风险
- `process_document(..., mode in {reparse, retry})` 会先执行 `_clear_existing_index()`。
- `_clear_existing_index()` 会删除 Qdrant points 并删除旧 chunks。
- 如果新解析、Embedding 或 Qdrant 写入失败，旧可用索引已经被破坏。
- V3 必须引入 SourceRevision、ChunkRevision、IndexRevision 和 staging/active 切换。

## 10. 当前 Chat 与 RAG
- Chat session 保存 user/assistant 消息。
- `ask_in_session()` 调用 `rag_service.ask_question(space_id, question, answer_mode)`，没有传入历史消息、会话摘要或选中片段。
- 当前没有 SSE stream API，停止生成主要是前端停止展示，不是后端取消。

## 11. 当前学习包脚本
- `scripts/generate_learning_package.py` 可以扫描 Git status 和路由。
- 仍写死 V2.5 的 implemented_features、knowledge_points、review_suggestions 和 interview_expression。
- 不支持 `--from-ref`、`--to-ref`、`--build-report`、`--migration-report`、`--output`。
- 没有 Git ref 时不会明确失败。

## 12. 当前前端信息架构
- AppShell 中仍有多个导航指向相同路由：会话记录 -> `/chat`，知识点/学习笔记 -> `/learning`，练习中心 -> `/learning/cards`，设置 -> `/system`。
- V3 要新增 `/sources`、`/media/images`、`/media/audio`、`/media/videos`、`/tasks`、`/chat/sessions`、`/learning/knowledge-points`、`/learning/quizzes`、`/learning/notes`、`/learning/versions`、`/settings` 等独立页面。

## 13. V3 第一阶段建议
优先顺序：
1. 修复 Alembic 0001/0002 downgrade 和迁移测试脚本。
2. 增加编码检查脚本，修复 stage_delivery_log 乱码。
3. 增强 IngestionJob 字段和 JobEvent 表，为 Redis Worker 做数据库地基。
4. 增加 Redis 配置和 Docker Compose redis 服务。
5. 引入 Source/Revision/MultimodalChunk/CitationLocator 数据模型和 V3 migration，但先保留 Document 兼容层。
6. 改造学习包脚本为真实 Git ref diff，当前无 commit 时明确失败。

## 14. 未验证或待后续验证
- Docker Compose redis/qdrant 真实启动尚未验证。
- FFmpeg/FFprobe 尚未安装或未进 PATH。
- Docling、faster-whisper、OCR、Vision Provider 尚未接入。
- CI 尚未创建。
- SSE 流式回答尚未实现。
