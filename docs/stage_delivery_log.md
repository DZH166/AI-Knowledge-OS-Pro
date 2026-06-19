# AI Knowledge OS Pro 阶段交付记录

这个文件用于记录每个项目阶段结束时的固定交付物。以后每完成一个阶段，都必须同时确认：

- 教学/学习记录已写入 `docs/learning_log.md`，并且只追加不覆盖旧记录。
- 阶段交付记录已追加到本文件。
- 项目源码已打包为 zip，便于归档、回滚和作品集沉淀。
- README 和启动方式已更新到当前真实状态。
- 关键功能已完成验证。

## V1：基础文档 RAG 知识库闭环

### 阶段状态
已完成。

### 教学/学习记录
- 主学习档案：`docs/learning_log.md`
- 当前版本记录：`V1：基础文档 RAG 知识库闭环`
- 记录内容包括：本版本功能、主要文件、AI 应用开发知识点、小白解释、项目用法、补课建议、面试表达和下一版本建议。

### 项目 zip 包
- 打包文件：`releases/AI-Knowledge-OS-Pro-V1-20260611.zip`
- 打包范围：项目源码、前后端配置示例、README、学习档案、路线图、阶段交付记录。
- 排除内容：`.git`、`node_modules`、`.next`、运行数据库、上传文件、缓存文件、临时日志。

### 本阶段验证
- 后端健康检查通过：`GET /health`
- Qdrant Server 已启动并验证：`http://127.0.0.1:6333`
- 前端页面可访问：Dashboard、知识库、上传、问答、文档、文档详情、学习档案。
- `txt / md / pdf` 三种文件上传、解析、切片、向量入库验证通过。
- RAG 问答返回引用来源和相关 chunks，并保存问答历史。
- 前端 `npm run typecheck` 和 `npm run build` 通过。
- 后端 `python -m compileall backend/app` 通过。

### 下一阶段建议
V2 优先做文档治理和学习复盘增强：文档删除、重新索引、标签、学习卡片和错题本雏形。

## V2：真实 RAG 加固、文档治理与项目学习教练闭环

### 阶段 A：备份和现状检查
已完成。

- 检查了当前目录、Git 状态、Python/Node 环境、SQLite 表结构、Qdrant 状态、现有配置、README、学习档案和阶段交付记录。
- 确认当前仓库尚无 commit，V1 文件均为未跟踪文件。
- 确认 SQLite 当前保留 V1 学习记录，业务数据为空；V2 仍按保留已有数据设计迁移。
- 已生成 V2 前备份包：`releases/AI-Knowledge-OS-Pro-V1-before-V2-20260611-035602.zip`。
- 现状检查记录保存在：`docs/v2_current_state_audit.md`。

<!-- stage:v2-real-mode-governance-learning-coach:confirmed -->
## V2 阶段交付：真实模式、文档治理与学习教练

- 已确认 V2 学习包，并追加到 `docs/learning_log.md`。
- 本阶段包含系统诊断、provider adapter、Alembic 迁移、文档治理、索引兼容、RAG 拒答和学习卡片。
- 阶段结尾要求：保留教学记录，并在 release 步骤生成 V2 zip 与 sha256。

<!-- stage:v2-final-delivery -->
## V2 最终交付记录

- 教学记录：已追加到 `docs/learning_log.md`，slug 为 `v2-real-mode-governance-learning-coach`。
- 数据库迁移：已执行 `python -m alembic upgrade head`，当前版本为 `0002_v2_schema`。
- 后端验证：`python -m compileall backend/app` 通过；`python -m pytest` 通过，12 个测试全部通过。
- 前端验证：`npm run typecheck` 通过；`npm run build` 通过。
- 项目归档：已生成 `releases/AI-Knowledge-OS-Pro-V2-20260611.zip` 和对应 `.sha256` 文件。
- 归档排除：依赖目录、构建缓存、密钥文件、SQLite 数据库、上传文件、日志和旧 release 包。

<!-- stage:v2-5-final-delivery -->
## V2.5 ?????????????????????????

### ????
????

