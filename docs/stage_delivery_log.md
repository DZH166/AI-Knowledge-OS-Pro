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

<!-- stage:v3-6-github-portfolio-release-20260621 -->
## V3.6 阶段交付：GitHub 作品集与安全发布收口

### 阶段状态
V3.6 已完成 GitHub 作品集化收口：专业 README、真实 CI、项目规范、UTF-8 与版本检查、隔离演示数据、自动截图、媒体任务 API 契约修复、真实 Git 差异学习包和安全 release 流程均已落地。

### 交付证据
- 第一阶段提交：`9dca572 feat: complete V3.6 portfolio release`。
- 展示截图：Dashboard、上传中心、知识问答、媒体库、视频详情、学习档案、任务中心，共 7 张 `1440 x 960` PNG。
- 展示 API：dashboard summary、ingestion jobs、learning logs、chat history、chat sessions 均返回 HTTP 200。
- 视频展示：3 个带 `timestamp_ms` 的关键帧、时间戳跳转按钮和高亮转写片段。
- 学习包：基于 `ba4166f..9dca572`、42 个变更文件、79 条 API 路由及真实验证结果生成。

### 验证结果
- compileall：通过。
- pytest：41 passed，18 warnings。
- Alembic fresh upgrade/current：`0006_v3_6_unified_media_tasks (head)`。
- frontend typecheck/build：通过。
- encoding/version check：通过。
- release inspection：199 files，forbidden=0，missing=0。

### 发布边界
- 未配置真实 provider 时继续返回明确 NOT_CONFIGURED 类错误，不生成假 OCR、假视觉描述、假字幕或假回答。
- 合成展示数据库与媒体位于被忽略目录，不进入 Git 或 release zip。
- 发布器只选择当前仓库 Git 跟踪文件，并排除 `.env`、数据库、uploads、logs、`node_modules`、`.next`、缓存、嵌套仓库和本地代理元数据。
- 最终摘要以 `releases/AI-Knowledge-OS-Pro-V3.6-20260621.zip.sha256` 为权威，不在归档内文档写入自引用哈希。

<!-- stage:v3-7-github-showcase-demo-20260701 -->
## V3.7 阶段交付：GitHub 作品集、一键 Demo 与工程可信度

### 阶段状态
已完成 V3.7 GitHub 作品集化收口：README、Demo seed、Demo readiness、secret/repo-clean 检查、release dry-run、架构图、简历表达、系统能力矩阵和 CI 质量门均已落地。

### 代码与文档交付
- 创建开发分支：`feature/v3.7-github-showcase-demo`。
- 新增 `docs/v3_7_predevelopment_audit.md` 和 `docs/v3_7_acceptance_report.md`。
- 新增 `docs/demo_script.md`、`docs/architecture_diagram.md`、`docs/resume_pitch.md`、`docs/github_release_checklist.md`。
- 新增 `docs/assets/demo/README.md`，README 不引用尚未捕获的 GIF，避免破图。
- 新增 Demo 脚本：`scripts/setup_demo.py`、`scripts/seed_demo_data.py`、`scripts/check_demo_ready.py`。
- 新增安全脚本：`scripts/check_secrets.py`、`scripts/check_repo_clean.py`。
- 增强 `scripts/release.py --dry-run`，输出 included/excluded counts 和 secret/database/uploads/cache 风险项。
- 系统状态页新增能力矩阵，明确真实 Provider 和本地服务依赖。

### 验证结果
- compileall：通过。
- pytest：44 passed，19 warnings。
- frontend typecheck：全局 `npm` 不在当前 PowerShell PATH；使用 bundled Node + 项目本地 TypeScript CLI 通过。
- frontend build：全局 `npm` 不在当前 PowerShell PATH；使用 bundled Node + 项目本地 Next.js CLI 通过。
- encoding check：通过。
- secret check：通过。
- repo clean check：通过。
- release dry-run：通过，included_files=213，excluded_files=0，secrets/database/uploads/cache 均为 no。
- demo seed/readiness：通过，创建 synthetic `demo_showcase.db`，包含知识库、文档、图片/音频/视频记录、任务、问答、学习卡片和学习档案。

### 能力边界
- Demo 数据为合成样例，不代表真实 provider 输出。
- 未配置真实 LLM/Embedding/OCR/Transcription provider 时继续明确拒绝，不生成假回答、假 OCR、假转写或假学习资料。
- Docker Compose 当前启动 Redis/Qdrant 依赖服务，不是完整生产部署。
- Demo GIF 尚未录制，README 使用脚本和占位目录说明。

