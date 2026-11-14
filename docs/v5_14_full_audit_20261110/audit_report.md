# 溯知 Evidence OS：全量审查报告

审查日期：2026-11-10（Asia/Shanghai）
审查对象：`<PROJECT_ROOT>`，HEAD `eac2253`
产品版本：V5.8 / 5.8.0（仓库内同时存在 V5.12、V5.13 的 WIP 文档）
审查方式：全量质量门 + 关键代码路径阅读 + 评测复跑；不修改业务代码。

## 1. 结论

项目已经具备“可演示、可回归、可解释”的工程底座：证据不可变、任务可恢复、存储可自检/备份/恢复、中文检索有离线评测、前端有 59 项生产构建浏览器回归。

但它目前更像**单机研究工作台**，还不是可直接暴露到公网的产品：

- 应用层没有认证/授权，150 个 API 路由默认开放。
- 评测隔离存在缺口：运行过聊天后，`evaluate_rag.py --demo` 会因工作库多出的 QA 日志而失败；新种子库则通过。
- 实时链路（Redis/Qdrant/Worker）没有被本地或 CI 的浏览器回归真实覆盖。
- 备份只覆盖 SQLite 与上传文件，不包含 Qdrant 向量库，也没有自动恢复演练。
- 多个核心文件过大，`evidence_agent/controller.py` 已达 132 KB；后续功能继续堆叠会显著增加回归成本。

**审查判断（非行业基准）**

| 维度 | 判断 | 说明 |
| --- | --- | --- |
| 功能与正确性 | 8.5 / 10 | 主链路完整，边界与失败补偿做得细 |
| 测试与回归 | 8.0 / 10 | 1014 后端 + 206 前端 + 59 浏览器；缺真实服务与覆盖率门 |
| 存储与恢复 | 8.5 / 10 | 自检/备份/异目录恢复有证据；缺向量库与定时演练 |
| RAG / AI 证据 | 7.0 / 10 | 合成评测扎实，真实模型质量仍未测量 |
| 安全（仅本机） | 8.0 / 10 | 本机风险可控；上传/分享/异常信息仍需收口 |
| 安全（若公网） | 5.5 / 10 | 无认证、无 CSP、无限流，不能直接暴露 |
| 可维护性 | 7.0 / 10 | 分层清楚，但存在 4 个体量过大的核心文件 |
| 可观测/运维 | 6.0 / 10 | 有请求 ID 与页面；缺指标、追踪、审计日志与部署编排 |
| UI/UX | 8.5 / 10 | 分区清楚、中文一致、响应式与无障碍回归通过 |

## 2. 实际执行的验证

| 检查 | 结果 |
| --- | --- |
| `compileall backend/app scripts` | 通过 |
| `ruff check backend/app backend/tests scripts` | 通过 |
| `pytest backend/tests` | **1014 passed, 4 skipped, 0 failed**（1662.92 秒，含并发 E2E 负载） |
| `pip check` | 无损坏依赖 |
| `alembic heads` | `0017_reviewed_feedback (head)` |
| 前端 `lint` / `typecheck` | 通过 |
| 前端 `test:unit` | **47 文件 / 206 测试**通过 |
| 前端 `build` | 通过；38 个静态页 + 1 个动态页；共享 JS 103 kB |
| 生产构建浏览器回归 | **59 / 59 通过**（2.1 分钟） |
| 固定 Agent 评测 | **60 / 60**；citation completeness 1.0；immutable identity 1.0；unauthorized 0；hard gates 全过，`failures=[]` |
| 中文检索严格模式 | 20 正例 + 4 负例；Hit@1/5 = 1.0；MRR = 1.0；负例 4/4 为空；scope/identity 违规 0 |
| Demo RAG（新种子库） | `result=passed`；9 个 locator 全部有效；2 个代码 locator |
| Demo RAG（当前工作库） | **failed**：多出 4 条 `retrieval_status=success` 的聊天日志 |
| 存储自检（deep hash） | `ok=true`；8 个引用文件、5 个指纹、0 缺失、0 孤儿 |
| Demo 全量回归 | 67 项检查通过 |
| 快速质量门 | `check_all.py --quick` 10 项全部通过 |
| 生产依赖审计 | `npm audit --omit=dev` → 0 vulnerabilities |
| 全量依赖审计 | 8 个 moderate（@typescript-eslint / minimatch 开发链），无 high/critical |
| 编码/版本/文档链接/密钥/仓库清洁 | 全部通过（931 个 UTF-8 文件、230 个文档、58 个本地链接、0 密钥发现） |

证据文件：

- [Agentic 评测报告](evidence/agentic_eval.json)
- [Agentic 验收门](evidence/agentic_acceptance.json)
- [中文检索报告](evidence/chinese_retrieval.json)
- [新种子库 RAG 报告](evidence/rag_fresh_seed.json)
- [当前工作库 RAG 失败报告](evidence/rag_working_db_failure.json)

## 3. 关键发现

### P0：评测隔离失效，质量门会被运行态污染

