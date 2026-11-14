# 校招项目竞争力审查：溯知 Evidence OS

> **2026-11-15 状态更新**：仓库已脱敏并设为 public，`main` CI 已通过；本轮已提交/合并 6 个 PR（评测隔离、错误边界、ADR/Provider 文档、README 30 秒、CI 修复、证据日志清理），另有 1 个一键 Docker PR 和 1 个 chunking benchmark PR 待合并。下面保留审查时的原始判断，并在“已补”处标注。
>
> 已补：公开可见、脱敏、commit/PR 历史、CI 绿、评测隔离、错误边界、ADR、Provider 模板、3 分钟 demo 脚本、1k/10k chunking 基准。
> 仍缺：真实 provider 20 题结果、3 分钟视频、端到端 1k/10k benchmark、Docker 构建验证。

审查日期：2026-11-15
审查对象：`<PROJECT_ROOT>`（HEAD `eac2253`，工作区 79 个未提交变更）
用途：校招简历项目 / 面试深挖材料，不是生产上线评审。

## 1. 一句话判断

**这是一个明显高于普通课程项目的全栈 AI 工程作品，但目前“招聘方看不见、摸不到、验证不了”的部分，抵消了它很大一部分技术含量。**

技术底子足够支撑 AI 应用 / Agent 后端 / 全栈岗位的面试；真正缺的不是再加功能，而是：

1. 一个招聘方能点开的入口；
2. 一组真实模型/真实规模的结果；
3. 一个能在 3 分钟内讲清楚的叙事；
4. 一份能证明“这是你做的、你讲得清”的工程痕迹。

## 2. 招聘方实际会看到什么

### 30 秒：简历筛选

当前最大问题不是代码，而是**可见性**：

- ~~GitHub 仓库对未登录访问返回 404~~ → **已设为 public，未登录可访问**。
- ~~远端 main 只有 1 个 commit~~ → **已基于脱敏基线追加 8 个 commit，并有合并 PR 记录**。
- ~~本地 155 commit / 79 未提交~~ → **工作区已提交并推送；公开历史为清洗后的 8 个 commit**。
- 仍没有公开 demo URL；一键 Docker PR 已提交（待 Docker 构建验证），`docker-compose.yml` 已扩展 app/worker/frontend。
- 没有 3 分钟演示视频/GIF；只有 12 张静态截图。

也就是说：**面试官在简历上看到一个 GitHub 链接，点开是 404；即使拿到访问权，也只看到一条“重写历史”的提交。** 这会让项目在筛选阶段直接失去被深挖的机会。

### 5 分钟：README / 作品页

优点：

- README 有截图、问题定义、对比表、架构图、快速启动、边界说明。
- 技术关键词密度高：evidence-native、immutable revision、outbox、checkpoint、RRF、AgentPolicy、Qdrant、RQ。
- 有“当前边界”和“简历表达”段落，诚实度是加分项。

问题：

- 286 行 README 对校招面试官偏长；前 2 屏没有“3 分钟视频 / 在线 demo / 真实模型结果”。
- 指标是测试与合成评测，不是产品效果；没有真实用户、真实资料、真实模型延迟/成本。
- “真实 Redis/Qdrant/RQ/Chromium 流程”在简历段落里是强主张，但本机当前无法复现真实服务链路；面试官追问时会危险。
- 版本叙事（V5.8 / V5.12 / V5.13）对内部是资产，对招聘方是噪音；需要一页“当前状态”而不是版本史。

### 30 分钟：代码与面试

优点：

- 1014 个后端测试、206 个前端单测、59 项生产构建浏览器回归，测试纪律在校招项目里非常突出。
- 证据身份、durable execution、取消 fence、恢复、存储自检/备份/恢复，这些是有深度的工程问题。
- 代码分层清楚，类型严格，无 TODO/FIXME，无 `as any`/`ts-ignore`。
- CI、迁移、评测、发布脚本齐全，说明有工程闭环意识。

风险：

- `evidence_agent/controller.py` 131.8 KB、`media_service.py` 76.3 KB、`Workbench.tsx` 41.7 KB；面试官会问“为什么这么大”，需要有意识地说“这是下一轮要拆的”。
- 150 个 API、44 个页面，功能面过宽；校招面试更看重“你砍掉了什么、为什么”。
- 合成评测 60/60 很容易被追问“真实模型呢？”；必须有诚实且具体的回答。