### 建议发布信息
- 建议 commit message：`feat: add V3.7 GitHub showcase demo workflow`。
- 建议 tag：`v3.7.0`。
- 建议 GitHub Release 标题：`AI Knowledge OS Pro V3.7 - GitHub Showcase Demo and Engineering Trust`。

<!-- stage:v3-8-portfolio-demo-docs-20260702 -->
## V3.8 阶段交付：GitHub 作品集 Demo 文档化与可重置演示流程

### 阶段状态
已完成 V3.8 阶段收口：版本统一、V4.0 长期预审计、GitHub 文档地图、可重置 synthetic demo 数据、面试问答、V4.0 目标设计文档、学习包 Markdown 输出和本地验证均已落地。

### 代码与文档交付
- 创建长期开发分支：`feature/v4.0-knowledge-portfolio-os`。
- 新增 `docs/v4_0_long_run_predevelopment_audit.md`，真实记录 V3.7 基线和 V4.0 缺口。
- 新增 V3.8 验收与测试报告：`docs/v3_8_acceptance_report.md`、`docs/v3_8_test_report.md`。
- 新增 `docs/v3_8_learning_package_draft.md`，由当前真实 working tree diff、路由快照和验证报告生成。
- 新增 quickstart、demo mode、本地开发、环境变量、部署、Docker、发布流程、版本、提交规范和文档质量检查文档。
- 新增 RAG、多模态、媒体、任务队列、引用定位、引用跳转和学习闭环流程文档。
- 新增 RAG 评估、混合检索、代码仓库接入、作品集系统、模拟面试、可观测性和性能说明设计文档，全部标明当前状态与限制。
- 新增 `scripts/reset_demo_data.py`，并补充路径安全测试，防止误删非 Demo 数据库。
- 泛化 `scripts/generate_learning_package.py`，支持 Markdown 输出和版本通用学习包元信息。

### 验证结果
- compileall：通过。
- pytest：46 passed，22 warnings。
- frontend typecheck：通过。
- frontend build：通过，15 个 App Router 页面构建成功。
- encoding check：通过，235 个 UTF-8 文本文件。
- secret check：通过，233 个 tracked text 文件 findings=0。
- repo clean check：通过。
- version check：通过，`V3.8 / 3.8.0`。
- release dry-run：通过，included_files=244，secrets/database/uploads/cache 均为 no。
- demo reset/readiness：通过。

### 能力边界
- V3.8 没有声称完成 hybrid retrieval、RAG evaluation、code repository ingestion、portfolio APIs、interview session 或 observability page。
- 上述能力已作为 V4.0 目标文档化，等待后续真实实现、测试和验收。
- Demo 数据继续保持 synthetic 标识，不冒充真实 LLM/OCR/transcription provider 输出。
- 未配置 provider 时仍必须明确拒绝，不生成假回答、假 OCR、假转写或假学习资料。

### 下一阶段
- V3.9：实现 `scripts/evaluate_rag.py --demo`、轻量 UI smoke checks、provider diagnostics 和任务中心体验质量门。
- V4.0：实现代码仓库接入、混合检索、作品集生成、模拟面试和可观测性页面。

<!-- stage:v3-9-quality-gates-in-progress-20260702 -->
## V3.9 进行中交付：RAG Demo 评估与前端 Smoke 质量门

### 阶段状态
V3.9 已启动质量门建设，但尚未最终验收。当前完成 RAG demo evidence-chain evaluation、frontend smoke check、CI 接入和 raw metadata UI 收口。

### 交付内容
- 新增 `scripts/evaluate_rag.py --demo`，不调用 provider，只验证 synthetic demo evidence 和 citation plumbing。
- 新增 `scripts/check_frontend_smoke.py`，检查关键页面、导航目标和 raw/debug UI 文案。
- 新增 `backend/tests/test_v3_9_rag_evaluation.py` 和 `backend/tests/test_v3_9_frontend_smoke.py`。
- CI backend job 增加 demo seed、readiness 和 RAG evaluation；quality job 增加 frontend smoke。
- 系统状态页和媒体详情页不再直接展示 metadata JSON，改为可读摘要。
- 系统状态页新增能力配置向导，使用占位 env 示例并强调缺 provider 时必须明确拒绝。
- 任务中心新增恢复建议，帮助用户区分 provider 配置、Worker 中断、索引服务和取消后重试等处理路径。
- 新增 `docs/v3_9_quality_gate_report.md`。