`evaluate_rag.py --demo` 默认读取 `backend/data/demo_showcase.db`，并校验**所有** `qa_logs`。演示库在聊天、E2E 或手工试用后会追加 `retrieval_status=success` 的记录；评测器只接受 `grounded` / `insufficient_context`，于是工作库失败，而新种子库通过。

现场证据：

- 当前工作库 `qa_logs=6`，评测失败 4 条；
- 新建种子库 `qa_logs=2`，评测 `result=passed`；
- 失败报告与通过报告已同时保存在 `evidence/`。

影响：**验收数字不可复现**。同一份代码，换一个“用过”的库就红。CI 目前没有跑 `evaluate_rag.py`，所以这个问题没有被 CI 捕获。

建议：评测必须使用隔离数据库（临时种子库或只读快照），或在种子 QA 上写入稳定来源标记；工作库只用于产品验收，不作为评测输入。验收标准：连续进行 10 次聊天后，评测仍然只评估种子记录；故意破坏一条种子记录时，评测仍必须失败。

### P1：应用层没有认证/授权，默认假设“只有本机能访问”

`backend/app/main.py` 只注册了 CORS、请求 ID 与统一响应中间件；没有认证依赖、权限校验或 workspace 隔离。150 个 `/api` 路由默认开放，上传文件、运行轨迹、分享链接、备份/恢复能力都可通过本机端口访问。

当前定位是个人本机工作台，这可以接受；但一旦绑定 `0.0.0.0`、放到反向代理后或做多人演示，就是高风险暴露面：

- 任何能访问端口的人都能读写资料、触发模型调用、下载上传文件；
- CORS 允许携带凭据，但没有会话认证；
- 分享链接使用 32 字节随机 token、1–30 天过期、可撤销，这一点设计是好的，但创建分享链接本身不需要认证。

建议：明确“仅本机”边界并默认绑定 `127.0.0.1`；若要联网，先加认证（反向代理 Basic/OIDC 或应用内会话）、workspace 级授权和 CSRF 策略，再开放端口。

### P1：Web 安全头、限流与请求体上限缺失

