# 后续升级路线图

本路线图基于 [全量审查报告](audit_report.md) 的实际发现。顺序原则：**先让评测可信，再决定是否联网，最后做规模和体验**。不要在评测隔离和认证之前继续加页面。

## 1. 优先级总表

| 优先级 | 任务 | 解决什么 | 预估 | 验收标准 |
| --- | --- | --- | --- | --- |
| P0 | 评测隔离 | 工作库被聊天污染后 `evaluate_rag.py --demo` 假失败 | 0.5–1 天 | 10 次聊天后仍只评估种子记录；破坏种子仍失败 |
| P0 | 修正 README 指标与 CI artifact 名称 | 验收数字/产物名漂移 | 0.5 天 | README 写明 33.33 pp 与基线变化；artifact 为 V5.8 |
| P1 | 本机边界与认证 | 150 个开放路由、无 workspace 授权 | 2–4 天（本机声明）/ 1–2 周（联网） | 未认证请求 401；跨 workspace 403；默认只监听 loopback |
| P1 | 安全头/限流/请求体上限 | 公网暴露风险 | 2–3 天 | CSP、XFO、Referrer-Policy 生效；超限 413/429 |
| P1 | 实时链路 CI | Redis/Qdrant/Worker 回归缺口 | 2–4 天 | CI 完成上传→Worker→索引→引用 smoke |
| P1 | 后端依赖锁定 | 后端不可复现 | 1–2 天 | `uv sync --locked` 或 `pip install --require-hashes` 通过 |
| P1 | Qdrant 备份/恢复 runbook | 恢复后向量缺失 | 2–3 天 | 空 Qdrant 恢复后 dense 检索可用，或明确重建耗时 |
| P2 | 拆核心大文件 | controller/media/Workbench 耦合 | 1–2 周 | 单文件 < 50 KB；行为测试不变 |
| P2 | 错误边界/加载骨架 | 渲染异常落到默认页 | 1 天 | 注入错误显示 reset；慢路由有骨架 |
| P2 | 指标/追踪/审计日志 | 只看到页面，没有告警 | 3–5 天 | `/metrics`、任务失败率、恢复/分享审计事件 |
| P2 | 列表分页 + FTS5 | 大资料库扫描与全量返回 | 1–2 周 | 1 万文档下 p95 可接受；游标分页 |
| P2 | 覆盖率与隐藏评测集 | 不知道测试覆盖哪里 | 1 周 | 后端覆盖率基线；隐藏 60+ 案例 |
| P3 | 部署编排 | 只有 Redis/Qdrant compose | 3–5 天 | backend/worker/frontend Dockerfile + compose |
| P3 | 真实模型评测 | 合成数据不等于真实质量 | 1–2 周 | 可选 provider、成本/延迟/引用报告 |
| P3 | 多用户/workspace | 单机模型限制 | 2–4 周 | 租户隔离、配额、审计 |

## 2. 第一阶段：让质量门可信（本周）

### 2.1 评测隔离（P0）

**问题复现**

- 当前工作库：`qa_logs=6`，多出的 4 条为聊天产生的 `retrieval_status=success`；
- `scripts/evaluate_rag.py --demo` 读取全部日志，只接受 grounded/insufficient_context；
- 新种子库：`qa_logs=2`，`result=passed`。

**实现选项（推荐 A + B）**

A. 评测 CLI 增加 `--fresh`：在临时目录调用 `seed_showcase.seed()`，评测完删除；CI 与本地默认使用隔离库。
B. 给种子 QA 加稳定标记：例如 `answer_mode="showcase_seed"` 或独立 `origin` 字段；评测只读标记记录。若不想改表，至少按“种子问题集合 + 最早 id 去重”过滤，并在报告里写明过滤规则。
C. 工作库只做产品验收，禁止作为评测输入；文档和脚本帮助文本明确。

**测试**

- 在已聊天的库上跑评测仍通过；
- 人为把一条种子记录改成 `success`，评测必须失败；
- 评测报告记录 `source_database_sha256` 或 `seed_version`，避免“换了库不知道”。