### 验证结果
- 全量 pytest：49 passed，22 warnings。
- V3.9 targeted tests：3 passed。
- RAG demo evaluation：通过，1 条 QA、1 个时间戳 citation、7 个 multimodal chunks、7 个 citation locators。
- Frontend smoke：通过，4 个导航复用 warning。
- Frontend typecheck/build：通过。
- encoding check：通过，241 个 UTF-8 文本文件。
- secret check：通过，239 个 tracked text 文件 findings=0。
- release dry-run：通过，included_files=250，secrets/database/uploads/cache 均为 no。

### 能力边界
- 这不是最终 V3.9 验收。
- Demo RAG 评估不代表真实 LLM 质量。
- Frontend smoke 不是浏览器 E2E 测试。
- 当前导航复用 warning 会在 V4.0 UI/UX 信息架构阶段继续拆分。

<!-- stage:v3-9-navigation-ia-split-20260702 -->
## V3.9 进行中交付：导航信息架构拆分与 Smoke 门禁升级

### 阶段状态
V3.9 继续推进产品体验质量门：已将重复导航入口拆成独立页面，并让 smoke 检查在发现重复导航目标时直接失败。V3.9 尚未最终验收，版本号继续保持 `V3.8 / 3.8.0`。

### 交付内容
- 新增 `/chat/history` 会话记录页面，展示多轮会话与最近问答。
- 新增 `/learning/knowledge-points` 知识点列表页面。
- 新增 `/learning/quizzes` 练习中心页面。
- 新增 `/learning/notes` 学习笔记页面，支持手动保存笔记。
- 新增 `/system/settings` 设置说明页面，强调 Provider、Demo 模式和发布安全边界。
- 更新 AppShell 导航，消除 `/chat`、`/learning`、`/learning/cards`、`/system` 的重复菜单目标。
- 更新 frontend smoke 脚本和测试，覆盖 19 个必检路由，并要求 `warnings=0`。

### 验证结果
- compileall：通过。
- 全量 pytest：49 passed，21 warnings。
- V3.9 frontend smoke targeted test：1 passed。
- Frontend smoke：通过，required_routes=19，nav_targets=16，warnings=0。
- Frontend typecheck/build：通过。
- encoding check：通过，246 个 UTF-8 文本文件。
- secret check：通过，findings=0。
- repo clean check：通过。
- version check：通过，`V3.8 / 3.8.0`。
- RAG demo evaluation：通过。
- release dry-run：通过，secrets/database/uploads/cache 均为 no。

### 能力边界
- 新页面当前是轻量收口页，主要复用已有 API 和空状态；学习路线、作品集、模拟面试和可观测性仍属于后续 V4.0 增强范围。
- Demo/真实模式边界不变：未配置 provider 时必须明确拒绝，不生成假回答、假 OCR 或假转写。

<!-- stage:v4-0-portfolio-summary-start-20260702 -->
## V4.0 起步交付：作品集概览 API、求职页面与可观测性入口

### 阶段状态
V4.0 知识增强与求职作品集方向已开始真实实现。当前完成 portfolio summary API、作品集求职页面、可观测性入口和 smoke 覆盖；自动简历生成、模拟面试反馈、代码仓库接入和混合检索仍在后续阶段。

### 交付内容
- 新增 `backend/app/schemas/portfolio_schema.py`。
- 新增 `backend/app/services/portfolio_service.py`，聚合真实数据库计数和能力边界。
- 新增 `backend/app/api/routes_portfolio.py`，公开 `GET /api/portfolio/summary`。
- 新增 `backend/tests/test_v4_0_portfolio_summary.py`，覆盖聚合逻辑和 API 响应契约。
- 新增 `/portfolio`、`/portfolio/resume`、`/portfolio/interview`、`/portfolio/project-review` 页面。
- 新增 `/system/observability` 页面，明确 request/task/retrieval trace 的当前状态与后续接入边界。
- 更新 AppShell，增加“作品集求职”导航组和可观测性入口。
- 更新 frontend smoke，覆盖 24 个必检路由。

### 验证结果
- compileall：通过。
- 全量 pytest：51 passed，22 warnings。
- V4.0 portfolio + V3.9 smoke targeted tests：3 passed。
- Frontend smoke：通过，required_routes=24，nav_targets=21，warnings=0。
- Frontend typecheck/build：通过，25 个 build entries（含 `_not-found`）。
- encoding check：通过，255 个 UTF-8 文本文件。
- secret check：通过，findings=0。
- repo clean check：通过。
- version check：通过，`V3.8 / 3.8.0`。
- RAG demo evaluation：通过。

### 能力边界
- 当前 portfolio 页面展示的是 deterministic project facts，不是 LLM 生成内容。
- 自动生成简历、面试问答和项目复盘必须后续接入真实 provider；未配置时应返回 NOT_CONFIGURED 类拒绝。
- 可观测性页面当前是入口和字段边界，结构化 retrieval/provider trace 仍待实现。

