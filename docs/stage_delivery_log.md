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
- `python\python.exe -m pytest`：61 passed, 25 warnings。
- `python\python.exe scripts/check_frontend_smoke.py`：passed，required_routes=27，nav_targets=24，warnings=0。
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

<!-- stage:v4-4-pr-ci-source-branch-hardening-20260705 -->
### V4.4 PR CI source branch hardening addendum
- Pull request CI for `530183a` had one backend failure: portfolio markdown generation could not populate `source_branch` in a detached PR checkout.
- Updated portfolio git metadata detection to use GitHub Actions branch environment variables before local git branch commands.
- Added regression coverage for PR head-ref metadata.
- Targeted portfolio tests passed: `6 passed`.
- Full local gate passed after the fix: backend pytest `75 passed, 22 warnings`, frontend typecheck/build, encoding, version, docs/assets checks, provider dry-run, demo checks, full regression, secret scan, repo-clean and release dry-run.
- Next release action: regenerate the V4.4 local release archive, commit this CI hardening change, push, and confirm the PR checks turn green.

<!-- stage:v4-5-live-demo-e2e-hardening-20260705 -->
## V4.5 delivery: strict live demo E2E hardening

V4.5 has completed the implementation and local verification pass for version alignment, strict browser E2E, citation jump coverage, observability browser coverage, demo-mode retrieval hardening, GitHub Actions live E2E and V4.5 documentation. Final release archive generation, GitHub push, CI confirmation, tag and GitHub Release remain the next release operations.

### Delivered changes
- Updated visible version to `V4.5 / 4.5.0`.
- Added strict Playwright dependency/script support and kept optional E2E skip behavior honest.
- Added a CI `live-e2e` job with Chromium installation and Playwright artifact upload.
- Strengthened browser specs for Dashboard, Upload, Tasks, Chat, Media, video timestamp detail, Learning, Portfolio, System, citation jumps and observability.
- Added stable frontend test IDs for chat, citation panel, media detail, keyframes, transcript segments and observability panels.
- Split media transcript rendering into `frontend/components/media/TranscriptTimeline.tsx`.
- Fixed demo E2E CORS env serialization and pinned the temporary demo backend embedding/index settings.
- Updated showcase seed data so demo fingerprints match the real `DEMO_MODE=true` embedding fingerprint.
- Added demo-mode-only keyword retrieval fallback when Qdrant is unavailable; real mode still fails explicitly.
- Generated V4.5 live E2E, citation jump, observability, quality gate, acceptance and release note docs.

### Verification evidence
- Backend compileall: passed.
- Backend pytest: `75 passed`, `22 warnings`.
- Alembic isolated SQLite upgrade/current: passed at `0006_v3_6_unified_media_tasks (head)`.
- Frontend typecheck/build: passed.
- `check_all --quick`: passed.
- `check_all --demo`: passed.
- `check_all --provider-eval`: passed without external calls.
- `check_all --observability`: passed.
- Strict live browser E2E: `22 passed`.
- `check_all --e2e`: passed with browser E2E `22 passed`.

### Boundaries
- Demo data remains synthetic and labelled.
- Missing real providers still return explicit NOT_CONFIGURED-style states.
- No fake OCR, fake vision description, fake transcription, fake answer, fake embedding, fake rerank score or fake citation jump was added.
- Release artifacts remain local under `releases/` and untracked by design.

<!-- stage:v4-5-learning-package-draft-20260705 -->
### V4.5 learning package draft addendum
- First V4.5 implementation commit: `5b6e205`.
- Generated `docs/v4_5_learning_package_draft.md` from `main..HEAD` after the implementation commit.
- Included the draft in README documentation navigation and V4.5 release archive required entries.
- Remaining release steps: run final release clean checks, generate and inspect the V4.5 zip, push branch, confirm GitHub Actions, merge/tag/release.