## 3. 岗位适配

| 方向 | 适配度 | 判断 |
| --- | --- | --- |
| AI 应用 / LLM 应用工程 | ★★★★★ | 最匹配：RAG、Agent、引用、评测、Provider 抽象都有 |
| Agent 后端 / 平台工程 | ★★★★☆ | 状态机、outbox、幂等、恢复很强；缺真实队列/部署规模 |
| 全栈开发 | ★★★★☆ | Next.js + FastAPI + 测试 + UI 完整；缺线上部署 |
| 后端开发（Python） | ★★★★☆ | 工程规范强；SQLite/单机架构会被问扩展性 |
| 测试开发 | ★★★★☆ | 测试层次丰富；缺性能/安全/混沌测试 |
| 算法 / ML | ★★☆☆☆ | 没有训练/微调/真实模型评测；是应用工程，不是算法研究 |
| 数据工程 | ★★★☆☆ | 有摄取/索引/评测；缺大规模数据管道与仓库 |

**建议定位**：AI 应用工程 / Agent 后端 / 全栈，不要把自己包装成“算法工程师”。

## 4. 当前最强卖点

按面试价值排序：

1. **Evidence identity**：revision/index/chunk/hash/locator 全链路，引用可回放。普通 RAG 项目通常只有 `source + page`，这里有“哪一版、哪个片段、为什么是它”。
2. **Durable Agent execution**：outbox、checkpoint、idempotent command、execution fence、取消后迟到结果不写回。这是很多校招项目没有的并发/恢复深度。
3. **失败关闭与诚实降级**：真实模式 Qdrant 不可用会报错，demo 才允许稀疏降级；比“静默兜底”更工程化。
4. **测试与评测纪律**：1014 后端测试、59 浏览器回归、60 固定场景、24 题中文检索；能证明不是“跑通一次”。
5. **存储保证**：fsync、SQLite FULL、哈希 manifest、备份后复核、异目录恢复路径重写；很少见。
6. **UI/UX**：四个一级入口、中文一致、响应式、无障碍巡检；能直接截图书面作品。
7. **中文检索的测量闭环**：V5.12 把单次检索代理多跳成功率从 41.67% 提到 66.67%，Agent 仍 100%，相对提升从 58.33 收窄到 33.33——这是一个很好的“基线变强导致相对指标下降”的面试故事。

## 5. 差什么：按优先级

### Gap 1：招聘方看不见（最高优先级）

- 仓库私有，README 里的 CI 徽章也不会对未登录用户显示。
- 远端只有 1 个“重写历史”的 commit；本地 155 个 commit 和 79 个未提交变更没有形成公开工程痕迹。
- 没有公开 demo / 视频 / GIF。

**要补**：

- 做一个**公开的 portfolio 镜像仓库**，只保留可公开的代码、截图、sanitized 数据；或者把当前仓库设为 public（确认无个人信息/密钥后）。
- 公开历史不要直接推 155 个 WIP commit，也不要只有 1 个 squash；用 10–20 个有意义的 commit 重建叙事：
  1. `feat: evidence index with immutable revisions`
  2. `feat: durable agent runtime with outbox and checkpoints`
  3. `feat: hybrid retrieval and Chinese lexical search`
  4. `feat: storage integrity, backup and restore`
  5. `test: fixed 60-case agent evaluation`
  6. `feat: workbench recovery and citation UI`
  7. `chore: CI, quality gates and release checks`
- 先提交当前 79 个变更，再决定公开哪些；不要把“未提交”当成“已完成”。

### Gap 2：没有真实模型/真实资料证据

- 固定评测是 synthetic corpus + deterministic recording model；README 也承认“不代表真实大模型质量”。
- 没有 `.env` / provider key 配置，没有真实 Q&A 记录、延迟、成本、失败案例。
- 面试官一定会问：“接真实模型效果怎么样？”

**要补**：