<!-- stage:v4-0-hybrid-retrieval-start-20260702 -->
## V4.0 起步交付：轻量混合检索与 Rerank 降级边界

### 阶段状态
V4.0 知识增强主线继续推进：RAGService 已从单一路径检索升级为 lightweight hybrid retrieval。当前实现覆盖 dense + keyword fusion、trace 字段和 rerank 未配置降级；完整 FTS/BM25、真实 rerank provider 和前端 debug panel 仍在后续阶段。

### 交付内容
- 新增 `backend/app/services/hybrid_retriever.py`。
- 新增 `backend/app/services/rerank_provider.py`。
- 更新 `backend/app/services/rag_service.py`，通过 HybridRetriever 获取候选证据。
- 更新 `backend/app/schemas/chat_schema.py` 和 `frontend/types/api.ts`，支持可选检索 trace 字段。
- 新增 `backend/tests/test_v4_0_hybrid_retrieval.py`。
- 更新 `docs/hybrid_retrieval.md` 和 `docs/rag_evaluation.md`。

### 验证结果
- compileall：通过。
- 全量 pytest：53 passed，22 warnings。
- Hybrid retrieval + audio timestamp regression targeted tests：3 passed。
- Frontend smoke：通过，required_routes=24，nav_targets=21，warnings=0。
- Frontend typecheck：通过。
- Frontend build：通过，25 个 build entries（含 `_not-found`）。
- encoding check：通过，258 个 UTF-8 文本文件。
- secret check：通过，findings=0。
- repo clean check：通过。
- RAG demo evaluation：通过。

### 能力边界
- 当前 keyword 检索是轻量 SQLite scan，不是完整 BM25/FTS5。
- Rerank provider 尚未接真实服务；未配置时只使用 deterministic fusion，`rerank_score` 保持为空。
- 主界面暂不直接展示 trace 字段，避免 raw/debug 信息影响普通用户体验。

<!-- stage:v4-0-code-repository-ingestion-start-20260702 -->
## V4.0 起步交付：代码仓库接入与代码 Citation Locator

### 阶段状态
V4.0 代码仓库理解能力已开始落地。当前支持安全本地仓库扫描、代码文件切片、file/line locator、向量索引、RAG 引用字段和 `/code` 页面；远程同步、AST 符号图谱、自动项目复盘和模拟面试仍在后续阶段。

### 交付内容
- 新增 `backend/app/schemas/code_repository_schema.py`。
- 新增 `backend/app/services/code_repository_service.py`。
- 新增 `backend/app/api/routes_code_repositories.py` 并挂载到 API router。
- 扩展 `Citation`、`RelatedChunk` 和前端类型，支持 `file_path`、`line_start`、`line_end`、`symbol_name`。
- 新增 `/code` 页面、AppShell 导航入口和上传中心代码仓库流程卡。
- 更新 `docs/code_repository_ingestion.md`、`docs/roadmap.md`、学习日志和阶段交付日志。
- 新增 `backend/tests/test_v4_0_code_repository_ingestion.py`。

### 验证结果
- compileall：通过。
- 全量 pytest：56 passed，25 warnings。
- Code repository targeted tests：3 passed。
- Frontend smoke：通过，required_routes=25，nav_targets=22，warnings=0。
- Frontend typecheck：通过。
- Frontend build：通过，26 个 build entries（含 `_not-found`）。
- encoding check：通过，263 个 UTF-8 文本文件。
- secret check：通过，findings=0。
- repo clean check：通过。

### 能力边界
- 当前只做本地路径扫描，不自动 clone 远程仓库。
- 当前使用轻量行切片和简单 symbol 识别，不是完整 AST/语言服务器分析。
- 代码复盘、简历生成和面试反馈仍需后续真实 LLM provider，未配置时不能输出假内容。

<!-- stage:v4-0-learning-roadmap-relations-start-20260702 -->
## V4.0 起步交付：学习路线与轻量知识关系

### 阶段状态
V4.0 学习教练方向已开始落地。当前实现派生学习路线、知识关系 API、学习路线页面和知识关系页面；持久化 KnowledgeRelation、复杂图谱和真实 LLM 个性化路线仍在后续阶段。

### 交付内容
- 新增 `LearningRoadmapRead`、`LearningRoadmapStep` 和 `KnowledgeRelationRead` schema。
- 扩展 `learning_package_service`，从现有知识点和学习资产派生 roadmap 与 knowledge graph。
- 新增 `/api/learning/roadmap` 与 `/api/learning/knowledge-graph`。
- 新增 `/learning/roadmap` 与 `/learning/knowledge-graph` 页面。
- 更新 AppShell 导航，拆分学习路线、知识关系和版本档案。
- 新增 `backend/tests/test_v4_0_learning_roadmap.py`。
- 更新 `docs/learning_system.md`、roadmap、学习日志和阶段交付日志。

