# V5.13 全量审查记录（进行中）

日期：2026-11-07。环境：Windows、Python 3.12.9、Node 24.19.0；依赖按 `backend/requirements.txt` 由 pip 解析（FastAPI 0.162.0、SQLAlchemy 2.1.8、pytest 8.x）。

## 基线

| 检查 | 结果 |
| --- | --- |
| 后端全量 `pytest backend/tests` | **11 failed, 89 errors, 876 passed, 2 skipped**（854.55 秒） |
| 前端 `npm run lint` | 通过 |
| 前端 `npm run typecheck` | 通过 |
| 前端 `npm run test:unit` | 46 文件 / 203 测试通过 |
| 前端 `npm run build` | 通过，39 个构建页面 |
| 编码 / 版本 / 密钥 / 文档链接 / 仓库清洁检查 | 通过 |
| 首次浏览器巡检 | CORS 阻断，所有 API 请求失败 |

## 发现与修复

### 1. `BACKEND_CORS_ORIGINS` 按文档写法会导致进程启动崩溃

`.env.example` 写的是逗号分隔，`Settings` 字段却是 `list[str]`。pydantic-settings 会先尝试 JSON 解码，逗号字符串直接抛 `SettingsError`，Uvicorn 无法导入应用。V5.1 演示脚本用 JSON 数组，所以问题被掩盖。

修复：使用 `NoDecode` 注解关闭隐式 JSON 解码，validator 同时接受逗号分隔和 JSON 数组，非法 JSON 返回明确错误。新增 `test_config_cors_origins.py`（5 项）。

### 2. Windows 上 ffmpeg 输出解码失败导致视频元数据变成 1ms

`video_service.py` 的四处 `subprocess.run(..., text=True)` 没有指定编码，Windows 使用 ANSI 代码页读取 ffmpeg 的二进制式 stderr，reader 线程抛 `UnicodeDecodeError`，`probe` 失败后退化为 `duration_ms=1`，并留下大量 reader 线程告警。

修复：所有 ffmpeg/ffprobe 调用强制 `encoding="utf-8", errors="replace"`；测试辅助的 ffmpeg 调用同样处理。新增 `test_video_tooling_encoding.py` 锁定编码合同。修复后视频相关 4 项测试通过，原本由解码失败级联出的 80+ 项错误消失。

### 3. 子进程测试的编码不一致

`test_v4_3_api_regression.py` 和 `test_v5_migration_clis.py` 强制 UTF-8 读取子进程、但子进程按本地代码页输出，导致 `stdout=None`、`json.loads(None)`。修复为两侧统一 `PYTHONIOENCODING=utf-8` 并允许替换解码；两项测试恢复通过。

### 4. 证据资料库「活跃版本」恒为 0

前端把 `source.status === "active"` 当成活跃版本条件；真实来源状态是 `ready`，活跃身份实际由 `active_revision_id` 决定。改为按 active revision 计数，并新增 `activeRevisionCount` 单元测试。

### 5. Chunker 的显式 0 被静默替换，重叠过大可能不前进

`chunk_size or settings.chunk_size` 会把显式 0 换成默认值；`chunk_overlap >= chunk_size` 时窗口不前进。修复：显式 `None` 才使用默认值；启动时校验正数与 overlap 上界，错误信息可读。新增 4 项契约测试。

### 6. 界面中英混排与不可读原生控件

摄取、任务、学习、媒体详情等 Developer Mode 页面存在大量英文标题、空状态和按钮；文档上传器还展示了浏览器原生的英文 “Choose Files”。修复：统一中文文案、把原生 file input 视觉隐藏但保留键盘可达性、5 个摄取工作流卡片改为响应式五列布局、面包屑对 `sources`/数字/UUID 做可读化。

## 修复后验证