### ??/????
- ???? `docs/learning_log.md`?
- ?????????????????????????RAG ????????????????????????

### ?????
- ?????? SQLite ???`releases/AI-Knowledge-OS-Pro-DB-before-V2.5-20260611-133605.zip`?
- ??? `python -m alembic upgrade head`?
- ???? head?`0003_v2_5_product_learning`?

### ????
- `python -m compileall backend/app`????
- `pytest`?15 passed?
- `npm run typecheck`????
- `npm run build`????

### ????
- ?? V2.5 release zip?`releases/AI-Knowledge-OS-Pro-V2.5-20260611.zip`?
- ??????????????SQLite ????????????? release ? `*.tsbuildinfo`?

<!-- stage:v2-5-final-polish-20260611 -->
## V2.5 最终收口交付记录

### 阶段状态
已完成。

### 教学/学习记录
- 已在 `docs/learning_log.md` 追加 `V2.5 最终补充：产品化交互与学习闭环收口`。
- 本次记录覆盖统一 UI 组件库、Chat 学习闭环、异步请求陈旧响应保护和版本学习包生成脚本。
- 历史 V1/V2/V2.5 记录未删除、未覆盖。

### 代码与产品补充
- `frontend/components/ui.tsx`：补齐 Toast、Modal、ConfirmDialog、Drawer、DataTable、FilterBar、Pagination、ActionMenu、FormField、HelpTooltip、CopyButton。
- `frontend/components/KnowledgeChat.tsx`：接入重生成、收藏、保存学习笔记、转学习卡片追问、面试表达追问和停止展示。
- `frontend/app/globals.css`：补齐新交互组件样式。
- `scripts/generate_learning_package.py`：展开未跟踪目录并优先列出复盘关键文件。
- `docs/v2_5_acceptance_report.md`：更新最终验收内容。

### 验证结果
- `python -m compileall backend/app`：通过。
- `pytest`：15 passed。
- `python -m alembic current`：`0003_v2_5_product_learning (head)`。
- `python -m compileall scripts/generate_learning_package.py`：通过。
- `npm run typecheck`：通过。
- `npm run build`：通过。

### 打包要求
- 下一步执行 `scripts/release.py --version V2.5` 重新生成最终 zip 和 sha256。
- 发布包必须继续排除依赖、构建缓存、密钥、SQLite 数据库、上传文件、日志、测试输出和 `*.tsbuildinfo`。

### 最终打包结果
- 已重新生成最终发布包：`releases/AI-Knowledge-OS-Pro-V2.5-20260611.zip`。
- SHA256：`287b807743c560358a95d237c0850237bb5426a61700e7d7948a2c9100cf2c29`。
- zip 清单校验：128 个文件，禁入项 0 个。
- 已确认未包含：`node_modules`、`.next`、虚拟环境、SQLite 数据库、uploads、logs、`.env`、缓存、测试输出、`*.tsbuildinfo`。
<!-- stage:v3-task-multimodal-foundation-20260618 -->
## V3 阶段交付：稳定任务引擎与多模态知识中枢基础

### 阶段状态
已完成 V3 本轮核心交付。

### 教学/学习记录
- 已在 `docs/learning_log.md` 追加 `V3：稳定任务引擎与多模态知识中枢基础`。
- 本次学习记录覆盖 Redis/RQ 后台任务、任务状态机、任务事件表、Worker 心跳、Alembic 迁移、多模态 Source 模型、系统诊断和前端任务中心。
- 历史 V1/V2/V2.5 学习记录未删除、未覆盖。

### 代码与产品交付
- 后端新增 Redis/RQ task broker 和 Worker。
- 后端新增 JobEvent 事件表和 V3 ingestion job 字段。
- 后端新增多模态基础模型与 Alembic `0004_v3_task_multimodal_foundation`。
- 文档上传、重试、重新解析、重建索引改为后台任务化。
- 前端新增 `/tasks` 任务中心。
- 系统状态页新增 Redis 和 Worker 诊断。
- README、架构文档、路线图、任务流文档、V3 验收报告和环境变量示例已更新。