### 验证结果
- Learning roadmap targeted tests：3 passed。
- compileall：通过。
- 全量 pytest：58 passed，20 warnings。
- Frontend smoke：通过，required_routes=27，nav_targets=24，warnings=0。
- Frontend typecheck：通过。
- Frontend build：通过，28 个 build entries（含 `_not-found`）。
- encoding check：通过，266 个 UTF-8 文本文件。
- secret check：通过，findings=0。
- repo clean check：通过。
- version check：通过，`V3.8 / 3.8.0`。
- RAG demo evaluation：通过。

### 能力边界
- 当前关系是 request-time 派生视图，不是持久化图数据库。
- 当前路线不调用 LLM，不做假个性化推荐。
- 后续可以加入 KnowledgeRelation 表、图谱可视化和真实 provider 生成路线。
<!-- stage:v4-0-portfolio-ui-resilience-20260702 -->
## V4.0 起步交付：作品集页的服务边界收口与 smoke 通过

### 阶段状态
已完成本轮作品集页收口：真实摘要展示与 LLM 生成动作拆分，根页补齐 smoke 需要的真实项目概览文案，前端 typecheck/build 与后端测试重新通过。

### 交付内容
- 重写 `/portfolio`、`/portfolio/resume`、`/portfolio/interview`、`/portfolio/project-review`，让真实概览与可选生成内容分离。
- 保留 provider 缺失的明确拒绝，不把整页失败伪装成能力完成。
- 重新验证 frontend smoke、TypeScript typecheck、Next.js build 和后端 pytest。

### 验证结果
- `E:\python3.12.9\python.exe -m pytest`：61 passed, 25 warnings。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：passed，required_routes=27，nav_targets=24，warnings=0。
- frontend typecheck：passed。
- frontend build：passed。

### 当前边界
- 本轮仅完成作品集页边界收口，README、版本号、release 检查和推送仍待继续。

<!-- stage:v4-1-codebase-cleanup-architecture-consolidation-20260702 -->
## V4.1 进行中交付：全量代码体检、历史归档与架构收口

### 阶段状态
V4.1 已启动并完成第一批真实清理：代码资产清单、历史报告归档、前端 hooks suppression 清理、架构边界文档和多项质量门禁。当前仍未宣布最终发布，secret/repo-clean/release dry-run 需要在最终文件集 staged 后再次验证。

### 交付内容
- 新增 `scripts/audit_codebase.py`。
- 新增 `docs/v4_1_predevelopment_audit.md`、`docs/v4_1_code_inventory.md`、`docs/v4_1_code_inventory.json`。
- 新增 `docs/v4_1_dead_code_report.md`、`docs/v4_1_dead_code_plan.md`、`docs/v4_1_cleanup_report.md`。
- 新增 `docs/backend_architecture.md`、`docs/frontend_architecture.md`、`docs/module_boundaries.md`、`docs/scripts_reference.md`。
- 新增 `docs/v4_1_dependency_audit.md`、`docs/v4_1_test_audit.md`、`docs/v4_1_config_audit.md`、`docs/v4_1_ci_release_audit.md`、`docs/v4_1_docs_cleanup_report.md`。
- 将 V2/V3/V4.0 历史报告移动到 `docs/archive`，不删除历史学习档案。
- 更新 README、release 检查脚本和相关测试，指向新的 archive 路径。
- 移除本地临时 pnpm 文件，保留 npm/package-lock 作为前端标准依赖链路。

### 当前验证结果
- compileall：passed。
- pytest：61 passed，8 warnings。
- frontend typecheck：passed。
- frontend build：passed，28 routes。
- Alembic 临时库 upgrade/current：passed，`0006_v3_6_unified_media_tasks (head)`。
- encoding check：passed，282 UTF-8 files。
- version check：passed，`V3.8 / 3.8.0`。
- frontend smoke：passed，warnings=0。

### 当前边界
- V4.1 是工程治理与架构收口阶段，不新增假 AI 能力。
- 历史报告已归档但未删除；`learning_log.md` 和 `stage_delivery_log.md` 继续 append-only。
- 最终 release dry-run、secret check、repo clean check 和 V4.1 验收报告仍需在最终 staged 文件集上完成。

<!-- stage:v4-1-final-reverification-20260703 -->
## V4.1 最终复验：全量代码体检与架构收口完成