- 后端全量：**1014 passed, 4 skipped, 0 failed**（1178.72 秒）。4 个跳过均为平台能力限制（Windows 符号链接权限、真实 Linux 进程生命周期）。
- 变更区域聚焦回归：78 passed（存储、备份、切片、追问检索、Agent 语言、CORS、视频编码、演示脚本、迁移 CLI、模型预算）。
- 前端 lint / typecheck / unit（47 文件 / 206 测试）/ build（39 个构建页面）通过。
- 固定 60 案例 Agent 评测：**60 / 60**，citation completeness 1.0、immutable identity 1.0、unauthorized action 0、multi-hop lift +33.33pp；`check_v5_acceptance.py` 全部硬门禁通过，`failures=[]`。
- Demo RAG 引用评测：`result=passed`，1 条 grounded、1 条拒绝、1 条有效引用、9 个 locator 全部有效。
- 存储自检示例库（`--deep-hash`）：`ok=true`，4 个 active source、8 个引用文件、0 缺失、0 孤儿、5 个内容指纹核对通过。
- 备份 + 验证 CLI：8 个上传文件、1.4 MB 数据库、manifest SHA-256 复核通过；备份会拒绝与数据库登记指纹不一致的文件。

### 浏览器流程

生产构建 + `next start` 下按单 worker 运行 59 项自包含 Playwright：**59 / 59 通过**（2.0 分钟）。开发服务器并发 79 项时为 68 passed / 11 failed，失败项集中在需要 Redis/RQ/Worker 的实时运行与首次冷编译；逐项复跑后相关流程均通过。该结果不冒充实时服务全通过：本机 Docker daemon 未运行，Redis/Qdrant/Worker 未启动。

## 修复后发现的演示数据哈希漂移

示例种子把媒体来源的 `content_hash` 写成固定 fixture 标识，但文件是现场生成的图片/音频/视频，字节哈希并不相同。默认自检只看存在性，问题被掩盖；加入备份哈希核对后才暴露。修复：种子改为对实际写入的文件计算 SHA-256，同时补齐第二份文档自己的文件、大小和哈希。重新播种后 `--deep-hash` 通过，备份也可通过数据库指纹核对。

## 边界

- 以上是本地环境与合成/演示数据的验证，不代表真实模型质量或生产部署保证。
- 最终全量、浏览器全套与构建结果在本阶段收口时更新；未执行的检查不提前记为通过。


### 7. 生产构建下工作台只输出 Suspense 占位，首屏无表单

V5.12 的初始化保护依赖服务端先渲染一个 disabled 草稿。`/workbench` 在 `next build` 中被静态预渲染，`useSearchParams` 使边界退化为客户端渲染，生产 HTML 只有“正在恢复研究工作台…”。开发服务器会动态渲染，所以浏览器测试只在生产构建才暴露。

修复：把工作台路由标记为 `force-dynamic`，让服务端拿到真实 query 并渲染 disabled 表单；客户端 hydration 后再开放编辑。生产构建 + Playwright 延迟脚本回归通过（1.3 秒）。这不是关闭保护，而是让保护在真实构建里生效。


### 8. 生产依赖审计发现一个 critical 与一个 high

`npm audit --omit=dev` 报告 Next.js 15.5.27 的 Image Optimization SVG RCE / App Router Server Actions DoS，以及 zod 4.4.x 的集合校验内存耗尽。修复：Next 固定升级到 15.5.29，zod 升级到 4.6.6，vite override 升到 8.3.6；升级后 `npm audit --omit=dev --audit-level=high` 返回 `found 0 vulnerabilities`。完整 `npm audit` 仍有 8 个 moderate 的 @typescript-eslint 开发链告警，无 high/critical；作为开发工具边界保留。随后重新执行 lint/typecheck/unit/build 与生产构建浏览器回归，未以“审计通过”替代运行时验证。


### 9. 存储自检在空数据库上不应 500

首次启动但尚未执行迁移时，SQLite 文件存在、完整性检查通过，随后查询 `sources` 会抛“no such table”。新增表结构预检：缺少必需表时返回 `database_schema_incomplete` 与明确的 `alembic upgrade head` 提示，不把可恢复的部署状态变成未处理异常。损坏的数据库文件同样返回 `database_unreadable`。

