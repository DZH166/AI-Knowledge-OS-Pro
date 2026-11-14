# V5.13 运营质量与存储保证：验收记录

日期：2026-11-07（Asia/Shanghai）。产品显示版本保持 V5.8 / 5.8.0；本阶段不声称真实模型质量、云部署或生产级高可用。

## 范围

范围、边界与交付物见 [spec.md](spec.md)；基线、根因和逐项修复见 [audit_report.md](audit_report.md)。本文件只记录实际执行过的检查，未执行的项目明确标注为边界。

## 后端

| 检查 | 结果 |
| --- | --- |
| `ruff check backend/app backend/tests scripts` | 通过 |
| `compileall backend/app scripts` | 通过 |
| 全量 `pytest backend/tests` | **1014 passed, 4 skipped, 0 failed**（1178.72 秒） |
| 固定 60 案例 Agent 评测 | **60 / 60**，`check_v5_acceptance.py` 全部硬门禁通过，`failures=[]` |
| 中文检索评测（24 题，严格模式） | 双路径 Hit@1/5 = 1.0，MRR = 1.0，负例 4/4 为空，范围/身份违规 0 |
| Demo RAG 引用评测 | `result=passed`；1 条 grounded、1 条拒绝、1 条有效引用、9 个 locator 全部有效 |
| Demo 全量回归 | `check_full_regression.py` 67 项检查通过（来源、版本、任务、媒体、学习与导航一致性） |
| 存储自检（示例库，deep hash） | `ok=true`；4 个 active source、8 个引用文件、0 缺失、0 孤儿、5 个指纹核对通过 |
| 备份 + 验证 CLI | 8 个上传文件、1.4 MB 数据库；manifest 与逐文件 SHA-256 复核通过 |
| 恢复 CLI（不同上传根目录） | `restore_storage.py --force` 成功；4 个来源、1 个知识空间、8 个上传文件恢复；重写 14 条存储路径，随后 `--deep-hash` 自检 0 缺失、0 孤儿 |

## 前端

| 检查 | 结果 |
| --- | --- |
| `npm run lint` | 通过（`--max-warnings=0`） |
| `npm run typecheck` | 通过 |
| `npm run test:unit` | 47 文件 / 206 测试通过（新增存储面板、模态与来源标签测试） |
| `npm run build` | 通过（Next 15.5.29）；39 个构建页面 |
| 生产依赖审计 | `npm audit --omit=dev --audit-level=high` → **0 vulnerabilities**；完整审计仍有 8 个 moderate 的 @typescript-eslint 开发链告警（无 high/critical） |
| 横向溢出与单 h1 巡检 | 390 / 768 / 1024 / 1440 宽度 × 12 个路由，48 个组合均无横向溢出且只有一个 h1 |
| 无障碍页面巡检 | 12 个路由：单 h1、按钮可访问名称、图片 alt、无横向溢出，全部通过 |
| 项目快速质量门 | `check_all.py --quick` 10 项全部通过：编码、版本、文档链接、README 资产、前端 smoke、UI 性能预算、交互反馈、请求缓存、E2E 脚手架、CI 产物 |

## 浏览器

- **生产构建 + 生产服务器（`next start`）**：59 项自包含浏览器流程**全部通过**（2.0 分钟），覆盖 demo-smoke、恢复/重连、产物上传、引用面板、移动端、observability、12 项无障碍页面巡检、工作台初始化与幂等重试。
- 生产构建首次暴露 `/workbench` 静态预渲染只输出 Suspense 占位的问题；改为 `force-dynamic` 后，延迟脚本回归通过，首屏即为 disabled 表单。
- 开发服务器一次性并发 79 项时，68 passed / 11 failed；失败集中在未启动 Redis/Qdrant/Worker 的实时链路和首轮冷编译，逐项复跑可区分环境限制。
- 本机 Docker daemon 未运行，Redis、Qdrant 与 Worker 未启动；因此实时服务链路不作为本阶段通过项。

## 存储保证

- SQLite：WAL + `synchronous=FULL` + 外键约束；只读自检覆盖 `integrity_check`、`foreign_key_check`、journal mode、页数与磁盘空间。
- 上传：写入后 `flush`/`fsync`，核对实际文件大小；失败删除残留文件并返回可读错误。新增两项上传持久性测试。
- 证据台账：active revision / active index revision 的存在性、归属、状态、片段数与向量数、重复 active、悬空索引引用。
- 边界状态：损坏数据库返回 `database_unreadable`，未迁移的空库返回 `database_schema_incomplete`，两者都不以未处理异常结束。
- 文件：存在性、声明大小、可选 SHA-256、孤儿文件；备份前与数据库登记指纹交叉核对，不一致则拒绝生成备份。
- 备份/恢复：SQLite 在线备份 API、逐文件 manifest、创建后立即复核；恢复前完整验证并保留旧数据库/旧上传目录副本。
- 演示种子：来源和文档的内容指纹改为实际文件字节的 SHA-256；修正第二份文档的路径、大小和哈希。


## 复现命令

```powershell
# 后端
python -m compileall backend/app scripts
python -m ruff check backend/app backend/tests scripts
python -m pytest backend/tests -q

# 评测
python scripts/evaluate_agentic_rag.py --mode demo --output .controlled_browser_logs/agentic_eval.json
python scripts/check_v5_acceptance.py --report .controlled_browser_logs/agentic_eval.json
python scripts/evaluate_chinese_retrieval.py --strict
python scripts/evaluate_rag.py --demo

# 存储
python scripts/check_storage_integrity.py --deep-hash
python scripts/backup_storage.py --output .controlled_browser_logs/backup.zip
python scripts/backup_storage.py --verify .controlled_browser_logs/backup.zip
python scripts/restore_storage.py --archive .controlled_browser_logs/backup.zip --database-url "sqlite:///.controlled_browser_logs/restore/restored.db" --upload-dir .controlled_browser_logs/restore/uploads --force

# 前端
cd frontend
npm run lint
npm run typecheck
npm run test:unit
npm run build
$env:E2E_BASE_URL="http://127.0.0.1:3000"
$env:E2E_SKIP_WEBSERVER="1"
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npx playwright test --config=playwright.config.ts --workers=1
```

## 明确边界

- 演示数据、合成评测和本地测试通过不等于真实模型答案质量；真实 Provider 未配置时系统仍明确拒绝。
- 备份归档不加密，也没有云端复制；跨机高可用不在范围内。
- `storage-health` 是只读检查，不自动修复内容冲突；Qdrant point 级一致性仍由 `scripts/reconcile_evidence_index.py` 负责。
- 浏览器实时链路、Linux 进程生命周期和 Windows 符号链接权限仍受本机能力限制。