### 交付状态
- V4.1 代码资产清单、dead-code report、cleanup plan、cleanup report、dependency/test/config/CI/docs audit、backend/frontend/module boundary 文档和 learning package draft 均已生成。
- V2、V3、V4.0 历史报告已移动到 `docs/archive`，未删除历史学习档案。
- `docs/learning_log.md` 与 `docs/stage_delivery_log.md` 继续只追加维护。
- 当前稳定可见版本仍保持 `V3.8 / 3.8.0`；V4.1 是工程治理和架构收口分支，不冒充新增 provider-backed AI 能力。

### 最终验证
- compileall：通过。
- pytest：bundled Python 环境 61 passed，9 warnings。
- frontend typecheck：通过。
- frontend build：通过，28 个 App Router routes。
- Alembic isolated SQLite upgrade/current：通过，`0006_v3_6_unified_media_tasks (head)`。
- encoding check：通过，284 个 UTF-8 文本文件，96 条 legacy append-only 日志行保留。
- version check：通过，`V3.8 / 3.8.0`。
- frontend smoke：通过，required_routes=27，nav_targets=24，warnings=0。
- RAG demo evaluation：通过。
- secret check：通过，scanned=282，findings=0。
- repo clean check：通过，forbidden tracked files=0。
- release dry-run：通过，release_dry_run_version=V3.8，included_files=293，未发现 secrets/database/uploads/cache。

### 环境说明
- 当前 PowerShell 默认 `python` 是未安装 FastAPI 的 Anaconda 环境；项目兼容 bundled Python 可完整通过测试。
- 当前 PowerShell 没有全局 `npm`，`pnpm exec` 会触发 pnpm approve-builds 限制；前端使用 bundled Node 调用项目本地 CLI 完成验证。

<!-- stage:v4-2-full-regression-demo-release-readiness-20260703 -->
## V4.2 交付：全链路回归、Demo 稳定与发布前准备

### 交付内容
- 版本同步到 `V4.2 / 4.2.0`。
- Demo seed 增强为文档、图片、音频、视频、代码仓库、RAG、拒答、任务中心和学习资产完整链路。
- 新增 `scripts/check_full_regression.py`。
- 增强 `scripts/check_demo_ready.py` 和 `scripts/evaluate_rag.py`。
- 新增 `backend/tests/test_v4_2_full_regression.py`，并增强 RAG evaluation 测试断言。
- CI backend job 新增 full regression gate。
- 新增 V4.2 full regression、demo validation、RAG quality、test、acceptance、learning package 和 GitHub release notes 文档。
- README、roadmap、demo mode、RAG evaluation、release process 和 scripts reference 已同步 V4.2。

### 当前验证
- targeted V4.2 regression tests：9 passed。
- Demo readiness：passed。
- RAG demo evaluation：passed。
- Full regression checklist：passed，67 checks。
- compileall 与 version check 已通过。
- full pytest：63 passed，13 warnings。
- frontend typecheck/build：passed，28 routes。
- release dry-run：passed，V4.2，302 files。
- release archive check：passed，files=302，forbidden=0，missing=0。

### 当前边界
- Demo 数据为 synthetic 且明确标注，不代表真实 provider 输出。
- live browser E2E 尚未自动化；V4.2 使用 static frontend smoke 与 seeded full regression 作为发布前门禁。
- 当前 release zip 保留在本地 `releases/`，不纳入 Git；推送后仍需以 GitHub Actions 结果作为远端最终证明。
<!-- stage:v4-3-real-demo-ux-hardening-release-usability-20260704 -->
## V4.3 delivery: real demo UX hardening and release usability

### Delivery status
V4.3 has completed the core implementation pass for repository governance, docs integrity, README asset safety, provider-boundary regression, API regression and unified quality-gate orchestration. Final release zip generation remains the last local packaging step after these append-only logs are committed.

### Delivered files and changes
- Added V4.2.1 repository governance reports:
  - `docs/v4_2_1_repository_source_audit.md`
  - `docs/v4_2_1_mainline_diff_report.md`
  - `docs/v4_2_1_merge_plan.md`
  - `docs/v4_2_1_release_preparation.md`
  - `docs/v4_2_1_branch_governance.md`
- Added V4.3 quality scripts:
  - `scripts/check_docs_links.py`
  - `scripts/check_readme_assets.py`
  - `scripts/check_all.py`
- Added tests:
  - `backend/tests/test_provider_boundaries.py`
  - `backend/tests/test_v4_3_api_regression.py`