### 数据库与备份
- V3 前数据库备份：`releases/AI-Knowledge-OS-Pro-DB-before-V3-20260612-210458.zip`。
- 备份 SHA256：`e6837b5cf8a5da703cb55633e833b9c286654fd3b301b25ee89663063229e1c8`。
- 已执行 `python -m alembic upgrade head`。
- 当前数据库版本：`0004_v3_task_multimodal_foundation`。
- 当前本地 SQLite 中 `learning_logs` 保留 2 条记录，业务数据为空。

### 验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：19 passed，5 warnings。
- `python -m alembic upgrade head`：通过。
- `python -m alembic current`：`0004_v3_task_multimodal_foundation (head)`。
- `npm run typecheck`：通过。
- `npm run build`：通过，Next.js 构建包含 `/tasks` 页面。

### 本阶段边界
- 已完成多模态数据模型基础。
- 尚未实现真实图片 OCR。
- 尚未实现真实音频转写。
- 尚未实现真实视频关键帧、字幕和时间轴引用。
- 下一阶段应选择一个真实多模态 pipeline 逐步接入，而不是一次性做不可验证的假闭环。

### 打包要求
- 本阶段需要生成 `releases/AI-Knowledge-OS-Pro-V3-YYYYMMDD.zip` 和 `.sha256`。
- release zip 必须排除依赖、缓存、密钥、SQLite 数据库、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 已生成 V3 发布包：`releases/AI-Knowledge-OS-Pro-V3-20260618.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3-20260618.zip.sha256`。
- zip 清单校验：141 个文件，禁入项 0 个。
- 已确认未包含：`node_modules`、`.next`、虚拟环境、SQLite 数据库、uploads、logs、真实 `.env`、缓存、测试输出和 `*.tsbuildinfo`。

<!-- stage:v3-1-image-metadata-ingestion-20260618 -->
## V3.1 阶段交付：图片元数据接入与媒体资料库

### 阶段状态
已完成 V3.1 小阶段核心交付，当前为 metadata-only 图片接入闭环。

### 教学/学习记录
- 已在 `docs/learning_log.md` 追加 `V3.1：图片元数据接入与媒体资料库`。
- 本次学习记录覆盖可信多模态接入、文件哈希去重、Pillow 图片元数据解析、Source/MediaAsset 分层和媒体资料库产品化。
- 历史 V1/V2/V2.5/V3 学习记录未删除、未覆盖。

### 代码与产品交付
- 后端新增图片上传、校验、保存、哈希去重和 Pillow 元数据读取能力。
- 后端新增媒体来源 API：图片上传、来源列表、来源详情。
- 图片入库后创建 `Source`、`SourceRevision` 和 `MediaAsset`。
- 图片元数据明确记录 `ocr_status=not_configured` 和 `vision_description_status=not_configured`，不生成伪 OCR 或伪图像描述。
- 上传页新增图片资料接入面板。
- 前端新增 `/media` 媒体资料库页面。
- 前端新增 `/media/sources/[id]` 媒体来源详情页。
- AppShell 侧边栏新增“媒体资料库”导航入口。
- README、路线图和 V3.1 验收报告已更新。

### 验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：21 passed，6 warnings。
- `npm run typecheck`：通过。
- `npm run build`：通过，Next.js 构建包含 `/media` 和 `/media/sources/[id]`。

### 本阶段边界
- 已完成图片真实元数据接入。
- 尚未实现真实 OCR。
- 尚未实现截图报错识别。
- 尚未实现图像描述模型调用。
- 尚未将图片内容写入向量检索；后续应在真实 OCR/视觉模型接入后生成 `MultimodalChunk` 和 `CitationLocator`。

### 打包要求
- 本阶段需要生成 `releases/AI-Knowledge-OS-Pro-V3.1-YYYYMMDD.zip` 和 `.sha256`。
- release zip 必须排除依赖、缓存、密钥、SQLite 数据库、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 发布包路径：`releases/AI-Knowledge-OS-Pro-V3.1-20260618.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3.1-20260618.zip.sha256`。
- zip 清单需要校验禁入项为 0。