- 配置一个 OpenAI-compatible provider（DeepSeek/Qwen/OpenAI 任一），跑 20–30 个真实问题。
- 记录：模型名、温度、输入/输出 token、单次成本、p50/p95 延迟、引用是否有效、拒答是否合理。
- 保留 3 个真实失败案例（检索没命中、引用错、模型胡编），说明你如何定位。
- 在 README 用一张小表分开写：
  - Deterministic CI：60/60，citation 1.0；
  - Real provider（20 题）：通过 X/20，平均延迟 Y ms，平均成本 Z；
  - 不把两者混成一个“通过率”。

### Gap 3：没有规模/性能证据

- 当前 demo 只有 4 个来源、9 个多模态 chunk；SQLite 单机。
- 没有 1k/10k 文档的摄取吞吐、检索 p95、内存、DB 大小。
- 面试官会问：“资料多了怎么办？”

**要补**：

- 生成 1,000 / 10,000 个合成文档，测：
  - 摄取吞吐（docs/min）；
  - 检索 p50/p95；
  - SQLite 文件大小、WAL 大小；
  - 内存峰值；
  - 与 FTS5/Qdrant 的对比（至少说明瓶颈）。
- 写一页 `docs/benchmarks.md`，明确“SQLite 适合单用户，10 万文档需要 Postgres/FTS5/分片”。
- 不需要真的做分布式，但要能说出迁移路径。

### Gap 4：没有线上闭环

- 没有后端/前端 Dockerfile，没有 app+worker 的 compose，没有公开 URL。
- 没有认证/授权、CSP、限流；直接公网部署有风险。
- 没有指标/追踪/审计。

**要补（二选一）**：

A. **本机一键 demo**（更诚实、成本低）：
- `docker compose --profile demo up` 启动 backend + worker + frontend + Redis + Qdrant；
- 自动 seed showcase；
- README 第一屏放“一键启动 + 3 分钟视频”。
- 明确写“本机单用户，不暴露公网”。

B. **公开 demo**（加分但工作量大）：
- 先加认证/限流/安全头，再部署到 Fly/Render/Railway + Qdrant Cloud/Upstash；
- 限制模型预算，防滥用；
- 公开 URL + 只读 demo 账号。

对校招，A 已经足够；B 是差异化加分，不要为了 B 牺牲稳定性。

### Gap 5：项目叙事太宽，岗位焦点不够

- 150 路由、44 页面、V5.1–V5.13 文档，容易让面试官觉得“什么都有，但不知道你最擅长什么”。
- README 的简历段落是一整句长句，信息密度过高，缺少“问题 → 方案 → 结果”的节奏。

**要补**：

- 一句话定位：**“把 RAG 从答案生成做成可审计的证据流水线。”**
- 三个深挖故事（只讲三个）：
  1. **证据身份**：为什么普通 RAG 的 citation 不够？revision/index/chunk/hash 怎么保证回放？
  2. **可恢复执行**：取消后迟到结果为什么会污染状态？outbox/checkpoint/fence 怎么解决？
  3. **检索质量**：中文 lexical 的失败案例是什么？怎么测？为什么相对提升从 58.33 降到 33.33 不是退步？
- 一个取舍故事：为什么 SQLite？为什么不用 LangChain？为什么真实模式 fail-closed？
- 一个“我砍掉了什么”：V4.x Developer Mode 收敛到四个主入口；150 路由里哪些是诊断、哪些是产品。

### Gap 6：工程过程不可见

- 远端 1 个 commit；本地 155 个 commit、5 个 merge，但未公开。
- 没有公开 issue/PR 讨论；虽然模板齐全。
- 面试官无法判断“哪些是你设计的、哪些是 AI 生成的”。

**要补**：

- 公开仓库保留有意义的 commit + 2–3 个 PR（可以是自己开分支、自己 review 的 PR），展示设计讨论。
- 每个核心模块写 1 页 ADR：为什么 immutable revision、为什么 outbox、为什么 SQLite、为什么 fail-closed、为什么 RRF。
- 准备“我遇到的最难 bug”故事：CORS 配置启动崩溃、Windows ffmpeg 编码导致 89 个测试错误、Next 生产构建只输出 Suspense 占位、恢复后路径全变孤儿。这些是真实的、能讲出诊断过程的。