### 2.2 指标与 CI 卫生（P0/P3）

- README 的 `+58.33 pp` 改为当前值 `+33.33 pp`，并解释：V5.12 词法检索把单次检索代理的多跳成功率从 41.67% 提升到 66.67%，Agent 仍为 100%，所以相对提升收窄。绝对能力没有下降。
- `.github/workflows/ci.yml` 的 artifact 名 `suzhi-evidence-os-v5.2` 改为 `suzhi-evidence-os-v5.8`。
- `eslint-config-next` 从 15.5.27 对齐到 15.5.29。
- 把 `evaluate_rag.py --demo --fresh` 加入 CI backend job。

### 2.3 错误边界与静默异常（P2）

- 增加 `frontend/app/error.tsx`、`global-error.tsx`、`not-found.tsx`；关键路由 `loading.tsx`。
- `routes_ingestion_jobs.py:55` 与 `ingestion_service.py:622` 的 `except Exception: pass` 至少记录 `warning`，带 job_id、exception 类型；队列不可用应让前端看到“已入队但未启动”的真实状态。

## 3. 第二阶段：决定“只本机”还是“可联网”（两周）

### 3.1 本机边界（最低成本）

如果产品定位就是个人本机：

- 默认 `uvicorn --host 127.0.0.1`，README 明确“不要绑定 0.0.0.0”；
- CORS 默认只留 localhost；
- 加 `TrustedHostMiddleware` 允许 `localhost/127.0.0.1`；
- 在系统页显示“本机模式，无认证”；
- 这仍然不是“安全认证”，只是缩小暴露面。

### 3.2 联网认证（若需要）

- 反向代理层 OIDC/Basic 是最低工作量；应用内会话则需用户表、密码/SSO、CSRF、cookie SameSite。
- 所有资源查询加 `workspace_id` 过滤；不能只靠前端隐藏。
- 分享链接保持随机 token + 过期 + 撤销；创建/撤销需要登录。
- 审计：登录、上传、删除、分享、恢复、策略启用。
- 验收：未登录 401；跨 workspace 403；分享 token 过期/撤销 404；CSRF 测试。

### 3.3 安全头与限流

- Next `headers()`：CSP（先允许 Next 所需 inline/eval 的最小集，再逐步收紧）、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`、`Permissions-Policy`。
- 后端：请求体上限、按 IP/会话限流、上传并发限制；生产关闭 `/docs`。
- 反向代理：TLS、HSTS、超时、最大 body。
- 验收：响应头快照测试；超限 413/429；CSP 下页面与分享页无控制台错误。

## 4. 第三阶段：可靠性与规模（一个月）

### 4.1 实时链路 CI

在 GitHub Actions 用 service containers：

```yaml
services:
  redis: { image: redis:7.4-alpine, ports: ["6379:6379"] }
  qdrant: { image: qdrant/qdrant:v1.12.5, ports: ["6333:6333"] }