<!-- stage:v3-2-configurable-image-ocr-20260618 -->
## V3.2 阶段交付：可配置图片 OCR 与图片文字检索

### 阶段状态
已完成 V3.2 本轮核心交付。图片可以在配置真实 OCR provider 后提取文字、生成多模态 chunk、进入 Qdrant 检索，并在 Chat 中作为引用来源出现。

### 教学/学习记录
- 已在 `docs/learning_log.md` 追加 `V3.2：可配置图片 OCR 与图片文字检索`。
- 本次学习记录覆盖 OCR provider adapter、真实模式能力边界、MultimodalChunk、CitationLocator 和多模态索引兼容。
- 历史 V1/V2/V2.5/V3/V3.1 学习记录未删除、未覆盖。

### 代码与产品交付
- 后端新增 `backend/app/services/ocr_service.py`。
- 后端新增 OpenAI-compatible vision OCR provider。
- 新增 OCR 配置项并写入 `.env.example`、`backend/.env.example`。
- 新增 `POST /api/media/sources/{source_id}/ocr`。
- 图片 OCR 未配置时返回 `OCR_NOT_CONFIGURED`，不生成伪 OCR 文本。
- OCR 成功后创建新的 `SourceRevision`。
- OCR 文本保存为 `MultimodalChunk`。
- 图片来源定位保存为 `CitationLocator`。
- OCR chunk 生成 embedding 并写入 Qdrant。
- `RAGService` 支持检查并检索 active multimodal index revision。
- 系统状态页新增 OCR provider 诊断。
- 媒体详情页新增“执行真实 OCR”和 OCR 片段展示。
- README、路线图、架构、RAG pipeline、索引兼容文档已更新。

### 验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：23 passed，9 warnings。
- `npm run typecheck`：通过。
- `npm run build`：通过，Next.js 构建包含 `/media/sources/[id]` 的 OCR 操作页面。

### 本阶段边界
- 已完成图片 OCR 可配置真实 provider 和 RAG 检索链路。
- 尚未实现截图报错结构化归档。
- 尚未实现图像描述 caption。
- 尚未实现音频转写。
- 尚未实现视频关键帧、字幕和时间轴引用。

### 打包要求
- 本阶段需要生成 `releases/AI-Knowledge-OS-Pro-V3.2-YYYYMMDD.zip` 和 `.sha256`。
- release zip 必须排除依赖、缓存、密钥、SQLite 数据库、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 发布包路径：`releases/AI-Knowledge-OS-Pro-V3.2-20260618.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3.2-20260618.zip.sha256`。
- zip 清单需要校验禁入项为 0。

<!-- stage:v3-3-screenshot-error-archive-20260618 -->
## V3.3 阶段交付：截图报错识别与报错归档

### 阶段状态
已完成截图 OCR 报错识别、归档、去重、来源追溯和处理状态闭环。

### 教学/学习记录
- 已在 `docs/learning_log.md` 追加 V3.3 教学记录。
- 历史 V1/V2/V2.5/V3/V3.1/V3.2 内容未删除、未覆盖。

### 代码与产品交付
- 新增 ErrorArchive 模型、schema、service、API 和前端页面。
- 新增确定性异常/HTTP/error marker 抽取和无证据拒绝策略。
- 新增来源与 OCR chunk 引用、SHA256 指纹去重和状态流转。
- 图片详情页支持识别并归档报错。
- 新增 `/errors` 报错档案页面。

### 数据库与备份
- V3.3 前数据库备份：`releases/AI-Knowledge-OS-Pro-DB-before-V3.3-20260618-232120.zip`。
- 备份 SHA256：`e0af8c30fb17dbff8c247f84a94dc75429c53b04c4e4b817a6c413bbf0e39c6e`。
- 真实数据库当前版本：`0005_v3_3_error_archive`。
- E 盘临时库 upgrade → downgrade 0004 → upgrade head 验证通过。

### 验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：25 passed，5 warnings。
- `npm run typecheck`：通过。
- `npm run build`：通过，包含 `/errors` 页面。