### Gap 7：量化指标是“测试指标”，不是“产品指标”

- 1014 测试、59 E2E、60/60 评测很亮眼，但招聘方更想知道：
  - 用户省了多少时间？
  - 引用错误率降低多少？
  - 单次查询成本/延迟多少？
  - 资料更新后旧引用是否还能回放？
- 没有真实用户，至少要有“任务完成时间/引用核验时间”的小实验：
  - 5 个真实资料、10 个问题，人工核验引用需要多久；有系统 vs 手工。
  - 这是产品指标，不是编造用户量。

### Gap 8：面试深度需要主动证明

- 文件太大、功能太多，面试官可能怀疑“是不是 AI 堆出来的”。
- 合成评测 60/60 太完美，反而容易被追问。

**要补**：

- 能打开 3 个核心文件讲 10 分钟：`evidence_index/sql.py`、`evidence_agent/controller.py`、`storage_backup.py`。
- 能解释 5 个失败案例和 3 个取舍。
- 能现场改一个小需求（例如新增一个 locator 类型/一个状态），证明不是只会跑现成代码。
- 主动说边界：真实模型未评估、单机 SQLite、无多租户；这比被问出来好。

## 6. 面试官最可能追问的 12 个问题

1. 为什么叫 Evidence OS？和普通 RAG 的区别是什么？
2. citation 里为什么要 revision/index/chunk/hash 四层？只存 source_id 不行吗？
3. 资料更新后，旧 Artifact 的引用怎么还能回放？
4. 取消 Run 后，迟到的模型结果为什么不能写回？execution fence 怎么实现？
5. outbox 解决了什么问题？和直接 `db.commit()` 后发消息有什么区别？
6. 为什么用 SQLite？并发写怎么办？什么时候换 Postgres？
7. RRF 为什么有效？k 值怎么选？dense/sparse 权重怎么定？
8. 中文检索做了什么？为什么分词/词法在中文里容易失败？
9. 60/60 是怎么测的？合成数据和真实模型差在哪？有没有真实 provider 结果？
10. 如果资料量到 100 万 chunk，检索/索引/存储怎么扩展？
11. 你为什么不用 LangChain/LlamaIndex？自己写 Agent runtime 的代价是什么？
12. 这个项目最大的技术债是什么？如果重做，你会先改哪三件事？

**回答原则**：先给结论，再给取舍，最后给证据；不要背术语。不会的就说不确定，并给出验证方法。

## 7. 两周行动清单（按投入产出排序）

### 第 1 周：让招聘方看见并相信

- [ ] 处理 79 个未提交变更：分组 commit，确保测试通过。
- [ ] 建公开 portfolio 镜像 / 或把仓库设为 public（脱敏后）。
- [ ] 远端历史整理成 10–20 个有意义 commit；至少 2 个 PR。
- [ ] 写 1 页 `docs/portfolio/README.md`：问题、3 张图、3 个指标、1 条启动命令、边界。
- [ ] 录 3 分钟 demo：Agent run → evidence ledger → citation jump → cancel/recover → storage check。
- [ ] 配置真实 provider，跑 20 题，记录延迟/成本/引用；保留 3 个失败案例。
- [ ] README 第一屏放：Demo 视频 / 一键启动 / 真实模型结果 / 合成评测分开。

### 第 2 周：让技术深度可验证

- [ ] 一键 `docker compose --profile demo up`（backend + worker + frontend + Redis + Qdrant）。
- [ ] 1k/10k 文档 benchmark：摄取吞吐、检索 p95、内存、DB 大小。
- [ ] 修评测隔离（工作库污染问题），补测试。
- [ ] 加 `docs/benchmarks.md`、`docs/adr/` 5 篇。
- [ ] 准备 3 个深挖故事 + 5 个失败案例 + 3 个取舍。
- [ ] 简历改成 3 条 bullet，每条“动作 + 技术 + 数字 + 边界”。
- [ ] 模拟面试：让同学/朋友按第 6 节问题追问 30 分钟。

### 第 3–4 周（可选加分）