```

启动 backend + 一个 RQ worker，跑一条真实 smoke：上传小 md → 任务 completed → `/api/chat` 或 Agent run 返回引用 → locator 可打开。再把 Qdrant snapshot 加到恢复测试。

### 4.2 Qdrant 备份/恢复

- 备份 manifest 记录 collection、alias、point 数、向量维度、模型 fingerprint。
- 恢复流程：SQLite+uploads 恢复 → Qdrant snapshot 恢复；若没有 snapshot，明确“重建向量”命令与预计耗时。
- 验收：空 Qdrant + 恢复后的库，dense 检索返回正确 revision/chunk；不匹配时 fail closed。

### 4.3 依赖与供应链

- 后端 `uv.lock` 或 `pip-compile --generate-hashes`；CI 用锁定安装。
- Dependabot/Renovate 每周更新；生产依赖 high/critical 阻断合并。
- 补 `.python-version`、`.nvmrc`；CI Node 20 与本地 Node 24 的差异写进文档。
- 验收：干净环境 `uv sync --locked` / `npm ci` 后测试通过。

### 4.4 可观测性

- `/metrics`：请求量/延迟/错误率、队列深度、任务成功/失败、检索 p50/p95、存储自检状态。
- OpenTelemetry：HTTP → service → DB/Qdrant/Redis span；请求 ID 已存在，接上 trace ID。
- 审计事件表或日志：恢复、删除、分享、策略激活、Provider 配置变更。
- 告警：任务 queued 超过阈值、存储 error、Qdrant 不可用、备份失败。

## 5. 第四阶段：可维护性与产品体验（1–2 个月）

### 5.1 拆文件

| 目标 | 拆法 | 验收 |
| --- | --- | --- |
| `evidence_agent/controller.py` | 提交/推进/检索/评估/综合/查询六个模块 | 文件 < 50 KB；现有 60 案例与 1014 测试不变 |
| `media_service.py` | image/audio/video/ocr/keyframe 子服务 | 每类独立测试；共享上传/事务工具 |
| `Workbench.tsx` | 表单、来源选择、恢复状态、提交、结果五个组件 | 单组件 < 15 KB；E2E 59 项不变 |
| `agent_policy_optimizer/service.py` | 搜索循环/评分/报告导出 | 优化评测结果不变 |

### 5.2 列表分页与检索

- 文档/来源/Run/Artifact 列表加游标分页；默认 50，最大 200。
- 词法检索从 SQL 候选遍历升级到 SQLite FTS5（unicode61/trigram）或独立索引；保留 scope/revision 过滤。
- 中文评测从 24 题扩到 200+，加入长问题、同义改写、否定、跨文档、表格/代码混合。
- 验收：1 万文档合成库的 p95 检索延迟、Recall@10 不降；分页接口不再 `.all()`。

### 5.3 覆盖率与隐藏集

- 后端 `pytest-cov` 先测量，不急着定 80%；按模块设基线（storage/retrieval/agent 优先）。
- 固定 60 案例用于回归，另建 60+ 隐藏案例用于发布前验收，避免对公开集过拟合。
- 前端对关键 reducer/恢复状态加属性测试；E2E 保持 59 项并加真实服务 smoke。

### 5.4 真实模型评测

- 可选 `--provider` 评测，记录模型、温度、token、成本、延迟、引用完整性。
- 与 deterministic recording 分开报告，不混在一个“通过率”里。
- 验收：同一数据集上真实模型报告可复现；失败案例可定位到检索/生成/引用哪一层。

## 6. 不建议现在做

- 不要在认证和评测隔离之前继续加页面/功能；会放大维护面。
- 不要用公开 60 案例调 prompt 到 100% 后宣称真实质量；需要隐藏集和真实 provider。
- 不要直接 `npm audit fix --force`；本轮已验证 Next 15.5.29 可用，强制升级可能破坏兼容。
- 不要把工作库当评测库；演示数据、验收数据、运行数据应分开。
- 不要为了“看起来智能”在真实模式静默降级检索；当前 fail-closed 是优点，应保留。

## 7. 建议的验收节奏

| 时间 | 目标 | 必须产出 |
| --- | --- | --- |
| 本周 | 评测隔离 + 文档/CI 卫生 | 污染库通过、破坏种子失败；CI artifact 正名 |
| 第 2 周 | 本机边界 + 安全头 + 依赖锁定 | 401/403 测试、响应头快照、锁文件 |
| 第 3–4 周 | 实时链路 CI + Qdrant 恢复 | 真实上传→检索 smoke；空 Qdrant 恢复 |
| 第 5–8 周 | 拆文件 + 分页/FTS5 + 指标 | 文件尺寸/复杂度门、1 万文档基准、`/metrics` |
| 第 9–12 周 | 真实模型评测 + 多用户/部署 | provider 报告、Dockerfile/compose、租户隔离测试 |

每个阶段结束时更新一份 `acceptance_report.md`，记录实际跑过的命令与数字；未执行的项明确写“未验证”，不要用“应该可以”代替证据。