- Updated current version to `V4.3 / 4.3.0`.
- Updated CI to include V4.3 docs/assets checks and V4.3 release artifact validation.
- Updated README and core docs for V4.3 startup, demo, release and roadmap guidance.
- Generated V4.3 reports:
  - `docs/v4_3_docs_link_report.md`
  - `docs/v4_3_demo_walkthrough_validation.md`
  - `docs/v4_3_provider_boundary_report.md`
  - `docs/v4_3_smoke_test_report.md`
  - `docs/v4_3_api_regression_report.md`
  - `docs/v4_3_quality_gate_report.md`
  - `docs/v4_3_release_readiness_report.md`
  - `docs/v4_3_release_notes.md`
  - `docs/v4_3_learning_package_draft.md`

### Verification evidence
- Backend compileall: passed.
- Backend pytest: 70 passed, 9 warnings.
- Frontend typecheck/build: passed.
- Docs link check: passed.
- README asset check: passed.
- Demo readiness, RAG demo evaluation and full regression: passed.
- Alembic isolated SQLite upgrade/current: passed at `0006_v3_6_unified_media_tasks (head)`.
- Secret check: passed, findings=0.
- Repo clean check: passed, forbidden tracked files=0.
- Release dry-run: passed for V4.3, 307 tracked files, no secrets/databases/uploads/cache.

### Boundaries
- Demo data is synthetic and labelled.
- Missing real providers still return explicit NOT_CONFIGURED-style failures.
- No fake OCR, fake vision description, fake transcription, fake answer or fake rerank score was added.
- `main` still requires PR merge before GitHub default branch shows the latest V4.3 state.
- Live browser E2E remains future work.