- [ ] 加认证/限流/安全头，部署一个只读 demo。
- [ ] Qdrant snapshot + 恢复演练。
- [ ] 拆 controller/media/Workbench。
- [ ] 加覆盖率与隐藏评测集。
- [ ] 公开 benchmark/真实模型报告。

## 8. 简历 bullet 建议

不要写“做了 150 个接口、44 个页面”；写“解决了什么问题、怎么验证”。

**版本 A（AI 应用/Agent 后端）**

> 独立设计 evidence-native RAG/Agent 系统（FastAPI / Next.js / SQLite / Qdrant / Redis），以 immutable revision/index/chunk + locator 实现引用可回放；用 outbox、checkpoint、幂等命令与 execution fence 解决取消/断线后的状态污染。固定 60 场景 Agent 评测 60/60、citation completeness 1.0；1014 后端测试 + 59 项 Chromium 回归。

**版本 B（后端/平台）**

> 为多模态研究 Agent 设计持久化执行层：SQLite WAL + transactional outbox + lease/CAS + checkpoint + execution fence，覆盖取消、重试、崩溃恢复与迟到结果丢弃；恢复场景 6/6 通过。实现存储自检/在线备份/校验恢复（SHA-256 manifest、异目录路径重写），8 个引用文件 0 缺失/0 孤儿。

**版本 C（全栈）**

> 独立实现从资料摄取、混合检索、引用回放到研究产物的全栈工作台（Next.js 15 / React 19 / FastAPI），支持 PDF 页码、媒体时间戳、OCR 区域、代码行四类 locator 深链；59 项生产构建浏览器回归、12 路由无障碍巡检通过。

**注意**：

- “60/60”必须加“固定合成评测”，不要暗示真实模型。
- “1014 测试”是工程指标，不要当产品指标；可以和“citation completeness 1.0”一起用。
- 如果没做真实 provider，不要写“真实模型效果提升”。

## 9. 三分钟 demo 脚本

**0:00–0:20 问题**

“普通 RAG 能回答，但很难证明这句话来自哪一版资料的哪个片段。我做的系统把引用变成可回放的证据链。”

**0:20–1:10 主流程**

- 选择知识空间，提交一个跨文档问题；
- 展示计划/检索/评估步骤；
- 打开 Artifact，点引用，跳到 PDF 页码 / 视频时间戳 / 代码行；
- 指出 revision/hash/locator。

**1:10–1:50 可靠性**

- 取消一个运行中的任务；
- 刷新页面，展示恢复，不重复执行；
- 说明迟到结果被 fence 丢弃。

**1:50–2:20 质量**

- 打开评测页：60/60、citation 1.0；
- 说明这是合成固定集，真实 provider 另有一张表；
- 展示中文检索 24 题结果。

**2:20–2:50 存储**

- 打开存储完整性面板：8 文件、0 缺失、0 孤儿；
- 说一句“备份带 SHA-256 manifest，恢复会保留旧副本”。

**2:50–3:00 边界**

“当前是单用户本地工作台，SQLite；多租户/公网部署是下一步，不是现在假装有。”

## 10. 不建议现在做

- 不要继续加页面/路由；先让现有能力可见。
- 不要把 276 篇文档都摆在招聘方前面；做 5 篇入口文档即可。
- 不要用公开 60 案例调 prompt 到 100% 后宣称真实质量。
- 不要为了“看起来生产级”直接公网部署无认证的模型接口。
- 不要把 155 个 WIP commit 原样推公开；整理叙事。
- 不要背“transactional outbox”等术语却讲不清失败场景；面试官会追问。
- 不要只准备项目，算法题/八股要单独练；项目不能替代笔试。

## 11. 结论

**项目本身：校招中上水平，AI 应用/Agent 后端方向有竞争力。**
**当前状态：作为“可投递作品”还不合格，主要卡在可见性、真实性和叙事，而不是代码能力。**

如果明天要投，先做三件事：

1. **让仓库可见**（公开镜像或 public + 脱敏 + 提交当前变更）；
2. **录 3 分钟 demo + 配真实 provider 跑 20 题**；
3. **把 README 第一屏改成“问题 + demo + 3 个真实数字 + 边界”**。

做完这三件，项目从“代码很多”变成“能被面试官记住的证据链作品”。