### 能力边界
- 只从明确 OCR 错误标记创建档案，不虚构根因。
- 图像描述、音频转写、视频关键帧与时间轴仍待实现。

### 打包要求
- 生成 `releases/AI-Knowledge-OS-Pro-V3.3-20260618.zip` 和 `.sha256`。
- 排除依赖、缓存、密钥、SQLite、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 发布包路径：`releases/AI-Knowledge-OS-Pro-V3.3-20260618.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3.3-20260618.zip.sha256`。
- zip 清单必须满足禁入项 0、关键文件缺失 0。

<!-- stage:v3-4-audio-transcription-20260618 -->
## V3.4 阶段交付：音频转写与时间戳引用

### 阶段状态
已完成 MP3/WAV/M4A 上传、真实时长、可配置转写、时间戳片段、向量检索、音频引用和详情页闭环。

### 教学与代码交付
- `docs/learning_log.md` 已追加 V3.4 教学记录，旧记录未覆盖。
- 新增转写 provider、音频上传/播放/转写 API、转写测试和音频前端体验。
- 新增 `docs/audio_transcription.md` 和 V3.4 验收报告。

### 验证结果
- compileall：通过。
- pytest：27 passed，11 warnings。
- typecheck：通过。
- Next.js build：通过。
- Alembic head：`0005_v3_3_error_archive`，无新增 migration。

### 能力边界
- 未配置真实 provider 时不生成伪转写。
- Speaker diarization 仅在 provider 返回 speaker 时保存。
- 视频音轨提取、关键帧和同步播放器仍待实现。

### 打包要求
- 生成 `releases/AI-Knowledge-OS-Pro-V3.4-20260618.zip` 和 `.sha256`。
- 排除依赖、缓存、密钥、SQLite、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 发布包路径：`releases/AI-Knowledge-OS-Pro-V3.4-20260618.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3.4-20260618.zip.sha256`。
- zip 清单必须满足禁入项 0、关键文件缺失 0。

<!-- stage:v3-5-video-pipeline-20260619 -->
## V3.5 阶段交付：视频接入、关键帧与视频时间戳引用

### 阶段状态
已完成 MP4/MOV 上传、真实视频元数据、关键帧、视频播放器、真实转写、时间戳片段、向量检索和视频引用闭环。

### 教学与代码交付
- `docs/learning_log.md` 已追加 V3.5 教学记录，旧记录未覆盖。
- 新增视频上传/转写/关键帧后端闭环，复用已有多模态 schema，无新增 Alembic migration。
- 新增媒体资产文件 API，用于前端展示已登记关键帧。
- 新增视频详情页播放器、关键帧预览、转写操作和时间轴。
- 新增 `backend/tests/test_v3_5_video_transcription.py`。
- 新增 `docs/v3_5_video_pipeline_report.md`。

### 验证结果
- compileall：通过。
- pytest：31 passed，10 warnings。
- typecheck：通过。
- Next.js build：通过。
- Alembic head：`0005_v3_3_error_archive`，无新增 migration。

### 能力边界
- 未配置真实 provider 时返回 `TRANSCRIPTION_NOT_CONFIGURED`，不生成伪字幕。
- 视频没有音轨时拒绝转写。
- 关键帧为真实抽取帧，但尚未做镜头级多关键帧索引。
- 暂未实现 SRT/VTT 字幕导出和播放器点击引用自动 seek。

### 打包要求
- 生成 `releases/AI-Knowledge-OS-Pro-V3.5-20260619.zip` 和 `.sha256`。
- 排除依赖、缓存、密钥、SQLite、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 发布包路径：`releases/AI-Knowledge-OS-Pro-V3.5-20260619.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3.5-20260619.zip.sha256`。
- zip 清单必须满足禁入项 0、关键文件缺失 0。

<!-- stage:v3-6-unified-media-tasks-20260619 -->
## V3.6 阶段交付：统一多模态任务中心与来源学习资产

### 阶段状态
已完成 V3.6 核心交付：文档/媒体统一任务模型、媒体任务编排、引用跳转、媒体详情页交互增强，以及从真实来源 chunk 生成学习资产。