<!-- stage:v4-5-final-release-archive-20260705 -->
### V4.5 final release archive addendum
- Final `check_all --full`: passed.
- Local release zip: `releases/AI-Knowledge-OS-Pro-V4.5-20260705.zip`.
- Release safety inspection: `files=355`, `forbidden=0`, `missing=0`.
- SHA256: recorded in the local `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.
- Release artifacts remain local and untracked by design.

<!-- stage:v4-5-release-doc-hygiene-20260705 -->
### V4.5 release documentation hygiene addendum
- Maintenance branch: `codex/v4.5-release-doc-hygiene`.
- CI push filters now include `codex/**` alongside `main` and `feature/**`.
- The local release checklist now reflects the current `V4.5 / 4.5.0` gates and links to the GitHub release checklist.
- Version consistency checks now cover release documentation and CI workflow surfaces, not only backend/frontend package metadata and README.
- `docs/v4_5_release_doc_hygiene_report.md` records the maintenance scope and is required by the V4.5 release archive checker.
- Validation passed: `check_version`, `check_all --quick`, `compileall`, `pytest`, `check_all --release` and staged `release.py --version V4.5 --dry-run`.
- Staged release dry-run included `356` files with no secrets, databases, uploads or caches.

<!-- stage:v4-5-release-doc-hygiene-archive-20260705 -->
### V4.5 release documentation hygiene archive addendum
- Local release zip regenerated after the hygiene documentation append: `releases/AI-Knowledge-OS-Pro-V4.5-20260705.zip`.
- Release safety inspection passed with `files=356`, `forbidden=0`, `missing=0`.
- Release artifacts remain local and untracked by design.

<!-- stage:v4-6-rag-eval-evidence-report-20260705 -->
## V4.6 preparation delivery: RAG evaluation evidence report

Delivered a low-risk V4.6 preparation increment on top of V4.5 without changing product version, provider behavior or database schema.

### Delivered changes
- `scripts/evaluate_rag.py --demo --output <path>` writes a JSON evidence report.
- The report includes summary metrics, citation source types, multimodal source types, locator shapes and QA traces.
- `scripts/check_all.py --demo` now writes `.pytest_tmp/v4_5_rag_eval_report.json` during the demo gate.
- Added `docs/v4_6_rag_eval_report.md` and updated RAG/script/roadmap docs.
- Added test coverage for the report structure and demo-only boundary.

### Verification evidence
- Targeted RAG evaluation tests: `2 passed`.
- Demo gate: passed, including demo seed, readiness, JSON RAG evidence report and full regression.
- Compileall: passed.
- Backend pytest: `75 passed`, `23 warnings`.
- Quick quality gate: passed.
- Release safety gate: passed with staged release dry-run `included_files=357`, no secrets/databases/uploads/cache.

### Boundaries
- No fake OCR, fake transcription, fake LLM answer or fake provider-backed evaluation was added.
- The JSON report validates deterministic seeded evidence and citation plumbing only.

<!-- stage:v4-6-rag-eval-full-gate-20260705 -->
### V4.6 RAG evaluation evidence full-gate addendum
- Final unified gate passed through `python scripts/check_all.py --full`.
- Backend pytest passed with `75 passed`, `22 warnings`.
- Frontend typecheck and Next.js production build passed; 28 app routes generated.
- Local browser demo E2E passed with `22 passed`.
- Demo RAG evidence report generation passed and remains demo-only.
- Release dry-run passed with `included_files=357`, no secrets/databases/uploads/cache.

<!-- stage:v4-6-project-structure-learning-page-20260705 -->
### V4.6 project structure learning page delivery

Delivered a low-risk V4.6 learning experience increment on the existing V4.5/V4.6 evidence baseline.

### Delivered changes
- Added `/learning/project-structure`.
- Added the `项目构造` navigation entry under `学习成长`.
- Added route and required-text coverage to `scripts/check_frontend_smoke.py`.
- Updated the frontend smoke regression expectation to `required_routes=28`.
- Added `docs/v4_6_project_structure_learning_page.md` and updated the V4.6 roadmap.

### Boundaries
- No backend API or database migration was added.
- No provider-backed capability was changed.
- No fake OCR, fake transcription, fake LLM answer, fake embedding or fake runtime metric was added.

<!-- stage:v4-6-project-structure-learning-page-verification-20260705 -->
### V4.6 project structure learning page verification

- Frontend smoke passed with `required_routes=28`.
- Targeted frontend smoke pytest passed with `1 passed`.
- Compileall passed for `backend/app` and `scripts`.
- Quick quality gate passed, including encoding, version, docs links, README assets, frontend smoke and E2E static scaffolding.
- Frontend typecheck passed via local `tsc --noEmit`.
- Frontend production build passed and generated `/learning/project-structure`.
- Full backend pytest passed with `75 passed`, `16 warnings`.
- Release gate passed with no secrets, forbidden tracked files, databases, uploads or caches in dry-run output.

<!-- stage:v4-6-quality-gate-json-report-20260705 -->
### V4.6 quality gate JSON report delivery

Delivered a self-check automation increment on top of the V4.6 learning-page branch.

### Delivered changes
- Added optional machine-readable JSON output to `scripts/check_all.py`.
- Preserved partial gate evidence on failures by writing the report from the script's final summary path.
- Added regression coverage for the quick-mode JSON contract.
- Updated CI to upload `quality-gate-json` artifacts when the report exists.
- Updated scripts reference, roadmap and V4.6 quality-gate JSON documentation.

### Verification
- Quick quality gate with JSON output passed.
- Targeted pytest coverage for the JSON report passed.

### Boundaries
- No provider-backed capability was changed.
- No application database or user upload directory is touched.
- No fake OCR, transcription, LLM response, embedding or quality score was added.

<!-- stage:v4-6-quality-gate-markdown-summary-20260705 -->
### V4.6 quality gate Markdown summary delivery

Delivered the next self-check automation layer after the JSON quality report.

### Delivered changes
- Added `scripts/summarize_quality_report.py`.
- Added Markdown summary artifact generation to GitHub Actions.
- Added two regression tests covering passed and failed report summaries.
- Updated scripts reference and V4.6 quality-gate documentation.

### Verification
- Compileall passed for scripts.
- Quality report summary tests passed with `2 passed`.
- Quick quality gate with JSON output passed.
- Markdown summary generation passed from the real quick JSON report.

### Boundaries
- No user data, upload directory or application database was touched.
- No provider-backed capability or fake quality score was added.

<!-- stage:v4-6-quality-artifact-validation-20260705 -->
### V4.6 quality artifact validation delivery

Delivered validation for generated self-check artifacts.

### Delivered changes
- Added `scripts/check_quality_artifacts.py`.
- Added CI validation for quick JSON and Markdown quality artifacts before artifact upload.
- Added regression tests for valid, failed and malformed artifact cases.
- Updated scripts reference and V4.6 quality-gate documentation.

### Verification
- Compileall passed for scripts.
- Quality artifact and summary tests passed with `5 passed`.
- Real quick quality chain generated JSON, generated Markdown and validated both artifacts successfully.

### Boundaries
- No provider-backed capability was changed.
- No app database, user uploads, logs or release artifacts are used as input by the validator.
- No fake quality score was introduced; the validator checks reported gate facts only.

<!-- stage:v4-6-run-self-check-entrypoint-20260705 -->
### V4.6 one-command self-check entrypoint delivery

Delivered a single entrypoint for the self-check evidence loop.

### Delivered changes
- Added `scripts/run_self_check.py`.
- Updated CI to call the wrapper instead of spelling out each quality artifact command.
- Added wrapper tests covering command composition and dry-run output.
- Updated scripts reference and V4.6 quality-gate documentation.

### Verification
- Compileall passed for scripts.
- Self-check wrapper, artifact validator and summary tests passed with `7 passed`.
- Real quick self-check passed and produced validated JSON plus Markdown artifacts.

### Boundaries
- No provider-backed capability was changed.
- The wrapper only writes explicit self-check artifacts under the selected output directory.
- No app database, user uploads or real provider keys are touched.

<!-- stage:v4-6-quality-report-comparison-20260705 -->
### V4.6 quality report comparison delivery

Delivered baseline-vs-current comparison for quality gate artifacts.

### Delivered changes
- Added `scripts/compare_quality_reports.py`.
- Added optional comparison support to `scripts/run_self_check.py`.
- Added comparison regression tests.
- Updated scripts reference, CI artifact matching and V4.6 quality-gate documentation.

### Verification
- Compileall passed for scripts.
- Quality comparison, self-check wrapper, artifact validator and summary tests passed with `10 passed`.
- Real quick baseline plus current self-check comparison passed with `regression_count=0`.

### Boundaries
- No provider-backed capability was changed.
- No fake quality score was added; comparison uses recorded gate status, gate presence and durations only.

<!-- stage:v4-6-self-check-history-index-20260705 -->
### V4.6 self-check history index delivery

Delivered a local history index for self-check artifacts.

### Delivered changes
- Added `scripts/index_self_checks.py`.
- Added tests for normal indexes, empty directories and pytest temporary fixture filtering.
- Updated scripts reference and V4.6 quality-gate documentation.

### Verification
- Compileall passed for scripts.
- Self-check index tests passed with `3 passed`.
- Real `.pytest_tmp` indexing passed and reported one real quick self-check run after filtering test fixtures.

### Boundaries
- No provider-backed capability was changed.
- No app database, uploads or logs are read by the indexer.
- The indexer summarizes recorded self-check artifacts only.

<!-- stage:v4-6-self-check-write-index-20260705 -->
### V4.6 self-check auto index refresh delivery

Delivered automatic history index refresh for the one-command self-check entrypoint.

### Delivered changes
- Added `--write-index` to `scripts/run_self_check.py`.
- Updated CI to refresh the self-check history index during the quality job.
- Expanded artifact upload paths to include `self_check_index.json` and `self_check_index.md`.
- Updated self-check wrapper tests and V4.6 quality-gate documentation.

### Verification
- Compileall passed for scripts.
- Self-check wrapper and index tests passed with `8 passed`.
- Real quick self-check with `--write-index` passed and produced the history index.

### Boundaries
- No provider-backed capability was changed.
- No app database, user uploads or real provider keys are touched.

<!-- stage:v4-6-self-check-improvement-plan-20260705 -->
### V4.6 self-check improvement plan delivery

Delivered a data-driven improvement plan artifact for the self-check loop.

### Delivered changes
- Added `scripts/plan_self_check_improvements.py`.
- Added `--write-plan` to `scripts/run_self_check.py`.
- Updated CI to generate and upload improvement plan JSON/Markdown artifacts.
- Added tests for failed/regressed, comparison-detail and healthy-baseline planning paths.

### Verification
- Compileall passed for scripts.
- Self-check improvement plan, wrapper and index tests passed with `12 passed`.
- Real quick self-check with `--write-index --write-plan` passed and produced the improvement plan.

### Boundaries
- No provider-backed capability was changed.
- No fake quality score or invented recommendation was added; actions are derived from self-check history and comparison artifacts only.

<!-- stage:v4-6-self-check-git-provenance-20260705 -->
### V4.6 self-check Git provenance delivery

Delivered traceability metadata for self-check evidence artifacts.

### Delivered changes
- Added Git branch, commit, short commit and dirty-state metadata to `check_all.py --json-report`.
- Rendered provenance in Markdown quality summaries.
- Added provenance to the self-check history JSON and Markdown index.
- Required provenance in quality artifact validation.
- Updated V4.6 quality-gate docs, scripts reference, roadmap and regression tests.

### Verification
- Compileall passed for backend app and scripts.
- Frontend smoke plus self-check provenance tests passed with `11 passed, 2 warnings`.
- Frontend typecheck passed using the bundled Node runtime.
- Frontend production build passed and included `/learning/project-structure`.
- Real quick self-check with `--write-index --write-plan` passed and generated provenance-aware artifacts.

### Boundaries
- No backend API, database schema, provider, RAG or media-processing behavior changed.
- No app data, uploads, logs or provider keys are read; the new metadata comes only from local Git commands or CI Git environment fields.
- No fake quality score or fake provider output was added.

<!-- stage:v4-6-self-check-auto-compare-latest-20260705 -->
### V4.6 self-check automatic latest comparison delivery

Delivered automatic baseline reuse for repeated local self-check runs.

### Delivered changes
- Added `--compare-latest` to `scripts/run_self_check.py`.
- The wrapper preserves an existing `check_all_<mode>.json` as `baseline_check_all_<mode>.json` before generating the new report.
- The saved baseline is passed to `scripts/compare_quality_reports.py`.
- When `--write-plan` is also used, the generated comparison JSON is included in the improvement-plan input.
- Added tests for baseline copying, missing-baseline skip behavior and dry-run command planning.

### Verification
- Compileall passed for scripts.
- Self-check wrapper, comparison and improvement-plan tests passed with `15 passed`.

### Boundaries
- No provider-backed capability was changed.
- No fake comparison is generated; missing baseline is reported as a skip.
- The preserved baseline is local self-check artifact data only, not application data or user uploads.

### Verification addendum
- Real first-run path passed with `auto_compare=skipped reason=no_previous_report`.
- Real repeated-run path passed with `auto_compare=enabled`, `regression_count=0` and an improvement-plan recommendation to broaden validation scope.

<!-- stage:v4-6-self-check-command-suggestions-20260705 -->
### V4.6 self-check command suggestions delivery

Delivered machine-actionable next-step hints for self-check improvement plans.

### Delivered changes
- Added a `command` field to improvement-plan JSON items.
- Added a `Command` column to improvement-plan Markdown output.
- Suggested concrete commands for first self-check generation, latest-baseline comparison and release-scope broadening.
- Kept command suggestions empty for remediation steps that require human inspection.
- Made quality-summary next-step wording mode-aware for quick and release reports.
- Updated V4.6 quality-gate docs, scripts reference, roadmap and regression tests.

### Verification
- Compileall passed for scripts.
- Self-check improvement-plan and wrapper tests passed with `14 passed`.
- Quality-summary, improvement-plan and wrapper tests passed with `18 passed` after the mode-aware summary wording fix.
- Quality-summary, improvement-plan and wrapper tests passed with `19 passed` after making release-mode broaden-scope wording mode-aware.
- Real release-mode self-check with latest-baseline comparison passed with `regression_count=0`.

### Boundaries
- No provider-backed capability was changed.
- No fake remediation is generated; commands are suggested only for deterministic self-check workflows.
- No application database, uploads, logs or provider credentials are read.

<!-- stage:v4-6-self-check-command-allowlist-20260705 -->
### V4.6 self-check command allowlist delivery

Delivered safety validation for executable self-check recommendations.

### Delivered changes
- Added `scripts/check_improvement_plan_commands.py`.
- Validated improvement-plan command suggestions against an explicit allowlist.
- Required command artifact paths to stay under `.pytest_tmp`.
- Allowed empty commands for human-inspection remediation items.
- Integrated command validation into `run_self_check.py --write-plan`.
- Updated scripts reference, V4.6 quality-gate docs and roadmap.

### Verification
- Compileall passed for scripts.
- Command validator, self-check wrapper and improvement-plan tests passed with `20 passed`.
- Real quick self-check with `--write-plan` passed and automatically validated the generated command suggestion.

### Boundaries
- No provider-backed capability was changed.
- The validator never executes suggested commands.
- Non-self-check commands and artifact paths outside `.pytest_tmp` are rejected.

<!-- stage:v4-6-self-check-next-command-summary-20260705 -->
### V4.6 self-check next command summary delivery

Delivered stable final-summary output for the next safe self-check command.

### Delivered changes
- Added `next_command_from_plan()` to `scripts/run_self_check.py`.
- Printed `next_command_priority`, `next_command_title` and `next_command` after `--write-plan` when a validated command exists.
- Printed an explicit dry-run unavailable marker instead of pretending a real next command was generated.
- Updated V4.6 self-check documentation and tests.

### Verification
- Compileall passed for scripts.
- Self-check wrapper and command-validator tests passed with `15 passed`.
- Real quick self-check with `--write-plan` passed and printed stable final `next_command_*` summary lines.

### Boundaries
- No suggested command is executed automatically.
- Output is derived from the already generated improvement-plan JSON.

<!-- stage:v4-6-self-check-next-command-artifacts-20260705 -->
### V4.6 self-check next command artifacts delivery

Delivered durable artifacts for the next validated self-check command.

### Delivered changes
- Added `self_check_next_command.json` and `self_check_next_command.md` to `run_self_check.py --write-plan`.
- Wrote `status=available` with priority, title and command when a validated command exists.
- Wrote `status=none` when no executable next command exists.
- Updated CI artifact upload paths to include next-command artifacts.
- Updated V4.6 quality-gate docs, scripts reference, roadmap and regression tests.

### Verification
- Compileall passed for scripts.
- Self-check wrapper and command-validator tests passed with `17 passed`.
- Real quick self-check with `--write-plan` passed and wrote next-command JSON/Markdown artifacts with `status=available`.

### Boundaries
- No suggested command is executed automatically.
- The artifact is derived from the validated improvement plan only.

<!-- stage:v4-6-self-check-manifest-artifacts-20260705 -->
### V4.6 self-check manifest artifacts delivery

Delivered a manifest for the generated self-check artifact bundle.

### Delivered changes
- Added `self_check_manifest.json` and `self_check_manifest.md` to `run_self_check.py`.
- Recorded self-check mode, comparison state, artifact paths, artifact existence and next-command summary.
- Updated CI artifact upload paths to include the manifest.
- Updated V4.6 quality-gate docs, scripts reference, roadmap and regression tests.

### Verification
- Compileall passed for scripts.
- Self-check wrapper and command-validator tests passed with `18 passed`.
- Real quick self-check with `--write-plan` passed and wrote manifest JSON/Markdown artifacts.

### Boundaries
- The manifest does not execute commands.
- The manifest records generated self-check artifact metadata only.

<!-- stage:v4-6-self-check-manifest-validator-20260705 -->
### V4.6 self-check manifest validator delivery

Delivered validation for the self-check artifact manifest.

### Delivered changes
- Added `scripts/check_self_check_manifest.py`.
- Validated manifest artifact paths against the `.pytest_tmp` evidence boundary.
- Checked declared artifact existence against the filesystem.
- Required core quality JSON/Markdown artifacts to exist.
- Reused the improvement-plan command allowlist for manifest `next_command.command`.
- Integrated manifest validation into `run_self_check.py` after manifest generation.
- Added regression coverage for the validator failure modes.

### Verification
- Compileall and targeted pytest are pending in this local step.
- A real self-check run will confirm the wrapper calls the validator before final artifact reporting.

### Boundaries
- The validator does not execute the suggested next command.
- It only validates generated self-check evidence metadata.

<!-- stage:v4-6-self-check-manifest-validator-verification-20260705 -->
### V4.6 self-check manifest validator verification delivery

Closed the local verification loop for the manifest validator.

### Delivered changes
- Verified the standalone manifest validator with success and failure-mode tests.
- Verified `run_self_check.py` calls the manifest validator after writing `self_check_manifest.json`.
- Verified quick/release gates, frontend typecheck/build and release package safety checks.
- Regenerated the release package after documentation changes as the final local packaging step.

### Verification
- Compileall passed for `backend/app` and `scripts`.
- Targeted V4.6 self-check tests passed with `22 passed`.
- Real quick self-check passed and reported `self_check_manifest=checked`.
- Quick quality gate passed with JSON evidence output.
- Frontend typecheck and production build passed.
- Release gate and release package safety check passed.

### Boundaries
- No provider-backed OCR, transcription, RAG answer or media processing behavior was changed.
- No user database, uploads directory or historical records were reset.

<!-- stage:v4-6-next-self-check-runner-20260705 -->
### V4.6 next self-check runner delivery

Delivered a safe runner for the next self-check command artifact.

### Delivered changes
- Added `scripts/run_next_self_check.py`.
- Validated `self_check_next_command.json` status and command shape.
- Reused the existing self-check command allowlist.
- Kept default behavior as validate-only.
- Required explicit `--execute` before running the command.
- Added CI validation for the generated next-command artifact.
- Added regression tests for ready, none, unsafe and explicit-execute paths.

### Verification
- Compileall, targeted tests and quality gates are pending in this local step.

### Boundaries
- The runner does not generate fake quality results.
- The runner does not execute arbitrary commands.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-next-self-check-runner-verification-20260705 -->
### V4.6 next self-check runner verification delivery

Verified the self-check runner as a controlled automation bridge.

### Delivered changes
- Confirmed validate-only mode reports `result=ready` for an allowlisted next command.
- Confirmed explicit execution advances quick self-check to comparison evidence.
- Confirmed release self-check can be advanced to comparison evidence.
- Confirmed the generated full-gate recommendation can be executed through the same runner path.

### Verification
- Compileall passed for scripts.
- Targeted self-check runner, manifest, wrapper and command-allowlist tests passed with `26 passed`.
- Quick compare-latest self-check passed with `regression_count=0`.
- Release compare-latest self-check passed with `regression_count=0`.
- Full gate passed, including backend tests, frontend build, demo E2E and release dry-run.

### Boundaries
- Execution remains explicit through `--execute`.
- Suggested commands remain restricted to the self-check allowlist.
- No real provider calls were made.

<!-- stage:v4-6-next-self-check-json-report-20260705 -->
### V4.6 next self-check JSON report delivery

Delivered a machine-readable readiness artifact for the next self-check command.

### Delivered changes
- Added `--json-output` to `scripts/run_next_self_check.py`.
- Wrote `schema_version`, `status`, `result`, `priority`, `title`, `command`, `next_command_json` and `failure`.
- Restricted report output paths to `.pytest_tmp`.
- Added CI artifact upload for `.pytest_tmp/next_self_check.json`.
- Added regression tests for successful JSON output, unsafe output paths and failed-command JSON payloads.

### Verification
- Compileall passed for scripts.
- Runner, self-check wrapper and command-allowlist tests passed with `25 passed`.
- Real quick self-check passed.
- Real next-command readiness JSON was written with `result=ready`.

### Boundaries
- JSON reporting does not execute the next command.
- Execution still requires explicit `--execute`.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-bounded-self-check-loop-20260705 -->
### V4.6 bounded self-check loop delivery

Delivered a bounded controller for chaining self-check artifacts.

### Delivered changes
- Added `scripts/run_self_check_loop.py`.
- Started the loop from `run_self_check.py`.
- Validated next-command artifacts through `run_next_self_check.py`.
- Added `--max-steps` as an explicit automation limit.
- Kept next-command execution opt-in through `--execute-next`.
- Added CI dry-run planning and artifact upload.
- Added regression tests for command construction, artifact chaining, dry-run reports, validate-only behavior and explicit execution behavior.

### Verification
- Compileall passed for scripts.
- Loop, next-runner and self-check wrapper tests passed with `27 passed`.
- Real validate-only loop passed and wrote `.pytest_tmp/self_check_loop.json`.
- CI-style dry-run loop passed and wrote `.pytest_tmp/self_check_loop_dry_run.json`.

### Boundaries
- The loop does not execute next commands unless `--execute-next` is present.
- Output and report paths stay under `.pytest_tmp`.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-self-check-loop-report-validator-20260705 -->
### V4.6 self-check loop report validator delivery

Delivered validation for bounded self-check loop reports.

### Delivered changes
- Added `scripts/check_self_check_loop_report.py`.
- Validated report schema, mode, status and bounded step counts.
- Validated `.pytest_tmp` paths and readiness artifact existence.
- Reused the self-check command allowlist for initial and step commands.
- Integrated report validation into `run_self_check_loop.py`.
- Added CI validation for `.pytest_tmp/self_check_loop.json`.
- Added regression coverage for valid reports, planned dry-runs, step-count mismatches, unsafe commands, unsafe paths and missing readiness artifacts.

### Verification
- Compileall passed for scripts.
- Loop report validator and loop tests passed with `12 passed`.
- CI-style dry-run loop passed and automatically validated the report.
- Real validate-only loop passed and automatically validated one ready next step.

### Boundaries
- The validator does not execute commands.
- It only checks loop report metadata and referenced readiness artifacts.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-self-check-loop-markdown-report-20260705 -->
### V4.6 self-check loop Markdown report delivery

Delivered a human-readable Markdown summary for bounded self-check loops.

### Delivered changes
- Added `--markdown-output` to `scripts/run_self_check_loop.py`.
- Wrote loop status, mode, execution flags, initial command and step table to Markdown.
- Added optional `markdown_output` validation to `scripts/check_self_check_loop_report.py`.
- Uploaded `.pytest_tmp/self_check_loop.md` from CI with the loop JSON report.
- Added regression coverage for dry-run Markdown reports, ready-step Markdown reports and missing Markdown artifact validation.

### Verification
- Compileall passed for scripts.
- Loop and loop-report validator tests passed with `13 passed`.
- CI-style dry-run loop passed and wrote `.pytest_tmp/self_check_loop.md`.

### Boundaries
- Markdown reporting does not execute commands.
- The report path remains restricted to `.pytest_tmp`.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-next-self-check-markdown-report-20260705 -->
### V4.6 next self-check Markdown report delivery

Delivered a human-readable Markdown report for next-command readiness.

### Delivered changes
- Added `--markdown-output` to `scripts/run_next_self_check.py`.
- Wrote status, result, priority, title, source artifact and validated command to Markdown.
- Kept Markdown output paths restricted to `.pytest_tmp`.
- Uploaded `.pytest_tmp/next_self_check.md` from CI.
- Added regression coverage for ready Markdown output, unsafe Markdown paths and failed-command Markdown payloads.

### Verification
- Compileall passed for scripts.
- Next-runner and loop tests passed with `16 passed`.
- Real quick self-check passed.
- Real next-command readiness wrote JSON and Markdown reports with `result=ready`.

### Boundaries
- Markdown reporting does not execute the next command.
- Execution still requires explicit `--execute`.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-next-self-check-report-validator-20260705 -->
### V4.6 next self-check report validator delivery

Delivered validation for next-command readiness reports.

### Delivered changes
- Added `scripts/check_next_self_check_report.py`.
- Validated readiness report schema, status/result pairs, safe paths, optional Markdown existence and allowlisted commands.
- Integrated readiness report validation into `run_next_self_check.py`.
- Added CI validation for `.pytest_tmp/next_self_check.json`.
- Added regression coverage for ready reports, none reports, unsafe commands, missing Markdown artifacts and invalid status/result pairs.

### Verification
- Compileall passed for scripts.
- Readiness report validator and next-runner tests passed with `15 passed`.
- Real quick self-check passed.
- Real next-command readiness wrote JSON/Markdown reports and automatically validated the JSON report.

### Boundaries
- The validator does not execute commands.
- It only checks readiness report metadata and command safety.
- No provider-backed or user-data behavior was changed.

<!-- stage:v4-6-self-check-loop-step-markdown-20260705 -->
### V4.6 self-check loop step Markdown evidence delivery

Delivered per-step Markdown evidence for bounded self-check loops.

### Delivered changes
- Added per-step `--markdown-output` calls when `run_self_check_loop.py` invokes `run_next_self_check.py`.
- Added `readiness_markdown` to executed loop step reports.
- Added the readiness Markdown path to loop report tables.
- Extended `check_self_check_loop_report.py` to validate per-step readiness Markdown paths when present.
- Added regression coverage for generated step Markdown and missing step Markdown artifacts.

### Verification
- Loop runner, loop report validator and next-readiness tests passed with `29 passed`.
- Dry-run loop report validation passed.
- Real quick loop validation passed and generated `next_self_check_step_1.md`.

### Boundaries
- Step Markdown reporting does not execute next commands by itself.
- Execution still requires `--execute-next`.
- No provider-backed, database or user-upload behavior was changed.

<!-- stage:v4-6-ci-artifact-contract-check-20260705 -->
### V4.6 CI artifact contract check delivery

Delivered a CI artifact coverage check for self-check evidence.

### Delivered changes
- Added `scripts/check_ci_artifacts.py`.
- Added CI artifact coverage for loop step readiness JSON and Markdown.
- Added the `CI artifacts` gate to `check_all.py --quick`.
- Added CI execution of the artifact coverage check before uploading quality artifacts.
- Added regression coverage for current workflow validity and missing loop step Markdown upload paths.

### Verification
- `python scripts/check_ci_artifacts.py` passed with zero failures.
- Release self-check comparison passed with zero regressions before this implementation pass.
- CI artifact, static quality gate, self-check runner and quality artifact tests passed with `22 passed`.
- Quick quality gate passed with the new `CI artifacts` gate.
- Release gate passed with `386` included files in dry-run.
- Release archive check passed with `files=386`, `forbidden=0`, `missing=0`, SHA256 `2bb83ae843f4663a95aec443086620f452e9171bd9b013fada086ccc30e71e4b`.

### Boundaries
- The check reads workflow configuration only.
- It does not call providers, touch databases or execute user-data workflows.
- It preserves append-only learning and delivery history.

<!-- stage:v4-6-full-self-check-mode-20260705 -->
### V4.6 full self-check mode delivery

Delivered full-mode support for the self-check evidence loop.

### Delivered changes
- Added `full` to `run_self_check.py` supported modes.
- Changed healthy release-baseline recommendations to use `run_self_check.py --mode full`.
- Extended the command allowlist, bounded loop entrypoint and loop report validator to understand full mode.
- Kept legacy `check_all.py --full --json-report` allowlist support for existing artifacts.
- Added regression coverage for full artifact command planning, full dry-run output, full-mode recommendations and full-mode command validation.

### Verification
- Self-check runner, plan, command validator, next-readiness, loop runner and loop report tests passed with `55 passed`.
- Full self-check dry-run planned the expected JSON, Markdown, history, improvement, next-command and manifest artifacts.
- Release self-check comparison produced a full self-check recommendation and the next-readiness report accepted it with `result=ready`.
- Quick and release quality gates passed after the implementation.
- Release archive check passed with `files=386`, `forbidden=0`, `missing=0`, SHA256 `f4c329ba189677ec06107e1d8979472697c92b0ea0563d9a1aaeccfae7238378`.

### Boundaries
- The implementation does not execute full gates automatically.
- Full execution still requires the explicit generated command or `run_next_self_check.py --execute`.
- No provider behavior, database schema or uploaded user data behavior was changed.

<!-- stage:v4-6-ci-release-full-handoff-evidence-20260705 -->
### V4.6 CI release-to-full handoff evidence delivery

Delivered CI coverage for the release self-check handoff into full validation.

### Delivered changes
- Added release self-check baseline and release comparison steps to the quality-and-release GitHub Actions job.
- Added full-ready next-command JSON and Markdown evidence under `.pytest_tmp/self_check_release`.
- Extended `scripts/check_ci_artifacts.py` to require release-to-full handoff commands and artifact upload paths.
- Added regression tests for missing release-to-full readiness commands and uploads.
- Updated script reference and V4.6 quality evidence documentation.

### Verification
- CI artifact, next-runner and next-report validator tests passed with `20 passed`.
- CI artifact contract check passed with `required_commands=9` and `required_artifact_paths=28`.
- Release self-check baseline passed.
- Release self-check comparison passed with zero regressions.
- Full-ready next-command report passed with `result=ready`.
- Explicit next-report validation passed.

### Boundaries
- CI does not automatically execute full validation from the generated next command.
- The new checks read workflow configuration and generated `.pytest_tmp` evidence only.
- No provider-backed, database or user-upload behavior was changed.

<!-- stage:v4-6-github-actions-status-diagnostic-20260705 -->
### V4.6 GitHub Actions status diagnostic delivery

Delivered a safe remote CI status diagnostic.

### Delivered changes
- Added `scripts/check_github_actions.py`.
- Added current branch/commit matching for GitHub Actions workflow runs.
- Added offline JSON input for deterministic tests and saved evidence review.
- Added optional JSON/Markdown report outputs under `.pytest_tmp`.
- Added strict `--require-success` mode for release operators.
- Added tests for passed, failed, pending, unavailable and unsafe output-path cases.

### Verification
- GitHub Actions status diagnostic tests passed with `7 passed`.
- Real remote diagnostic completed with `result=unavailable` and `failure=github_api_http_404`, writing JSON/Markdown reports under `.pytest_tmp`.

### Boundaries
- The diagnostic does not run in default local quality gates.
- Network, permission or private-repository API failures are reported as `unavailable` unless `--require-success` is requested.
- The script does not print GitHub tokens and does not call providers, databases or uploaded user-data flows.

<!-- stage:v4-6-ci-github-actions-status-artifact-20260705 -->
### V4.6 CI GitHub Actions status artifact delivery

Delivered CI artifact coverage for remote GitHub Actions status diagnostics.

### Delivered changes
- Added `actions: read` permission to the GitHub Actions workflow.
- Added a quality-and-release step that runs `scripts/check_github_actions.py` with `GITHUB_TOKEN: ${{ github.token }}`.
- Added `.pytest_tmp/github_actions_status.json` and `.pytest_tmp/github_actions_status.md` to the `quality-gate-json` artifact upload.
- Extended `scripts/check_ci_artifacts.py` to require the command, upload paths, permission and token environment binding.
- Added tests for missing diagnostic command, missing diagnostic uploads and missing workflow permission/token snippets.

### Verification
- CI artifact contract check passed with `required_commands=10`, `required_artifact_paths=30`, `required_workflow_snippets=2`.
- CI artifact and GitHub Actions diagnostic tests passed with `15 passed`.

### Boundaries
- The CI diagnostic does not use `--require-success` by default.
- The workflow token is passed only to the diagnostic process and is not printed.
- No provider-backed, database, media or user-upload behavior was changed.

<!-- stage:v4-6-github-actions-report-validator-20260705 -->
### V4.6 GitHub Actions report validator delivery

Delivered schema validation for GitHub Actions status evidence.

### Delivered changes
- Added `scripts/check_github_actions_report.py`.
- Added validation for status/result/conclusion combinations, repository shape, Actions run URLs, branch/head branch matching, unavailable failure text and Markdown report content.
- Updated `scripts/check_github_actions.py` to validate reports immediately after writing JSON/Markdown output.
- Added an explicit CI validator step after GitHub Actions status diagnosis.
- Extended CI artifact contract tests to require the validator step.

### Verification
- GitHub Actions report validator, diagnostic and CI artifact tests passed with `22 passed`.
- Real local diagnostic generated unavailable evidence and validated it with `github_actions_report=checked`.
- CI artifact contract check passed with `required_commands=11`, `required_artifact_paths=30`, `required_workflow_snippets=2`.

### Boundaries
- The validator checks artifact structure and consistency only.
- It does not turn unavailable remote access into a local gate failure unless the diagnostic was run with strict success requirements.
- No provider-backed, database, media or user-upload behavior was changed.

<!-- stage:v4-6-ci-artifact-ordering-20260705 -->
### V4.6 CI artifact ordering checks delivery

Delivered ordering validation for CI evidence commands.

### Delivered changes
- Added required ordered snippet groups to `scripts/check_ci_artifacts.py`.
- Validated that quick self-check evidence precedes next-command readiness checks.
- Validated that loop evidence precedes loop report validation.
- Validated that release comparison precedes full-ready handoff evidence.
- Validated that GitHub Actions status evidence is generated before status report validation.
- Validated that `quality-gate-json` upload happens after status report validation.
- Added regression tests for reversed or premature ordering.

### Verification
- CI artifact ordering tests passed with `12 passed`.
- CI artifact contract check passed with `required_ordered_groups=5`.

### Boundaries
- The ordering check reads workflow text only.
- It does not execute provider calls, modify databases or inspect uploaded user data.
- It preserves default non-strict remote CI status diagnostics.

<!-- stage:v4-6-ci-artifact-contract-report-20260705 -->
### V4.6 CI artifact contract report delivery

Delivered JSON and Markdown evidence for the CI artifact contract check.

### Delivered changes
- Added `--json-output` and `--markdown-output` to `scripts/check_ci_artifacts.py`.
- Added `.pytest_tmp/ci_artifacts_contract.json` and `.pytest_tmp/ci_artifacts_contract.md` to the quality artifact upload.
- Updated the CI workflow to write the contract report before other quality evidence is produced.
- Extended CI artifact ordering checks so the contract report command must appear before `quality-gate-json` upload.
- Added tests for report writing, unsafe output paths and premature upload ordering.

### Verification
- CI artifact tests passed with `16 passed`.
- CI artifact contract report generation passed with `required_commands=12`, `required_artifact_paths=32`, `required_workflow_snippets=2`, `required_ordered_groups=6`.

### Boundaries
- The report describes workflow configuration only.
- It does not execute provider calls, modify databases or inspect uploaded user data.
- Failed contract checks still write report files when output paths are provided.

<!-- stage:v4-6-ci-artifact-contract-report-validator-20260705 -->
### V4.6 CI artifact contract report validator delivery

Delivered schema validation for CI artifact contract evidence.

### Delivered changes
- Added `scripts/check_ci_artifacts_report.py`.
- Added validation for schema version, pass/fail consistency, workflow path safety, required count fields, failure count alignment and Markdown report content.
- Updated `scripts/check_ci_artifacts.py` to validate generated reports immediately after writing JSON/Markdown.
- Added an explicit GitHub Actions step that validates `.pytest_tmp/ci_artifacts_contract.json` and `.pytest_tmp/ci_artifacts_contract.md` before artifact upload.
- Added tests for passed reports, failed reports, malformed counts, unsafe workflow paths, missing Markdown and premature upload ordering.

### Verification
- CI artifact contract and report validator tests passed with `25 passed`.
- CI artifact contract generation passed with `required_commands=13`, `required_artifact_paths=32`, `required_workflow_snippets=2`, `required_ordered_groups=6` and `ci_artifacts_report=checked`.

### Boundaries
- The validator checks workflow evidence only.
- It does not execute provider calls, modify databases or inspect uploaded user data.
- It accepts real failed contract reports when their structure is consistent, so CI failures remain readable instead of losing their diagnostic payload.

<!-- stage:v4-6-full-self-check-manifest-validator-20260705 -->
### V4.6 full self-check manifest validator delivery

Delivered validator alignment for full self-check manifests.

### Delivered changes
- Updated `scripts/check_self_check_manifest.py` to accept `full` mode alongside `quick` and `release`.
- Added full manifest regression coverage in `backend/tests/test_v4_6_self_check_manifest.py`.
- Updated documentation to describe quick, release and full manifest validation consistently.

### Verification
- Self-check manifest, run-self-check and improvement-plan command tests passed with `25 passed`.
- A generated `.pytest_tmp/self_check_full/self_check_manifest.json` passed `scripts/check_self_check_manifest.py`.

### Boundaries
- The fix only changes self-check artifact validation.
- It does not alter provider behavior, user data, demo seed contents, media processing or release packaging rules.

<!-- stage:v4-6-self-check-baseline-resilience-20260705 -->
### V4.6 self-check baseline resilience delivery

Delivered a more durable auto-comparison baseline location for self-check runs.

### Delivered changes
- Updated `scripts/run_self_check.py` so `--compare-latest` copies the previous report to an isolated system temporary directory keyed by output path.
- Added regression coverage that deletes the active output directory after baseline preparation and confirms the baseline remains available.
- Documented the distinction between baseline inputs and regenerated self-check output artifacts.

### Verification
- Run-self-check, next-self-check, manifest and command allowlist tests passed with `36 passed`.
- `scripts/run_self_check.py` compiled successfully.

### Boundaries
- The change affects self-check comparison evidence only.
- It does not move uploaded CI artifacts, provider outputs, user data, release package contents or demo seed databases.

<!-- stage:v4-6-quality-comparison-duplicate-gates-20260705 -->
### V4.6 quality comparison duplicate gate preservation delivery

Delivered duplicate gate occurrence preservation for quality report comparisons.

### Delivered changes
- Updated `scripts/compare_quality_reports.py` so repeated gate names remain distinct in comparison evidence.
- Added stable occurrence labels such as `E2E scaffolding #2`.
- Added tests for duplicate gate missing detection and duplicate occurrence status changes.
- Documented why full quality reports now compare 22 gates instead of collapsing duplicate names to 21.

### Verification
- Quality comparison and run-self-check tests passed with `21 passed`.
- A real full self-check baseline compared against itself reported `base_gate_count=22`, `current_gate_count=22` and `regression_count=0`.

### Boundaries
- The fix changes comparison/reporting behavior only.
- It does not change quality gate execution order, provider behavior, demo data, business APIs or release packaging.

<!-- stage:v4-7-interaction-visual-cleanup-20260705 -->
### V4.7 interaction performance and visual cleanup delivery

Delivered the V4.7 interaction, visualization and cleanup-governance pass.

### Delivered changes
- Unified current version surfaces to `V4.7 / 4.7.0` across backend config, frontend package metadata, AppShell brand, version checks, release scripts and CI release artifact naming.
- Reduced the main AppShell navigation from 25 to 17 entries while preserving all existing routes.
- Added UI pending/feedback primitives and API timeout handling.
- Added static V4.7 interaction and UI performance gates and wired them into `check_all.py` and GitHub Actions.
- Redesigned Dashboard as a guided command center and `/learning/project-structure` as a visual learning map.
- Added V4.7 audit, performance, navigation, cleanup, acceptance, test, release-note and learning-package docs.

### Verification
- `python scripts/check_ui_performance_budget.py`: passed.
- `python scripts/check_frontend_interactions.py`: passed with `high_risk=0`.
- `python scripts/check_interaction_feedback.py`: passed with `high_risk=0`.
- `python -m pytest backend/tests/test_v3_9_frontend_smoke.py backend/tests/test_v4_7_ui_quality_gates.py`: `3 passed`.
- Frontend typecheck: passed.
- `python scripts/check_version.py`: passed.

### Boundaries
- No provider output was fabricated.
- No user data, uploads, databases, logs or historical learning archives were deleted.
- V4.6 self-check tooling was documented and classified instead of being removed blindly.

<!-- stage:v4-7-final-validation-20260705 -->
### V4.7 final validation delivery

Delivered the final V4.7 validation and release-evidence update.

### Delivered changes
- Updated final V4.7 acceptance, quality-gate and test reports with real command evidence.
- Expanded `docs/v4_7_learning_package_draft.md` into an 18-topic learning package for project study and interview explanation.
- Fixed the V4.7 release notes navigation cleanup wording.
- Updated the GitHub bug report version placeholder to `V4.7 / 4.7.0`.
- Extended `scripts/check_version.py` to include AppShell brand and the GitHub bug template.

### Verification
- `python scripts/check_frontend_interactions.py`: passed with `buttons=79`, `high_risk=0`.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_7.json`: passed.
- Full validation included backend pytest `190 passed`, frontend production build, browser E2E `22 passed`, demo readiness, demo RAG evaluation, full regression, secret scan, repo clean and release dry-run.

### Boundaries
- No user data, uploads, databases, logs, caches or secrets were added to the release surface.
- No fake provider output, OCR, transcription, citations, test results or release results were introduced.
- Historical learning and delivery records remain append-only.

<!-- stage:v4-8-runtime-performance-release-polish-20260705 -->
### V4.8 runtime performance and release polish delivery

Delivered the V4.8 runtime performance, request-cache and release-polish pass.

### Delivered changes
- Unified current version surfaces to `V4.8 / 4.8.0`.
- Added backend performance schemas, service and routes for request metadata snapshots.
- Recorded API request latency and cache status from the request middleware without storing bodies or secrets.
- Added frontend request cache/dedupe utilities and wired selected read endpoints to TTL-based caching.
- Added interaction timing metrics to `PendingButton` and exposed recent actions on `/system/performance`.
- Added `/system/performance` to AppShell navigation, smoke checks and production build routes.
- Added request-cache, performance observability and no-Git release-mode regression tests.
- Updated `check_secrets.py` and `check_repo_clean.py` to work in Git and extracted-source filesystem modes.
- Moved self-check and CI diagnostic implementations into `scripts/maintenance/` with root wrapper compatibility.
- Added V4.8 runtime, request-cache, performance dashboard, release zip, script migration, acceptance, test, release notes and learning-package docs.

### Verification
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: `194 passed`.
- Frontend typecheck: passed.
- Frontend production build: passed.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_8.json`: passed.
- Full validation included provider dry-run, optional browser E2E `22 passed`, demo readiness, demo RAG evaluation, full regression, secret scan, repo clean and release dry-run.

### Boundaries
- No fake LLM, OCR, transcription, citation, E2E, performance or release results were added.
- No user data, uploads, databases, logs, caches or secrets were added to the release surface.
- Historical V1-V4.7 learning and delivery records remain append-only.

<!-- stage:v4-8-final-release-20260705 -->
### V4.8 final release packaging delivery

Delivered the final V4.8 release archive and archive safety verification.

### Delivered changes
- Generated `releases/AI-Knowledge-OS-Pro-V4.8-20260705.zip`.
- Generated `releases/AI-Knowledge-OS-Pro-V4.8-20260705.zip.sha256`.
- Verified the archive with `scripts/check_release.py --version V4.8`.

### Verification
- Release check passed with `files=449`, `forbidden=0`, `missing=0`.
- SHA256: `81cdccb28ff0574fe5e21c511dc4761ea3280b43eadbf99c829d006802c43ddb`.

### Boundaries
- Release archive excludes `.env`, SQLite DBs, uploads, logs, `node_modules`, `.next`, caches, old releases and secrets by rule.
- The release archive is local under `releases/` and remains excluded from source control.

<!-- stage:v4-8-release-digest-correction-20260705 -->
### V4.8 release digest correction delivery

Recorded a correction for release digest handling: the final authoritative checksum is the `.sha256` file generated next to the regenerated release archive. Inline digest text inside versioned docs can become stale when those docs are included in the archive.

<!-- stage:v4-8-final-audit-no-git-validation-20260705 -->
### V4.8 final audit and no-Git validation delivery

Delivered the final V4.8 audit/documentation closure and extracted-source release validation.

### Delivered changes
- Added V4.8 predevelopment, interaction runtime and medium-risk interaction cleanup reports.
- Regenerated the V4.8 button latency map.
- Expanded the V4.8 learning package to 15 structured knowledge points.
- Updated quickstart and local development docs for V4.8 performance, request-cache and release validation workflows.
- Updated `scripts/check_release.py` so V4.8 audit and interaction reports are required in release archives.
- Updated V4.8 acceptance, test, quality-gate and release-zip user-experience reports with final no-Git evidence.

### Verification
- Targeted checks passed: interaction scan, interaction feedback, request cache, encoding, docs links, version consistency and UI performance budget.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_v4_8_final.json`: passed.
- `python scripts/release.py --version V4.8`: generated a local release archive.
- `python scripts/check_release.py --version V4.8`: passed with `files=453`, `forbidden=0`, `missing=0`.
- Extracted no-Git source tree validation passed with `check_version.py`, filesystem-mode `check_secrets.py`, filesystem-mode `check_repo_clean.py` and `check_all.py --quick`.

### Boundaries
- No fake LLM, OCR, transcription, citation, E2E, performance or release results were added.
- No user data, uploads, databases, logs, caches or secrets were added to the release surface.
- Historical learning and delivery records remain append-only.
- The authoritative release digest remains the `.sha256` file next to the regenerated local archive, not inline text inside packaged docs.

<!-- stage:v4-8-final-local-revalidation-20260705 -->
### V4.8 final local revalidation delivery

Delivered the final local quality revalidation after the V4.8 audit and no-Git release checks.

### Delivered changes
- Updated V4.8 acceptance and test reports with final compile, pytest, frontend build and Alembic evidence.
- Recorded the transient pytest environment failure caused by stale local demo log handles.
- Cleared the stale local demo backend/frontend child processes before rerunning the backend suite.

### Verification
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: passed with `194 passed, 23 warnings` after clearing the stale `.pytest_tmp/local_demo_logs` lock.
- Frontend typecheck: passed through local `node_modules/.bin/tsc.cmd --noEmit` with the bundled Node path.
- Frontend production build: passed through local `node_modules/.bin/next.cmd build` with the bundled Node path.
- Isolated Alembic migration check: passed through `upgrade head` and `current`, reporting `0006_v3_6_unified_media_tasks (head)`.

### Boundaries
- The rerun used generated `.pytest_tmp` data only and did not touch user databases, uploads, logs or historical archives.
- No fake test result was recorded; the initial lock failure and the successful rerun are both documented.

<!-- stage:v4-8-page-load-metrics-20260705 -->
### V4.8 page-load and route-switch metrics delivery

Delivered the missing browser page timing part of the V4.8 runtime performance objective.

### Delivered changes
- Added `frontend/services/page-metrics.ts`.
- Wired AppShell main navigation into route-switch timing.
- Added a page-load and route-switch panel to `/system/performance`.
- Updated README, V4.8 runtime/performance reports, the V4.8 learning package and release archive requirements.

### Verification
- Frontend typecheck and production build passed after the page metrics change.
- V4.8 release archive was regenerated and checked after adding `frontend/services/page-metrics.ts`.

### Boundaries
- Page timing is browser-session local and is not posted to the backend.
- No user prompts, files, API keys or provider payloads are recorded.

<!-- stage:v4-8-page-metrics-release-recheck-20260705 -->
### V4.8 page metrics release recheck delivery

Delivered the final release recheck after adding browser page-load and route-switch timing.

### Verification
- `python scripts/release.py --version V4.8`: regenerated the local archive.
- `python scripts/check_release.py --version V4.8`: passed with `files=454`, `forbidden=0`, `missing=0`.
- Extracted no-Git source tree validation passed again with version, filesystem-mode secret scan, filesystem-mode repo clean and `check_all.py --quick`.

### Boundaries
- The final authoritative digest remains the `.sha256` file next to the regenerated archive.
- The release archive remains local under `releases/` and excluded from source control.

<!-- stage:v4-8-interface-system-refinement-20260806 -->
### V4.8 interface system refinement delivery

Delivered a visual-system refinement for the existing AI Knowledge OS Pro frontend.

### Delivered changes
- Added an explicit frontend design-system guide.
- Refined the shared navigation shell, breadcrumb treatment, control states, and responsive mobile drawer behavior.
- Reworked Dashboard visual hierarchy and semantic status styling without changing API calls, provider modes, data models, or task behavior.

### Verification
- TypeScript typecheck passed.
- Next.js production build passed with all 30 routes generated.
- Desktop showcase review loaded real demo data.
- The 375px viewport check reported `scrollWidth=375` and `clientWidth=375` before the final mobile drawer overlap fix.

### Boundaries
- Hallmark was used as a design reference only; no third-party pages, copy, or assets were imported into the product.
- This is an interface refinement within V4.8, not a claim of new AI, OCR, transcription, RAG, or provider capability.

<!-- stage:v4-8-local-preview-api-proxy-20260806 -->
### V4.8 local preview API proxy delivery

Delivered an optional same-origin Next.js API proxy for constrained local preview environments.

### Delivered changes
- Added the `/api-proxy/*` rewrite only when `API_PROXY_TARGET` is configured.
- Updated example and environment documentation with the server-only target and browser-safe `/api-proxy` API base URL.

### Boundaries
- No backend API, database, provider configuration, media task, RAG result, or user data was changed.
- The proxy is opt-in and is not enabled without `API_PROXY_TARGET`.

<!-- stage:v4-8-ingestion-readiness-guidance-20260806 -->
### V4.8 ingestion readiness and duplicate guidance delivery

Delivered an ingestion integrity and user-feedback refinement for the local showcase and real upload path.

### Delivered changes
- Seeded ten persisted document chunks and added a readiness invariant that rejects mismatched document `chunk_count` metadata.
- Restricted ready-document retrieval to documents with actual chunk rows.
- Preserved duplicate-document routing details through the frontend API client and upload queue.
- Marked documents as failed when background task dispatch fails, while preserving the source and task record for inspection and retry.

### Verification
- Targeted pytest coverage passed for duplicate handling, RAG readiness refusal and failed task dispatch.
- A disposable showcase database passed readiness validation with `chunks=10`.
- Real local HTTP upload verification confirmed the first upload remains visible with a task-dispatch failure and the second response returns `DUPLICATE_DOCUMENT` with `document_id`, `job_id` and `next_action=reprocess`.

<!-- stage:v5-evidence-agent-20260815 -->
### V5 Evidence Agent delivery

Delivered the V5 local release candidate that upgrades 溯知 from a single-shot RAG application into an evidence-centered Agent system.

### Delivered changes
- Added canonical revision-safe EvidenceIndex lifecycle, vector manifests, atomic activation, cancellation compensation, dry-run/apply reconciliation and migration verification.
- Added the durable Agent runtime with quick/agent routing, structured planning and sufficiency, persisted Evidence Ledger, bounded model/tool calls, clarification/approval checkpoints, cancellation fences and claim-level Artifact provenance.
- Wired production Agent retrieval to the hybrid path while keeping a truthful sparse-only fallback when embedding is not configured and a hard error when real LLM mode is unavailable.
- Added Workbench, Run Workspace, Library and Artifact product zones, runtime-validated API/SSE contracts, source locators and Source↔Artifact provenance navigation.
- Added a deterministic 60-case evaluator, machine acceptance gate, CI jobs and V5 presentation assets.
- Added `docs/v5_agentic_rag/acceptance_report.md` and updated the task/checklist status from observed evidence only.

### Verification
- Agent clarification/Ledger/Artifact/runtime focused suite: `63 passed in 4.30s`.
- Adjacent Agent API/security/recovery suite: `10 passed in 7.93s`.
- V5 migration/CLI suite: `9 passed, 27 warnings in 21.73s`.
- Direct populated migration round-trip: exit 0, `0008→0006→0008`, semantic digest preserved, second upgrade equal to first.
- Pre-final backend full suite: `302 passed, 13 warnings in 107.54s`; final post-P1 full rerun remains a handoff gate.
- V5 evaluator and acceptance gate: 60/60 cases, gate `passed`, no declared failures, 0 external Provider calls.
- Frontend checkpoint: lint/typecheck/build passed, V5 Playwright `4/4`, selected citation `2/2`, production Artifact locator `1/1`, production audit 0 vulnerabilities; final post-edit full rerun remains a handoff gate.

### Boundaries
- Recording evaluation is deterministic and synthetic. The V4.9 comparison is explicitly a proxy, and no real-model quality claim is made.
- Production reranker is not configured. Registered open/neighbor evidence tools are not yet executed by the Runner. Server-side SSE stale-cursor reset and heartbeat are deferred.
- `alembic heads` reports one V5 head, while `alembic check` still exposes historical 0001–0006 model drift; no V5-specific drift is hidden.
- SQL migrations do not contact Qdrant. Existing online legacy payloads require an explicit reconciler/reindex operation after dry-run review.
- No push, merge, default-branch change, repository visibility change or public release publication was performed from this local delivery branch.

<!-- stage:v5-final-regression-and-sse-20260815 -->
### V5 final regression and SSE recovery delivery

Delivered the post-review runtime hardening and final full regression evidence.

### Delivered changes
- Added no-cursor, stale-cursor and future-cursor reset snapshots, cursor-neutral non-journaled heartbeats, public-event filtering and production-page projection reconstruction.
- Added the configurable real HTTP rerank adapter without enabling or mislabeling it in the default deterministic report.
- Replaced shared-counter recording ids with UUID generation and added concurrent-creation regression coverage.
- Preserved canonical sparse evidence and citation behavior when the live Qdrant endpoint returned `502`.

### Verification
- Backend full suite: `328 passed`.
- Backend SSE focused suite: `20 passed`.
- Frontend lint/typecheck: passed.
- Frontend unit suite: `12 files / 49 tests passed`.
- Next `15.5.23` production build: passed, 34 routes.
- Strict live E2E: `26/26 passed`.
- Production dependency audit: 0 vulnerabilities.
- Quick gate, migration round-trip/single head, evaluator 60/60 and acceptance gate: passed.

### Boundaries
- The final Standards/Spec follow-up is still running, so this entry does not predeclare its P0/P1 result.
- Production HTTP reranking is available but not configured or benchmarked in the default/fixed run.
- Neighbor/open-evidence execution remains partial; historical Alembic drift and legacy online Qdrant reconciliation remain explicit debt.
- V5 release-package verification currently fails because the release builder uses `git ls-files` and the V5 additions are not committed. Commit first, then rebuild and rerun the unchanged checker.

<!-- stage:v5-agent-closure-20260821 -->
### V5 Agent tool, Ledger and approval closure delivery

Delivered the next bounded Agent upgrade on top of the V5 local release candidate.

### Delivered changes
- EvidenceIndex now resolves an exact immutable chunk and a bounded same-revision neighbor window.
- Production Agent wiring executes `search_evidence`, `open_evidence` and `read_neighbors` through a short-session query port with one durable ToolCall per Runner slice.
- Worker recovery recognizes all three read-only evidence calls as safely replayable after a valid checkpoint.
- Model-selected candidates become support; remaining candidate/contextual rows become excluded with public reason/method events.
- Awaiting approval accepts a title-only modify command, supersedes the old publication proposal and rotates a content-bound digest without changing Run or Artifact identity.
- Run Workspace renders Chinese evidence-relation labels, exclusion explanations and a modification form; Recording Demo restores its Ledger by replaying the persisted journal.

### Verification
- Backend focused closure regression: `93 passed`; final full regression: `444 passed, 1 skipped in 150.71s`, including the parameterized recovery matrix.
- Frontend lint/typecheck/unit/build passed: `17 files / 76 tests`, 34 routes.
- V5 acceptance gate and quick quality gate passed.
- Targeted V5.1 browser scenarios: `2/2 passed`.

### Boundary
The current strict browser rerun lacked the backend origin environment variable, so its backend-dependent failures are recorded rather than relabeled. Real-provider quality benchmarking, historical Alembic drift and public GitHub publication remain separate follow-up work.

### Local release closure
- The settled V5.1 commit was packaged as `AI-Knowledge-OS-Pro-V5.0-20260821.zip`.
- Release checker result: 590 tracked files, forbidden 0, missing 0, manifest verified, freshness current.

<!-- stage:v5-1-integration-20260826 -->
### V5.1 multi-window integration delivery

Merged the dedicated Agent Intelligence, Product Experience, and Runtime/E2E branches into
`codex/v5.1-integration-control` without code conflicts.

### Delivered
- Agent continuation, tool-selection policy, conflict handling, and calibrated confidence.
- Taste-guided core UI redesign with clearer Chinese terminology and accessible approval flows.
- Isolated strict-runtime orchestration with explicit origins and owned resource cleanup.
- Portable evaluation digests and updated product/version quality gates.

### Verification
- Backend full: `455 passed, 1 skipped`.
- Runtime focused: `33 passed`.
- Frontend: lint/typecheck, `80 tests`, 34-route build.
- Targeted V5.1 browser flow: `7/7 passed`.
- Fixed evaluation and V5 acceptance gate: passed.

### Boundary
Docker daemon access is unavailable, so the canonical Redis/RQ + Qdrant double-run is not claimed.
Public V5.1 version bump, GitHub push/merge, real-provider benchmark, and Release publication remain the
next stage.

<!-- stage:v5-1-runtime-and-release-closure-20260826 -->
### V5.1 runtime and release closure delivery

Completed the non-model V5.1 release boundary on `codex/v5.1-integration-control`.

### Delivered
- Real Redis/RQ + Qdrant strict runtime with run-scoped manifests and exact owned-resource cleanup.
- RQ-safe durable Agent dispatch ids, observable worker/outbox logging and client-compatible Qdrant pinning.
- Route prewarming, four-worker browser concurrency and a 24-repeat code-evidence navigation regression.
- Public `V5.1 / 5.1.0` version alignment across backend, frontend, README, CI and release tooling.
- Updated V5.1 integration/runtime acceptance evidence and release profiles.

### Verification
- Canonical runtime: `32/32` twice, using independent infrastructure identities.
- Failure cleanup: forced readiness failure, zero owned-container or database residue.
- Backend after final review fixes: `457 passed, 1 skipped`; Ruff and compileall passed.
- Frontend: lint/typecheck, `81 tests`, 34-route production build, 0 production vulnerabilities.
- Migration round-trip, fixed 60-case evaluation, acceptance gate, quick gate, CI contract, secret scan
  and release dry-run all passed.

### Boundary
Model provider configuration and real-provider benchmarking were explicitly not performed. The local
archive and GitHub branch push are release-delivery actions; public GitHub Release publication remains
separate from source readiness.

### Local release evidence
`AI-Knowledge-OS-Pro-V5.1-20260826.zip` passed the release checker with 602 files, forbidden 0,
missing 0, a verified manifest and current source freshness. The SHA-256 remains in the generated
sidecar file rather than being embedded recursively in source documentation.

### Final review closure
- Standards axis: no hard documented-standard violations; three maintainability smells were fixed.
- Spec axis: strict port fallback, final-manifest verdict and lockfile-scope ambiguity were fixed.
- Post-review strict runtime: `32/32`, with a machine-readable final passed verdict and exact cleanup.

<!-- stage:v5-2-agent-control-20260827 -->
### V5.2 Agent Evaluation and Control Center delivery

Delivered the non-model Agent observability and regression-control stage on
`codex/v5.2-agent-evaluation-control`.

### Delivered
- Persisted sanitized Run Trace with replay integrity, policy/budget/call summaries, and failure triage.
- Durable fixed Evaluation Studio using SQL, transactional Outbox, Redis/RQ, leases, stale recovery, immutable
  terminal snapshots, and a fixed isolated evaluator subprocess.
- Evaluation history/detail/rerun, server status filtering, snapshot comparison, policy-change disclosure,
  provenance fingerprints, and accessible responsive interfaces.
- Strict runtime contracts that reject arbitrary evaluator modes, commands, paths, datasets, secret-bearing facts,
  malformed reports, contradictory comparison fields, and production-to-demo fallback.

### Verification checkpoint
- Focused post-review backend: `57 passed`.
- Focused frontend: `6 files / 17 tests`; lint and typecheck passed.
- Pre-review full checkpoint: backend `531 passed, 1 skipped`; frontend `96 tests`; production build and audit passed;
  fixed evaluator `60/60`; strict isolated runtime `36/36` twice with exact resource cleanup.

### Boundary
No real LLM, embedding, OCR, transcription, vision, or rerank provider was configured or benchmarked. The final
post-review full-suite, strict-runtime, release-archive, review-axis, and GitHub-push evidence is appended only after
those gates actually complete.

<!-- stage:v5-2-final-verification-20260827 -->
### V5.2 post-review verification closure

- Backend: `533 passed, 1 skipped in 210.90s`.
- Frontend: `25 files / 98 tests`, lint/typecheck, 35-page production build, 0 production vulnerabilities.
- Fixed evaluator: `60/60`, all hard gates, zero external provider calls.
- Migration: one `0009_v5_2_agent_control` head and populated `0009→0006→0009` semantic round-trip.
- Strict runtime: `36/36` for tokens `16816-389b8657` and `22308-2d0704c5`; exact cleanup passed twice.
- Adversarial closure: goal/private-policy redaction, environment allowlisting, policy-change disclosure, status
  filtering, centralized metric catalogs, and deterministic lease-heartbeat verification.

Real-provider configuration and quality benchmarking remain intentionally outside this stage.

<!-- stage:v5-2-nonfinite-final-20260827 -->
### V5.2 final Spec-review closure

Rejected non-finite evaluation values (`NaN`, positive infinity, negative infinity) at both JSON canonicalization
and numeric-validation boundaries. Final backend regression passed `536 passed, 1 skipped`; final strict runtime
tokens `18664-deccddad` and `24528-b972f20c` passed `36/36` with exact cleanup. This closes the malformed-report
requirement without changing the real-provider boundary.

<!-- stage:v5-2-release-archive-20260827 -->
### V5.2 release archive closure

Packaged `AI-Knowledge-OS-Pro-V5.2-20260827.zip`: 651 tracked files, forbidden 0, missing 0, manifest verified,
source freshness current. The detached archive SHA-256 is stored in the generated `.zip.sha256` sidecar.

<!-- stage:v5-3-adaptive-policy-20260828 -->
### V5.3 Adaptive Policy and Retrieval Lab delivery

Delivered the non-model adaptive-retrieval stage on `codex/v5.3-adaptive-policy-retrieval`.

### Delivered
- Immutable, versioned and strictly bounded retrieval policies with one active version.
- Idempotent draft commands, expected-active concurrency fences, evaluation-gated activation and audited rollback.
- Exact policy pinning on new/continued Agent Runs and pinned adaptive retrieval execution.
- Deterministic policy comparison and no-execution counterfactual simulation over persisted Run decisions.
- Candidate policy execution through SQL Outbox, Redis/RQ and the fixed isolated 60-case evaluator.
- A responsive Policy Lab connected to Evaluation Studio, Run Trace and System Observability.
- Current V5.3 version, architecture, local-development and resume documentation.

### Verification checkpoint
- Focused backend V5.3 suites, Agent recovery/control regressions, Ruff and compileall passed.
- Frontend passed `28 files / 105 tests`, lint, typecheck, production build and dependency audit with 0 vulnerabilities.
- Fixed default and candidate evaluations passed `60/60` with zero external provider calls.
- One Alembic head and the populated `0010→0006→0010` semantic migration round-trip passed.
- A pre-final strict runtime passed `39/39` with exact owned-resource cleanup.

Final full-suite, post-review double strict runtime, release archive and GitHub remote evidence are recorded only
after the unchanged final source completes those gates.

<!-- stage:v5-3-final-closure-20260828 -->
### V5.3 final review, runtime and release closure

- Backend: `582 passed, 1 skipped in 235.58s`; Ruff and compileall passed.
- Frontend: `28 files / 105 tests`; lint/typecheck/build passed; production audit found 0 vulnerabilities.
- Fixed evaluation: `60/60`, exact default/candidate policy fingerprints, zero external provider calls.
- Strict runtime: tokens `22736-058d00e4` and `35052-dc01de48` each passed `40/40` with exact process,
  container, database, WAL and SHM cleanup.
- Two-axis review: Standards 0 and Spec 0 remaining findings after all adversarial fixes.
- Release: `AI-Knowledge-OS-Pro-V5.3-20260828.zip`, 693 tracked files, forbidden 0, missing 0, manifest verified,
  source freshness current, detached SHA-256 sidecar generated.
- Remote: `codex/v5.3-adaptive-policy-retrieval` pushed and final local/remote commit SHA equality verified.

Real model-provider configuration and real-model answer-quality benchmarking remain intentionally outside V5.3.


## V5.4A offline retrieval optimizer core delivery:

- 阶段状态：完成（V5.4A 优化器核心 + API；页面与多模态任务留给 V5.4B）。
- 分支：`workbuddy/v5.4a-retrieval-optimizer-core`，基线 `062cf05cd23631488704915b62b6cbf1b6a22802`。
- 交付物：
  - 优化器核心模块 `backend/app/modules/agent_policy_optimizer/`（10 个文件，纯算法与 SQL 分层）。
  - 新表 `optimization_studies` / `optimization_trials` + Alembic `0011_v5_4_retrieval_optimizer`（单 head，upgrade/downgrade 往返验证）。
  - API `/api/v1/optimizer/*` 九条路由 + 严格输入校验。
  - outbox topic `agent.optimize.trial` → RQ `run_optimization_trial` → 固定 60 场景评测器。
  - 文档 `docs/v5_4_retrieval_optimizer_core/`（spec/plan/task/checklist/plain_language_guide/acceptance_report）。
- 本阶段验证：
  - 聚焦测试 31/31 通过（pure/sql/api/worker/migration 五文件）。
  - 全量后端：见 acceptance_report（新增 31 条后基线 582+1 全部保持通过）。
  - 前端单测 28 files / 105 tests 通过；`next build` 通过。
  - Strict E2E：V5.4A 分支与未修改 V5.3 基线各三跑对照，均为 38/40，且失败用例
    与失败原因完全一致（agent run 停在 routing 的环境性 flake），证明非本阶段回归。
  - 外部 Provider 调用：0（评测报告校验强制 + TrialMetrics 构造强制）。
- 双轴审查：
  - Standards Review：1 Blocker + 7 Major + 15 Minor/Nit，全部修复（含
    DetachedInstanceError、持久化回滚、schema 边界 500→422、错误码对齐、
    模型/迁移约束同步、死代码清理）。
  - Spec Review：5 项必须修复（HTTP 内联执行端点移除、recommendation_json 持久化、
    全集重评分、边界 422、迁移 CHECK 补齐）+ 3 项建议修复（cancel 允许 running 跑完、
    allow_nan=False、验收 #12 指纹不匹配 SQL 测试），全部落地。
- WorkBuddy Bundle：`AI-Knowledge-OS-Pro-V5.4A-WorkBuddy.bundle`（SHA-256 见 acceptance_report）。
- 下一阶段建议：V5.4B 页面与多模态（由另一个 Agent 负责），以及修复本机
  agent.run routing flake 的环境问题（建议：worker 并发或 E2E 单 worker 串行）。


## V5.5 optimizer closed loop delivery:

- 阶段状态：完成（闭环后端与 API；页面仍归 V5.4B）。
- 分支：`workbuddy/v5.5-optimizer-closed-loop`，基线 `53252cc9c4cfd34508fc483c8fbf2813d6753217`。
- 交付物：convert-draft / diff / retry / fail / settlement；Alembic 0012；
  4 条新 API；21 条新测试；文档六份。
- 验证：聚焦 21 passed；全量后端 636 passed, 1 skipped（清洁环境）；
  前端 105 passed + build 通过；Strict E2E 38/40（与基线一致的两个环境 flake）。
- 双轴审查：6 必须修复（retry 守卫/预算、全集前沿校验、并发转换 500、
  类型契约、spec 补充）+ 建议项全部落地。
- GitHub：分支已推送（`9d0049ee3c55d50e0b3251e4720554052ef2304d`）。
- Bundle：`releases/AI-Knowledge-OS-Pro-V5.5-WorkBuddy.bundle`
  （SHA-256 见同目录 .sha256 文件）。
- 下一阶段建议：V5.4B 页面；或 V5.6 贝叶斯候选生成 + 分类别胜败分析。


## V5.6 bayesian optimizer delivery:

- 阶段状态：完成（贝叶斯生成 + 暖启动 + 多轮 + 分类别分析；页面归 V5.4B）。
- 分支：`workbuddy/v5.6-bayesian-optimizer`，基线 `b38956d70209b963145a090dc3734f5d0c03e245`。
- 交付物：bayesian_generation.py / category_analysis.py 纯模块；Alembic 0013；
  next-round / categories API；warm start 全链路；21 条新测试；文档六份。
- 验证：聚焦 21 passed；全量后端 657 passed, 1 skipped；前端 105 passed +
  build 通过；Strict E2E 39/40（仅剩既有 routing flake，V5.3 policy 用例本轮通过）。
- 双轴审查：10 项（8 必须 + 2 建议）全部修复，含 categories 端点对齐 spec、
  推荐理由类别摘要接线、session 泄漏、Protocol 补齐、spec 语义修订。
- 下一阶段建议：V5.4B 页面（推荐审查页可展示类别对比与转草稿按钮）；
  或 V5.7 影子评估。


## V5.7 experiment workbench backend delivery:

- 阶段状态：完成（功能层第一期：overview/模板/事件流/导出/分享；页面归 V5.4B）。
- 分支：`workbuddy/v5.7-workbench-backend`，基线 `210a9e5fed08be0af0d7afcc8d40f9970edc96f0`。
- 交付物：overview/templates/events/export/share 五组能力；Alembic 0014（两表）；
  6 个新端点；16 条新测试；文档六份。
- 验证：聚焦 16 passed；全量后端 672 passed, 1 skipped（清洁环境）；前端 105 +
  build 通过；Strict E2E 38/40（与基线一致的两个既有 routing flake）。
- 双轴审查：7 项必须修复（缺失事件写入点、from-template 重复事件、Protocol
  补齐、死代码、无效 try/except、spec F4 修订、3-Trial 类别限制）+ 建议项全部落地。
- 下一阶段建议：V5.4B 页面（overview 端点即页面数据契约）；或 V5.8 影子评估。
<!-- stage:v5-7-integration-workbench-20260901 -->
### V5.7 Offline Retrieval Optimizer Workbench integration delivery

- Integrated WorkBuddy V5.4A–V5.7 backend history on `codex/v5.7-integration-ui` without rewriting the V5.3 baseline.
- Added V5.7 frontend routes `/policies/optimizer` and `/policies/optimizer/[studyId]`, typed no-fallback clients, Trial metrics, server-declared actions, comparison/diff/category views, and deterministic report rendering.
- Added a separate `agent-run-share` frontend boundary with expiring read-only Run Trace links, clipboard copy, revoke and mobile/keyboard coverage.
- Added Alembic `0015_v5_7_integration` with historical next-round receipt backfill and a single migration head.
- Hardened optimizer fingerprints, latency, exact case facts, cumulative budgets, candidate de-duplication, event ordering, Outbox recovery and template narrowing.
- Split optimizer internals into typed comparison, draft conversion, Trial inspection, workbench projection and terminal-command collaborators; Standards and Spec final reviews both reported 0 findings.
- Verification: optimizer-focused `99 passed`; backend full `681 passed, 1 skipped`; frontend `32 files / 114 tests`, lint, typecheck, Next.js build and zero-vulnerability audit passed; fixed evaluation `60/60` with zero external calls.
- Strict E2E: `43/43` twice, tokens `33076-80ffeecb` and `43720-a78a94be`; exact process/container/database cleanup passed on both runs.
- Visible version updated to `V5.7 / 5.7.0`; README, architecture, local development, release and resume surfaces were synchronized.
- GitHub branch `codex/v5.7-integration-ui` was pushed successfully. V5.7 release dry-run and archive verification passed with 789 files, zero forbidden/missing entries, verified Manifest and current-source Freshness; detached SHA-256 remains in the sidecar outside the archive.

<!-- stage:v5-7-1-audit-hardening-20260906 -->
### V5.7.1 审查修订与验收

- 基线 `f7577ea95f00ef6822ab957c8e8e63e4e951a2f7`；交付分支 `codex/v5.7.1-audit-hardening`。
- 修复执行/恢复预算、UTC 截止时间、并发轮次与草稿、旧执行覆盖、结果评分原子保存、取消后的推荐隔离、死信收敛与只读查询。
- 增加 0016 暖启动快照迁移；报告完整门禁、内容指纹与逐题矛盾检查；旧版真实分类恢复；三 Trial 完整两两对比。
- 页面增加自动更新、过时响应保护、同一意图重试去重、事件分页；分享列表持久恢复与刷新后撤销；当前算法术语更正为“观察引导搜索”。
- 本轮实测：后端 `701 passed, 1 skipped`；前端 `32 files / 115 tests`；lint、typecheck、生产 build、0 漏洞依赖审计通过；固定评测 `60/60`，外部模型调用 0。
- Strict E2E 连续两次 `44/44`，tokens：`audit571-a-20260906`、`audit571-b-20260906`；每次都定向清理临时进程、容器和数据库。第二轮的 Windows 连接关闭回调日志作为环境现象保留在验收说明中。
- 独立 Standards 与 Spec 最终聚焦复查均为 0 项仍待修复的实质问题；完整范围和边界见 `docs/v5_7_1_audit/acceptance_report.md`。
- 本地 Docker 启动故障通过备份隔离陈旧通信目录后恢复，未恢复出厂设置或删除容器数据；GitHub 登录已完成。
- 新增 `upgrade_explained.md`：逐项解释英文术语、修复原因与实现机制；真实模型、多人隔离、正式部署和 V5.8 仍不在本次完成范围。

<!-- stage:v5-8-reviewed-feedback-20260906 -->
### V5.8 反馈审阅与评测样例交付

- 基线 `8876e949c0d0da9dddf005fc2c9a66e7c552922a`；分支 `codex/v5.8-reviewed-feedback`。
- 完成成果/结论反馈、服务端固定快照、幂等提交、人工接受/驳回、版本冲突与并发保护、样例原子生成和用途/模式隔离导出；0017 迁移回环保留既有研究数据。
- 成果页新增反馈入口，评测中心新增审阅页；失败保留草稿与请求标识，导出不清空另一条审阅，内容指纹与选择集合在下载前验证。
- 修复独立审查发现的表单生命周期及 Docker 远端 context 探测问题；最终 Standards / Spec 复查均无遗留阻断/明确规格发现。
- 验证：后端 `733 passed, 1 skipped`；前端 `33 files / 121 tests`；生产 build、lint/typecheck、0 漏洞依赖审计通过；固定评测 `60/60`，外部调用 0；Strict E2E `v58-final-a`、`v58-final-b` 连续两次 `47/47`。
- 初次失败、修复原因和开发服务器日志现象均保留在 V5.8 验收报告中，没有用旧成绩替代本次结果。
- Docker 更新到 4.89.0 后，本机 Windows 26200 内置 restart 仍有端点兼容问题。已安装受限安全启动入口，保留原快捷方式和临时目录备份；正常冷启动验证通过，8 个原容器与 8 个数据卷保持一致。
- 不包含真实模型、新样例自动评分、自动写知识库/启用策略、多用户登录和公网部署。完成这一阶段后停止扩展，下一步由真实使用与评测需要决定。

<!-- stage:v5-8-1-hardening-20260926 -->
### V5.8.1 审查问题修复交付

- 基线 `d23d80f6dd1d31ea14c69b32cef82777bfbbc78d`；工作分支 `codex/v5.8.1-hardening`。这是 V5.8 的可靠性修订，尚未调整产品显示版本或宣布正式发布。
- 修复依赖漏洞、结论证据误判、Windows 代码仓库联接越界、模型重试/输出额度传递、过长目标中途异常、任务重复提交、错误说明丢失、过时推荐和小搜索空间误耗尽。先复现反例，再修复与回归。
- 验证：后端 `783 passed, 2 skipped`；前端 `33 files / 125 tests`、lint/typecheck/build、生产依赖审计 0 个已知漏洞；固定离线评测 `60/60`、验收门禁通过，外部模型调用 0。针对工作台的两个浏览器重试场景通过。
- 严格端到端套件本轮未执行：Docker Linux 引擎管道缺失。两项文件符号链接测试因本机 Windows 无创建权限跳过；目录联接测试已执行。真实模型、费用精度和刷新后的未完成提交恢复仍不在已验证范围。
- 详细修复表与边界见 `docs/v5_8_1_hardening/acceptance.md`；既有 V5.8 成绩和历史记录不改写。

<!-- stage:v5-9-research-journey-20260927 -->
### V5.9 三资料对比研究流程候选交付

- 固定基线 `dae1bccd3837b582216e753a7f931ef918658218`，分支 `codex/v5.9-research-journey`。本轮复用现有 Agent、来源目录、运行记录、证据深链与反馈，不引入新的模型或数据表；产品显示版本仍为 V5.8 / 5.8.0。
- 工作台增加三文档准备状态、同空间上传返回、维度驱动的只读对比请求、真实服务缺项提示；录制样例增加第三份独立来源与三条可点击引用，并持续标明非真实执行。
- 独立规范/需求审查推动补齐追加日志、状态文案、共用录制场景判定与请求结构测试。录制完成、刷新、审批、取消和引用深链用浏览器操作复核；真实模式的反馈失败保留草稿、普通研究重试 2/2 浏览器回归通过。
- 本轮实测：后端 `787 passed, 2 skipped`；前端 `38 files / 149 tests`，lint、typecheck、正式 build 通过；生产依赖审计 0 个已报告漏洞；固定离线评测 `60/60`、外部模型调用 0。
- Docker Linux 引擎不可连接，严格真实服务 E2E 未执行；真实模型、真实文档上传完成及反馈成功落库也未在本轮实测。详细边界见 `docs/v5_9_research_journey/acceptance_report.md`，通俗实现见同目录 `upgrade_explained.md`。

复审补充（2026-09-27）：规范轴无确定违规；需求轴指出反馈成功页面缺验收。随后增加可重复的浏览器回归 `frontend/e2e/v5-9-research-journey.spec.ts`，三项通过，覆盖三资料门槛、知识空间隔离和受控反馈成功确认。受控成功响应不等于真实数据库落库，严格真实服务验收仍保持未完成。

<!-- stage:v5-10-research-reliability-20261002 -->
### V5.10 研究可靠性实施与交叉复核

- 固定基线 `99b47827ecf0df0df433d5bf69246b04305b2441`；统一工作分支 `codex/v5.10-research-reliability`，产品显示版本仍为 V5.8 / 5.8.0，不改数据库模式或宣称正式发布。
- 已实施完整显式来源验证、固定版本内已采纳来源覆盖、审批发布重查和未发布草稿转缺口报告；定量冲突检查保留主体、指标、时期、英文词边界及明确单位换算，模型采纳候选后也执行检查。
- 工作台分开保存标签页草稿与原始待确认提交；损坏、过期、失效来源和存储拒绝有明确处理，已知真实/录制任务恢复保持原编号，运行结果增加缺口报告入口。
- 运行检查默认不探测付费模型；失败非零退出，跳过不记为浏览器通过，新增只限定受控文件且只管理自有进程的浏览器回归入口。
- 实际产品窗口负责页面；实际 Agent 与 Runtime 窗口因统一目录写权限限制承担独立复核，实施单元负责对应后端/脚本；集成窗口核对合同，主窗口统一测试和文档，未在旧目录各改一份版本。
- 最终验收收口中；初次全量、浏览器和类型检查失败均保留，不把可发现的用例或历史成绩当本轮通过。最新实测、双轴复审及未验证边界见 `docs/v5_10_research_reliability/acceptance_report.md`；通俗实现见同目录 `upgrade_explained.md`。

<!-- stage:interface-polish-20261004 -->
### 页面体验：紧凑工作台、可核对的状态图与顺畅操作

- 在统一工作树进行 UI 增量，保留未提交的 V5.10 可靠性改动；不改后端、数据库、模型、包依赖或产品版本。
- 拉取 shadcn/ui 与 Tremor 官方源码作为只读设计参考，记录固定提交和许可；不直接复制组件、不执行参考脚本、不提交嵌套仓库。
- 四核心入口统一中性配色、紧凑标题和侧栏；工作台资料选择常驻并可搜索，资料库增加列表/卡片、数量和可刷新恢复的地址筛选。
- 运行页增加公开阶段、证据分布、步骤预算，等待状态不高亮旧执行阶段，不伪造完成率；原引用参数和演示身份保持。
- 使用整列表 memo、延后筛选和离屏绘制减少不必要工作；修复移动菜单跨断点残留 inert、折叠入口焦点逃逸和重复预算配置。
- 最终前端 41 文件 / 171 测试、lint、typecheck、生产 build（39/39 静态生成）通过；原有 20 项受控浏览器回归两次通过，最后一次经父门禁运行并定向清理自有服务进程。两轴独立最终代码复核均无遗留发现。
- 实际查看桌面/手机、列表/卡片；操作资料搜索保留选择、刷新保留筛选、固定来源退出、草稿恢复及演示审批到成果引用；手机正反 Tab、Esc、拉宽恢复和减少动态效果通过。
- 本轮不是 V5.10 后端最终全量或真实模型验收，没有 GitHub 提交/推送/合并、公网部署和性能百分比结论。详情见 `docs/interface_polish_20261004/acceptance_report.md`，易懂实现见同目录 `upgrade_explained.md`。

界面收尾补充（2026-10-04）：正式预览复核推动增加终止态反例，完成/失败/取消/证据不足均只标最后上报阶段，不保留当前高亮。小修后重新执行 lint、typecheck、171 项单元测试和生产构建全部通过；正式构建版本第三次运行原有受控浏览器流程，20/20 通过（25.2 秒）。预览服务已启动在 `http://127.0.0.1:3100/workbench?demo=1`；它是固定演示预览，不是实际大模型研究。

<!-- stage:github-sync-20261004 -->
### GitHub 同步前验证

- 用户明确要求同步全部修改；范围包括原 V5.10 研究可靠性、运行恢复与检查脚本，以及本轮界面改造、测试和说明。
- 统一分支 `codex/v5.10-research-reliability`，远程仓库 `https://github.com/DZH166/AI-Knowledge-OS-Pro.git`；主分支仍为基线 `99b47827ecf0df0df433d5bf69246b04305b2441`，本次不直接合并主分支或发布版本。
- 推送前重新运行完整后端：`867 passed, 2 skipped`（719.98 秒）；编译检查通过；前端完整单元 `41 files / 171 tests` 再次通过。严格真实服务及真实模型仍未验收。
- 45 个代码、测试、忽略规则与说明文件纳入提交范围；密钥检查无发现、禁止提交文件 0 项。下载参考仓库、截图、日志、数据库、环境配置和缓存保持本地忽略。

同步完成补充（2026-10-04）：代码提交 `6bf8711e826a84150ad0615513cb0fed2587e2bb` 已推送至 `origin/codex/v5.10-research-reliability`；查询远程返回相同编号。后续按用户要求，在阶段验收后提交、推送并核对远程，不仅保留本地修改。本次未合并主分支或宣布正式发布。

<!-- stage:main-merge-review-20261004 -->
### 主分支合并前的完整审查与最终验证

- 用户授权审查后合并 main；主窗口固定基线 `99b47827ecf0df0df433d5bf69246b04305b2441`，两个独立只读审查单元分别检查整个分支的工程规范和需求规格，另对修复逐轮复审。
- 补齐简单中文省略“为”的同语境数字冲突，防止否定、可能和近似表达误报；公开任务到成果流程新增 20 项反例，最终可靠性文件 66 项通过。原始失败与限定规则的边界保留。
- 冻结代码完整后端 `887 passed, 2 skipped`（926.17 秒）；编译、10 项快速门禁、密钥和禁止文件检查、差异空白检查通过。两项文件符号链接反例受 Windows 权限限制跳过，目录联接反例已执行。
- 前端 lint/typecheck、41 文件 / 171 单元测试通过；正式前端源码未变，沿用 39/39 构建通过证据；原有三份受控浏览器流程再跑 20/20（32.9 秒）。
- 最终规范轴无书面违规，保留 2 项低优先级重复逻辑维护建议；需求轴已发现的功能问题均关闭、无范围扩张。详情见 `docs/v5_10_research_reliability/acceptance_report.md` 和 `audit_findings.md`。
- 严格真实服务、真实模型、公网部署与正式发布仍不在通过范围。此条记录合并前验收，实际远程合并将在完成后追加，不提前宣称保存成功。

主分支合并完成补充（2026-10-04）：修复提交 `e597f77492fd06f8a70789b24c200b034c6a702c` 先推送至工作分支并核对一致；重新获取远程 main、确认基线未变化及祖先关系后，通过 `--ff-only` 快进合并并推送 main。远程查询返回相同提交编号，本地/远程为 `0 / 0`，工作树干净。没有强制推送、丢弃历史、删除分支或触及其他工作树。本补充仅记录已经发生的合并，不将代码合并说成真实模型验收或正式发布。

<!-- stage:v5-11-trusted-research-experience-20261013 -->
### V5.11 可信研究体验：分窗实施与统一验收

- 固定基线 `ddb4f04291a221da60a74fa498a0cb81324fa64a`；分支 `codex/v5.11-trusted-research-experience`。产品显示版本不变，不改数据库结构或配置真实模型。
- 用户授权并行窗口实施；产品体验窗口负责上传、成果正文和移动证据，当前任务的实施智能体负责条件核验和运行器，根窗口接入运行页并负责重连、整合、全量验收和 Git。所有代码在最新 v57 工作树，旧 D 盘副本不重置、不覆盖。
- 数字结论保留前置限制条件；非数字与多行引用、独立证据边界均增加公开测试，Agent 成果流程验证拒绝丢条件改写并保留原文引用。
- 页面区分连接、重试与真正同步，按游标有限重连但不重放写入；上传显示真实后台阶段，成果安全渲染 Markdown，手机证据使用可关闭且返回焦点的面板。
- 浏览器运行器以进程归属容器清理本次后代，保留独立日志；日志目录同步从源码归档、编码检查排除。真实父先退/失败/超时及无关进程保护已有回归。
- 整合过程发现旧界面扫描误拦合法成果代码块，已用精确许可和保留调试输出拦截的反例修复。初次全量失败不算通过，验收收口记录见 `docs/v5_11_trusted_research_experience/acceptance_report.md`。
- 本条记录实施范围，不提前宣称最终验收、GitHub 推送、主分支合并、真实模型效果或正式发布完成。

<!-- stage:v5-11-final-review-20261013 -->
### V5.11 独立审查后的收口

- 需求审查发现终态任务的事件历史可能未收齐，已以失败反例修复，并经独立公开入口复核；工程审查和需求审查分开记录在 `docs/v5_11_trusted_research_experience/audit_findings.md`。
- 运行保障补齐 POSIX（Linux/macOS 进程接口）身份保留与丢失归属后拒绝发信号，最终本机全后端 `935 passed, 4 skipped`；Linux 云端另行完整执行，不与 Windows 数量相加。
- 生产依赖安全扫描发现的问题以兼容补丁修复；开发工具补丁保留官方来源和锁文件，非必要 Vite 升级因版本范围不匹配退回原兼容版本。开发工具仍有一条无上游修复的高危告警链，具体边界在验收文档披露。
- 云端旧 E2E（从页面到服务的端到端流程）两项失败已在本机复现并修复：更新页面定位及资料索引测试数据，保留业务断言，最终两项通过。没有用演示数据伪装真实模型接通。
- 补丁后的前端 46 文件 / 203 单元测试、静态/类型检查、39/39 页面正式构建和生产依赖审计通过。本条不提前记主分支合并；后续最终浏览器、归档和远端状态以本阶段验收记录及 GitHub 实际状态为准。

合并前验收补充（2026-10-13）：最终依赖下前端完整门禁再次通过，受控浏览器 30 项和旧流程 2 项全部通过；桌面及手机截图重新实看。云端 `2fe7033` 的 CI `38364887555` 四任务全通过，完整服务 E2E `77 passed`（确定性 demo 供应商，不是实际模型质量）。本地归档审查快照 887 文件、清单和内容校验通过；最终文档提交后仍会重建并校验交付快照。具体提交后的云端与主分支结果以 GitHub 和交付回执为准，不提前改写为完成。

<!-- stage:v5-11-navigation-budget-20261019 -->
### V5.11 最后云端结果与导航等待复核

- 重新获取远端确认 main 仍为原基线、工作分支为 `c80168c`。该提交 CI `38366665201` 四任务成功，后端 936 通过 / 3 跳过；浏览器是 76 通过及 1 项重试通过，保留首轮成果导航 15 秒超时记录。
- 仅移除成果 URL 断言的局部 15 秒覆盖，沿用现有 30 秒预算；临时 18 秒导航响应延迟先复现失败，再验证通过（两项、48.7 秒）。随后移除人为延迟，保留所有审批、刷新、成果与来源身份断言；没有改产品逻辑或全局预算。
- 2026-10-19 生产依赖在线审计仍为 0 告警，完整审计保留同一条开发链的 5 个高危节点。真实模型效果与云端已有服务异常日志仍分别保留边界，不以测试成功宣称全部已解决。
- 本条记录收口前已发生的核查，最终提交的云端结果、归档及主分支同步仍以最后交付回执为准。

<!-- stage:v5-12-reliable-chinese-retrieval-20261020 -->
### V5.12 后台异常与中文检索实施

- 按授权顺序先以真实 SQL Agent 和 HTTP（网页请求接口）复现缺失任务的流响应错误，再在发送成功响应头之前复用公开任务查询；11 项新回归连同旧接口/运行时共 39 项通过。真实独立服务另有 1 项 HTTP 检查通过，事件格式、游标恢复与空终态语义保留。
- 共享字面检索模块统一全角/大小写、中文相邻两字/三字片段及英文数字规则；重复词项饱和计分，SQL 规范得分由混合检索直接复用。固定历史版本和来源的交集在候选限额之前过滤，18 项新检索回归连同旧合同共 57 项通过。
- 锁定 24 个手工题目和摘要，20 个正例两条路径首位命中由 45% / 60% 提升至 100%，4 个无答案反例均正确为空、身份/范围违规 0。只是小型合成题集，不代表真实资料或真实大模型效果。评测器与基线一致性已独立审查，另有 6 项评测回归防止隐瞒漏召回或把严格安全门槛冒称准确率。
- 实现检查点 `eac2253` 后开始完整后端、前端与浏览器验收。首轮工程审查要求补齐两份追加日志，本次只在末尾追加、不重写历史；最终审查、云端、归档与主分支结果以本阶段验收记录和 GitHub 实际状态为准，不提前记为完成。


<!-- stage:v5-13-operational-quality-20261107 -->
### V5.13 全量质量审查、存储保证与界面收口

- 在干净 venv 中复现基线：后端全量 `11 failed / 89 errors / 876 passed`。根因不是同一个：`BACKEND_CORS_ORIGINS` 按文档逗号写法会让 Settings 启动崩溃；Windows 下 ffmpeg 子进程按 ANSI 解码失败，把视频时长退化成 1ms 并级联出 80+ 个错误；另有两项测试子进程编码不一致。
- 修复 CORS 的 `NoDecode` 兼容解析、ffmpeg/ffprobe 显式 UTF-8、测试子进程 `PYTHONIOENCODING`；修复证据资料库“活跃版本恒为 0”、Chunker 显式 0/重叠不前进、上传未 fsync、SQLite `synchronous` 未显式设置等真实缺陷。
- 新增只读存储自检（SQLite integrity/foreign key/journal、文件存在性/大小/可选 SHA-256、active revision/index 台账、孤儿文件）、证据资料库存储完整性面板、SQLite 在线备份与逐文件 manifest、验证后恢复与旧副本保留；修复演示种子把哈希写成固定 fixture 标识导致字节漂移的问题。
- 后端最终全量 `1014 passed, 4 skipped, 0 failed`（1178.72 秒）；固定 60 案例 Agent 评测 `60/60`，全部硬门禁通过；中文检索 24 题严格模式双路径 Hit@1/5=1.0；Demo RAG 引用评测 `result=passed`。前端 lint/typecheck/unit（47 文件 / 206 测试）/build（39 页面）通过。
- 浏览器：生产构建 + `next start` 下 59 项自包含流程全部通过；生产构建首次暴露工作台静态预渲染只输出 Suspense 占位，改为 `force-dynamic` 后延迟脚本回归通过。开发服务器并发 79 项 68 通过，失败集中在未启动 Redis/Qdrant/Worker 的实时链路与首轮冷编译；实时服务全链路仍未验收。
- 生产依赖在线审计发现 Next 15.5.27（critical：Image Optimization SVG RCE / Server Actions DoS）与 zod 4.4.x（high：集合校验内存耗尽），升级到 Next 15.5.29 / zod 4.6.6 / vite 8.3.6 后生产审计为 0 vulnerabilities；完整审计保留 8 个 moderate 的 @typescript-eslint 开发链告警，无 high/critical。随后重新跑 lint/typecheck/unit/build 与浏览器回归。
- 界面：摄取、任务、学习、媒体详情统一中文；原生 file input 不再露出英文；五列工作流与四列网格补充 1180/1024 断点；面包屑对 source/number/UUID 可读化；工作台增加 AI 服务准备度提示和 Ctrl/Cmd+Enter 提交。
- AI：Agent 计划/追问/综合要求与目标同语言；聊天短追问把上一轮问题带入检索，但回答、历史与引用仍只对应原始问题。以上均为本地合成/录制验证，不代表真实模型质量。
- 详情见 `docs/storage_integrity.md`、`docs/v5_13_operational_quality/audit_report.md` 与 `acceptance_report.md`。未合并 main、未推送、未发布版本。