### Recommended release path
Open a PR from `feature/v4.3-real-demo-ux-hardening` to `main`, wait for CI to pass, merge, tag `v4.3.0`, and create a GitHub Release from `docs/v4_3_release_notes.md`.
<!-- stage:v4-3-final-release-archive-20260704 -->
### V4.3 final release archive addendum
- Final `check_all --full`: passed.
- Final release dry-run: passed with `included_files=321`.
- Local release zip: `releases/AI-Knowledge-OS-Pro-V4.3-20260704.zip`.
- Release safety inspection: `files=321`, `forbidden=0`, `missing=0`.
- SHA256: recorded in the local `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.
- Release artifacts remain local and untracked by design.

<!-- stage:v4-4-ci-provider-dry-run-hardening-20260705 -->
### V4.4 CI provider dry-run hardening addendum
- PR #2 was created from `feature/v4.4-demo-e2e-observability` to `main`.
- The earlier push CI exposed one quality-job issue: provider dry-run imported backend dependencies before the quality job installed them.
- Fixed dry-run mode to be dependency-light while preserving real backend adapters for `--demo` and `--real-if-configured`.
- Local verification after the fix:
  - default `python scripts/evaluate_providers.py --dry-run`: passed.
  - `.venv` `evaluate_providers.py --dry-run`: passed.
  - `.venv` `evaluate_providers.py --demo`: passed.
  - `.venv` `evaluate_providers.py --real-if-configured`: passed.
- Re-ran final `python scripts/check_all.py --full` after the fix: passed.

<!-- stage:v4-3-post-release-hardening-20260704 -->
### V4.3 post-release hardening addendum
- Added missing final evidence reports:
  - `docs/v4_3_readme_asset_report.md`
  - `docs/v4_3_ux_error_state_report.md`
  - `docs/v4_4_planning.md`
- Updated release readiness and release notes from pre-merge language to actual published state: PR #1 merged, `main` synchronized, `v4.3.0` tag and GitHub Release created.
- Extended `scripts/check_all.py` with gate-level status/duration output and `--skip-frontend`.
- Extended frontend smoke checks to cover shared UX components and required Chinese status labels.
- Added shared UI primitives in `frontend/components/ui.tsx` for structured error state, provider-missing warning, demo banner, task log drawer, source locator button and learning action bar.
- Full validation after this addendum: `check_all --full` passed; pytest `70 passed, 10 warnings`; frontend build generated 28 routes; release dry-run included 324 files.
- Regenerated local V4.3 release zip and verified package safety: `files=324`, `forbidden=0`, `missing=0`.

<!-- stage:v4-4-demo-e2e-observability-20260705 -->
## V4.4 delivery: demo E2E contracts and runtime observability

### Delivery status
V4.4 has completed the implementation pass for version alignment, citation-jump contracts, runtime observability, optional browser E2E scaffolding, provider dry-run evaluation, documentation updates and V4.4 report generation. Final `check_all --full`, release zip generation and release archive inspection remain the last packaging steps after this append-only log update.

### Delivered files and changes
- Added runtime observability:
  - `backend/app/core/observability.py`
  - `backend/app/core/responses.py`
  - `backend/app/schemas/system_schema.py`
  - `backend/app/services/system_service.py`
  - `backend/app/api/routes_system.py`
  - `frontend/app/system/observability/page.tsx`
- Added observability and citation tests:
  - `backend/tests/test_v4_4_observability.py`
  - `backend/tests/test_observability.py`
  - `backend/tests/test_citation_jump_contracts.py`
- Added optional E2E infrastructure:
  - `frontend/playwright.config.ts`
  - `frontend/e2e/demo-smoke.spec.ts`
  - `frontend/e2e/citation-jump.spec.ts`
  - `frontend/e2e/system-observability.spec.ts`
  - `frontend/e2e/run-optional-e2e.mjs`
  - `scripts/check_e2e.py`
  - `scripts/run_demo_e2e.py`
- Added optional provider evaluation:
  - `scripts/evaluate_providers.py`
  - `docs/v4_4_provider_eval_report.md`
- Updated current version to `V4.4 / 4.4.0`.
- Updated CI, quality gates, release scripts and release archive required entries for V4.4.
- Generated V4.4 reports:
  - `docs/v4_4_predevelopment_audit.md`
  - `docs/v4_4_browser_e2e_report.md`
  - `docs/v4_4_citation_jump_report.md`
  - `docs/v4_4_observability_report.md`
  - `docs/v4_4_provider_eval_report.md`
  - `docs/v4_4_frontend_consolidation_report.md`
  - `docs/v4_4_quality_gate_report.md`
  - `docs/v4_4_acceptance_report.md`
  - `docs/v4_4_test_report.md`
  - `docs/v4_4_release_notes.md`
  - `docs/v4_4_learning_package_draft.md`

### Verification evidence so far
- Backend compileall: passed.
- Backend pytest: 73 passed, 15 warnings before the final compatibility wrapper rerun.
- Alembic isolated SQLite upgrade/current: passed at `0006_v3_6_unified_media_tasks (head)`.
- Frontend typecheck/build: passed.
- Docs links, README assets, frontend smoke and E2E scaffold: passed through `check_all --quick`.
- Observability/citation contract gate: passed.
- Provider dry-run gate: passed and reported NOT_CONFIGURED boundaries without external calls.
- Demo readiness, RAG demo evaluation and full regression: passed on `.pytest_tmp/v4_4_demo_showcase.db`.
- Optional browser E2E runner: skipped honestly with `PLAYWRIGHT_NOT_INSTALLED`.
- Secret check and repo-clean check: passed.
- Release dry-run: passed for V4.4, included_files=324, no secrets/databases/uploads/cache.

### Boundaries
- Demo data remains synthetic and labelled.
- Missing real providers still return explicit NOT_CONFIGURED-style failures.
- No fake OCR, fake vision description, fake transcription, fake answer, fake embedding, fake rerank score or fake citation jump was added.
- Live browser E2E is not claimed in the current local environment because Playwright is not installed.
- Release artifacts remain local under `releases/` and untracked by design.

### Recommended release path
Run final `check_all --full`, generate and inspect the V4.4 release zip, commit the V4.4 implementation/docs, push `feature/v4.4-demo-e2e-observability`, open a PR to `main`, wait for CI, then tag `v4.4.0` and draft the GitHub Release from `docs/v4_4_release_notes.md`.

<!-- stage:v4-4-final-full-gate-20260705 -->
### V4.4 final full-gate addendum
- Final `python scripts/check_all.py --full`: passed.
- Backend pytest: `74 passed, 23 warnings`.
- Frontend typecheck/build: passed.
- Docs, README assets, frontend smoke, provider dry-run, E2E scaffold, demo readiness, RAG evaluation, full regression, secret scan, repo-clean and release dry-run all passed.
- Optional live browser E2E was not claimed; current local runtime lacks Playwright and reports `PLAYWRIGHT_NOT_INSTALLED`.
- Remaining packaging step: generate final V4.4 release zip and run `scripts/check_release.py --version V4.4`.

<!-- stage:v4-4-final-release-archive-20260705 -->
### V4.4 final release archive addendum
- Staged V4.4 files so `release.py` could include new reports, E2E specs and scripts through `git ls-files`.
- Final staged release dry-run: passed with `included_files=347`, no secrets/databases/uploads/cache.
- Local release zip: `releases/AI-Knowledge-OS-Pro-V4.4-20260705.zip`.
- Release safety inspection: `files=347`, `forbidden=0`, `missing=0`.
- SHA256: recorded in the local `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.
- Release artifacts remain local and untracked by design.