### 教学与学习记录
- 已在 `docs/learning_log.md` 追加 V3.6 学习记录。
- 历史 V1/V2/V2.5/V3/V3.1/V3.2/V3.3/V3.4/V3.5 记录未删除、未覆盖。

### 代码与产品交付
- 新增 Alembic `0006_v3_6_unified_media_tasks`。
- `ingestion_jobs` 支持 `document_id=None`、`source_id` 和 `target_type`。
- 新增统一任务入口和媒体任务服务，支持图片、音频、视频处理任务进入 Task Center。
- 视频支持多关键帧提取和关键帧 OCR/视觉描述任务。
- Chat citation 补齐 `source_id` 与 `document_id`，前端支持跳转到媒体时间戳或文档 chunk。
- 媒体详情页支持播放器 seek、片段高亮、关键帧时间线、任务按钮和学习资料生成。
- 新增 `LearningArtifact` 与 `POST /api/learning/from-source`，只从真实文本来源生成学习资料。
- 新增 V3.6 后端测试覆盖媒体任务和学习资产。

### 验证结果
- `python -m compileall backend/app backend/alembic`：通过。
- `pytest`：39 passed，19 warnings。
- `python -m alembic upgrade head`：通过。
- `python -m alembic current`：`0006_v3_6_unified_media_tasks (head)`。
- `frontend typecheck`：通过。
- `frontend build`：通过。

### 能力边界
- 缺少真实 OCR/视觉/转写 provider 时返回明确 NOT_CONFIGURED 类错误，不生成假 OCR、假视觉描述或假字幕。
- 没有真实 chunk 文本的媒体不能生成学习资料。
- 尚未实现字幕导出、完整镜头级 scene segmentation 和知识图谱。

### 打包要求
- 生成 `releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip` 和 `.sha256`。
- release zip 必须排除 `node_modules`、`.next`、虚拟环境、缓存、`.env`、SQLite 数据库、uploads、logs、旧 release 和 `*.tsbuildinfo`。

### 最终打包结果
- 发布包路径：`releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip`。
- SHA256 文件：`releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip.sha256`。
- SHA256：`0cf83c2c013504b6629603f3823be62a992270cc6a602106bf94d4d87ab981d5`。
- zip 清单校验：173 个文件，禁止项 0。
- 已确认未包含：`node_modules`、`.next`、`.env`、SQLite DB、uploads、logs、旧 release、缓存和 `*.tsbuildinfo`。

### V3.6 final repackage after completion audit
- Rebuilt release package after upload/task UI, learning package automation and additional tests.
- Release path: `releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip`.
- SHA256 file: `releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip.sha256`.
- SHA256: `bde0259289923c44cc44546e4fc50a4c6a184653ca1be5719e0a034d702f45aa`.
- Zip inspection: 175 files, forbidden entries 0.
- Verified exclusions: `node_modules`, `.next`, `.env`, SQLite DB, uploads, logs, old releases, caches and `*.tsbuildinfo`.

### V3.6 final completion audit addendum
- Fixed a stale V2.5 upload error message and V3.6 learning-package confirmation stage text.
- Added a regression test for V3.6 stage delivery append behavior.
- Historical mojibake sections in `docs/learning_log.md` and `docs/stage_delivery_log.md` were preserved append-only; this addendum records the readable V3.6 completion state without rewriting old archive entries.
- Verification after the addendum: compileall passed; pytest `40 passed, 18 warnings`; Alembic current `0006_v3_6_unified_media_tasks (head)`; frontend typecheck passed; frontend build passed.

### V3.6 final release after completion audit addendum
- Release path: `releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip`.
- SHA256 file: `releases/AI-Knowledge-OS-Pro-V3.6-20260619.zip.sha256`.
- Previous regenerated SHA before this note: `bf1db3e543c5c8fab98409b04be1f0bddb4ed4e78efa7f5d0b446a77239a6815`.
- Zip inspection: 175 files, forbidden entries 0 under release exclusion rules.