`frontend/next.config.ts` 没有 `headers()`，未设置 CSP、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy`；后端没有 `TrustedHostMiddleware`、HTTPS 重定向、限流或全局请求体大小限制。上传接口有 25 MB 限制，但普通 JSON 接口没有。

建议：在反向代理或 Next 层加安全头；后端加请求体上限与基础限流；生产环境关闭或保护 `/docs`、`/openapi.json`；分享链接页面加 `Referrer-Policy: no-referrer`。

### P1：实时服务链路没有被 CI 真实覆盖

本次本机没有 Redis/Qdrant/Worker，59 项浏览器回归全部是自包含/模拟链路；全量 79 项在早前运行时，实时任务相关用例会因服务缺失失败。CI 的 `browser-e2e` 使用 demo 服务器，不能证明“上传 → RQ Worker → Qdrant 索引 → 检索 → 引用”在真实服务下成立。

建议：在 GitHub Actions 用 service containers 启动 Redis/Qdrant，再启动一个 Worker，增加一条真实链路 smoke；至少覆盖：上传小文档、任务完成、检索命中、引用 locator 有效、失败重试。

### P1：备份不覆盖向量库，也没有恢复演练

`storage_backup.py` 覆盖 SQLite + 上传文件，并能在异目录恢复时重写路径；但 Qdrant 是独立状态。恢复到新机器/空 Qdrant 后，词法检索可能仍工作，dense 检索会缺 point；项目文档已说明“不验证外部 Qdrant”，但没有自动重建步骤。

建议：备份 manifest 记录 Qdrant collection/alias/版本；恢复流程增加 Qdrant snapshot 或“从 SQLite + 原始文本重建向量”的明确 runbook；每季度做一次恢复演练并记录耗时。

### P1：Python 依赖没有锁文件

`backend/requirements.txt` 使用范围约束，没有 hash/lock；本地 Python 3.12.9，CI Python 3.12，前端 CI Node 20、本地 Node 24。前端有 `package-lock.json`，后端没有等价物。

建议：用 `uv.lock` 或 `pip-compile --generate-hashes` 生成锁定文件，CI 用 `--locked` 安装；加 Dependabot/Renovate；补 `.python-version` 与 `.nvmrc`。

### P2：核心文件过大，后续迭代成本上升

| 文件 | 大小 | 风险 |
| --- | ---: | --- |
| `backend/app/modules/evidence_agent/controller.py` | 131.8 KB | 运行状态机、检索、评估、综合、持久化混在一起 |
| `backend/app/modules/agent_policy_optimizer/service.py` | 77.2 KB | 优化循环与报告/实验耦合同一文件 |
| `backend/app/services/media_service.py` | 76.3 KB | 图片/音频/视频/OCR/关键帧共用一个大服务 |
| `backend/app/modules/evidence_index/sql.py` | 50.4 KB | 索引命令与 SQL 细节集中 |
| `frontend/components/evidence-agent/Workbench.tsx` | 41.7 KB | 29 处 hooks/API 调用、13 个内部函数 |

复杂度扫描（ruff C901，阈值 15）只有 9 个函数超阈值，最高 `_signal` 38；问题更多是“文件级耦合”，不是单函数不可读。

建议：按用例拆 controller（提交/推进/检索/综合/查询），media 按媒体类型拆，Workbench 拆为表单、来源选择、恢复状态、提交四个组件；先抽纯函数与类型，不改变 API。

### P2：前端缺路由级错误边界与加载骨架

`frontend/app` 下没有 `error.tsx`、`global-error.tsx`、`loading.tsx`、`not-found.tsx`。局部请求错误有处理，但渲染异常会落到 Next 默认错误页；慢页面也没有统一骨架。

建议：增加根级 `error.tsx`（带 reset 和 request_id 展示）、`global-error.tsx`、`not-found.tsx`，关键路由加 `loading.tsx`；用 Playwright 注入一次渲染错误验证。

### P2：可观测性有“页面”，缺“指标与审计”

已有请求 ID、统一 envelope、系统/observability 页面；但没有 Prometheus/OpenTelemetry、任务失败率/队列深度/检索延迟指标，也没有安全审计日志。两处 `except Exception: pass`（任务重试入队、取消补偿）会静默吞掉队列故障。

建议：加 `/metrics` 与结构化审计事件（登录/上传/分享/恢复/策略启用），把被吞异常至少记录 warning + job_id；对“任务长时间 queued”“存储自检 error”做告警。

### P2：文档指标漂移

README 仍写“多跳提升 +58.33 percentage points”；本次复跑为 **+33.33 pp**。这不是回归：V5.12 词法检索把单次检索代理的多跳成功率从 41.67% 提升到 66.67%，Agent 仍是 100%，所以“相对提升”自然收窄。

建议：README 同时写绝对值和基线变化，注明报告日期/数据版本；不要把“相对提升变小”误读为 Agent 变差。

### P3：CI/版本卫生

- CI 上传 artifact 名称仍是 `suzhi-evidence-os-v5.2`，与 V5.8 不一致。
- `eslint-config-next` 固定 15.5.27，而 Next 已升到 15.5.29。
- 仓库同时存在 V5.8 产品版本与 V5.12/V5.13 WIP 文档，缺少一张版本/文档状态矩阵。
- 无 `pyproject.toml`，ruff/pytest 配置分散。

## 4. 做得好的地方

- **证据身份**：Revision/Index/Chunk/hash/locator 绑定完整，固定评测中 immutable identity = 1.0。
- **失败关闭**：真实模式 Qdrant 不可用会抛错，不在真实模式静默降级为词法；demo 才允许降级。
- **恢复语义**：checkpoint、event journal、outbox、命令幂等、取消 fence 都有测试；不是“前端假装恢复”。
- **存储**：上传 fsync、SQLite `synchronous=FULL`、只读自检、哈希 manifest、备份后复核、恢复保留旧副本，这套组合在个人项目里少见。
- **测试纪律**：1014 后端测试、206 前端单测、59 生产构建 E2E、60 案例固定评测；没有 TODO/FIXME，没有 `as any`/`ts-ignore`。
- **依赖安全**：生产依赖 0 漏洞；开发链只剩 moderate。
- **UI**：主路径收敛为四个入口，中文一致，响应式和无障碍回归通过。

## 5. 建议的下一步

按“先可信、再安全、再规模”的顺序推进，详细任务与验收标准见 [upgrade_roadmap.md](upgrade_roadmap.md)；如果目标是校招作品，另见 [校招项目竞争力审查](campus_portfolio_review.md)。

**本周内（1–2 天）**

1. 修评测隔离，补“污染库仍通过、破坏种子仍失败”测试。
2. 修 CI artifact 名称、README 指标说明、`eslint-config-next` 版本。
3. 加根级错误边界、`not-found`、关键路由 loading。
4. 给两处静默异常加日志。

**两周内**

5. 明确本机边界并默认 loopback；若要联网，先做认证/授权。
6. 加安全头、请求体上限、基础限流。
7. CI 加 Redis/Qdrant/Worker 真实链路 smoke。
8. 后端依赖锁定 + Dependabot。
9. Qdrant 快照/重建 runbook + 恢复演练。

**一个月内**

10. 拆 controller / media / Workbench。
11. 文档/列表分页与 FTS5 检索，补规模基准。
12. 指标、追踪、审计日志。
13. 覆盖率测量与门槛。
14. 真实模型（可选、计费隔离）质量评测。

## 6. 审查边界

- 未做真实模型质量评估；60 案例是合成固定语料 + deterministic recording model。
- 本机 Docker daemon 未运行，未验证真实 Redis/Qdrant/Worker 全链路。
- 未做渗透测试、压力测试、故障注入；安全结论基于代码与依赖审计。
- 未评价 GPU/本地模型、云部署成本和多用户并发。
- 未修改业务代码；本报告只记录审查结果与建议。
