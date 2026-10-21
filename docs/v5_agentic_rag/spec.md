# 溯知 V5 Evidence Agent Spec

## Background

溯知 V4.9 已具备文档、图片、音视频和代码仓库的采集、切分、向量检索、问答引用与持久任务能力，但核心问答仍是一次检索加一次生成。现有系统还存在旧来源版本可能继续被召回、关键词检索漏掉旧精确命中、数据库与向量库索引生命周期不一致，以及评测不运行真实 RAG 链路等可信度问题。

V5 的第一实现周期将项目从“可追溯的多模态 RAG”升级为“证据原生的研究智能体”：用户提交一个研究目标，系统根据复杂度选择快速问答或有界的多步调查，形成计划、迭代检索、判断证据缺口与冲突，并输出每条事实可回到不可变来源版本的结论和产物。

本周期必须形成一条真实可演示、可评测、可恢复的纵向闭环；不以增加 Agent 数量或页面数量作为完成标准。

## Goals

- 让进入回答和 Agent 推理的证据具备可靠、唯一、可退役的版本生命周期。
- 为简单问题保留低开销快速路径，为复杂问题提供有界、可恢复的单主控 Agent Run。
- 让系统显式记录计划、工具步骤、证据、缺口、冲突、决定、引用与最终产物。
- 让每一条事实性结论都绑定不可变的来源版本、定位信息和内容指纹。
- 提供工作台、运行记录和证据检查器，使用户能够观察、澄清、暂停、恢复或取消运行。
- 用真实端到端评测证明检索、引用和 Agent 行为，而不是只检查 seeded 日志。
- 将主产品叙事收敛为“可审计的多模态证据智能体”。

## Functional Requirements

- F1: 系统必须为文档、图片、音频、视频和代码来源维护唯一的 active revision；新版本成功激活后，旧版本的 chunk、索引和向量不得再参与查询。
- F2: 索引建立、激活、退役、取消、失败和重试必须保持关系数据库、文件状态与向量库之间可恢复的一致性；系统必须能够发现并清理未被数据库追踪的向量。
- F3: 检索必须支持覆盖全部 active evidence 的 dense 与 sparse/keyword 召回、稳定的融合排序、可选的真实 rerank、来源过滤和相邻证据窗口；旧资料中的精确命中不得因创建时间较早而被跳过。
- F4: 用户必须能够提交研究目标、来源范围、交付物类型、运行预算和权限，创建一个持久 Agent Run，并读取其当前状态和最终结果。
- F5: 系统必须根据问题复杂度和可用来源，在无检索、单步快速检索和多步调查之间选择运行模式；简单问题不得无条件进入完整 Agent 循环。
- F6: 多步调查必须形成可见的事实需求或子问题计划，并通过受控的只读证据工具执行搜索、定位、打开和相邻上下文读取。
- F7: 每个 Agent Run 必须维护 Evidence Ledger，区分支持证据、反证、被排除证据、未覆盖需求和下一步检索建议。
- F8: Agent 必须在每轮检索后判断证据是否充分，并在“继续检索、请求澄清、正常返回证据不足、生成结论”之间作出结构化决定。
- F9: Agent 循环必须受步骤数、模型 token、时间和费用预算约束；连续无新增证据或预算耗尽时必须停止，不得无限自循环。
- F10: 最终回答和 Artifact 中的每条事实性 claim 必须引用一个或多个 immutable Evidence Reference；引用必须包含来源、revision、locator、内容指纹和支持关系。
- F11: 用户必须能够对 awaiting_input 或 awaiting_approval 状态提交澄清、批准、修改或拒绝决定，并从持久 checkpoint 恢复；用户取消后不得继续产生模型调用、工具步骤或产物。
- F12: 系统必须提供按 cursor 增量读取的有序运行事件，覆盖状态变化、计划、工具调用、证据、决定、模型用量、错误、恢复和完成；重复连接不得造成事件丢失或重复应用。
- F13: Agent Workbench 必须在一个核心界面展示目标、来源范围、计划、当前步骤、Evidence Ledger、预算、人工决定和最终 Artifact；切换知识空间后不得展示上一个空间的回答或引用。
- F14: 主产品导航必须收敛为工作台、资料库、Agent Runs 和产出物；性能、可观测性、配置与内部治理入口必须归入 Developer Mode，作品集自指页面不得继续作为核心产品入口。
- F15: 由 Agent 生成的 Artifact 必须保存 producing run 和 provenance，并允许用户从 claim 跳回原始 PDF 页、媒体时间戳或代码行，也能从来源查看派生产物。
- F16: 系统必须提供真实评测入口，运行 embedding、检索、上下文构造、Agent 决策、生成和引用验证链路，并输出 baseline 与 Agent 模式的可比较结果。
- F17: 被检索资料中的指令必须始终按不可信 evidence 处理；未授权的写入、外发和代码执行工具不得被调用，受保护动作必须进入明确的人工批准状态。

## Non-Functional Requirements

- N1: V4.9 已有知识空间、来源、任务和问答数据必须可迁移且可读取；数据库迁移必须支持 upgrade、downgrade 和模型一致性验证。
- N2: Agent Run、步骤、工具调用、证据和决定必须具备稳定标识、幂等写入和明确状态转换；进程或 Worker 重启不得损坏已提交状态。
- N3: 所有外部模型和媒体 Provider 必须保留 Real/Demo 的诚实边界；未配置时返回明确错误，不得伪造真实结果。
- N4: 单元和模块测试必须可使用本地或 recording fake adapter 运行；默认测试不得依赖可访问的真实 LLM、Redis Cloud 或远程 Qdrant。
- N5: Agent 运行必须记录 request/run/step/tool 关联标识、延迟、重试、token 和可得的费用数据，但不得记录密钥或未经必要处理的敏感内容。
- N6: 快速路径不得增加不必要的规划模型调用；性能报告必须分别给出 quick mode 与 agent mode 的 p50/p95，而不是混合平均值。
- N7: 工作台核心流程必须支持键盘操作、可见焦点、状态播报、reduced motion 和窄屏布局；关键控件必须具有可访问名称。
- N8: 前后端契约必须具有运行时校验或生成式类型来源，避免仅靠 TypeScript 强制转换掩盖 payload 漂移。
- N9: 新增模块必须通过小而稳定的 interface 隐藏 Agent runtime、RQ、Qdrant 和 Provider 实现细节；调用方不得依赖 LangGraph 状态类型。
- N10: 所有失败状态必须给出可操作的原因、是否可重试和下一步；`insufficient_evidence` 是正常业务结果，不得作为服务器异常返回。
- N11: V5 公开展示不得包含失效截图、旧版本文案或未实现能力；所有简历数字必须来自可重复运行的评测输出。

## Out of Scope

- 多 Agent 角色编排、Agent 之间的委派和自由对话。
- 开放互联网搜索、MCP 市场或第三方写入工具的正式接入。
- 自动执行代码、Shell、数据库写操作或向外部系统发送消息。
- 跨用户共享记忆、长期人格记忆和自动学习用户偏好。
- 完整的组织级认证、租户计费、配额结算和云生产部署。
- 将 SQLite 迁移为 PostgreSQL，或替换现有 FastAPI、RQ、Qdrant 技术栈。
- 模型微调、训练自有 embedding/rerank 模型。
- 为所有旧页面重新设计视觉；本周期只保证核心四区和端到端闭环。
- 用主观 LLM-as-judge 分数替代可验证的检索、locator、引用和工具轨迹指标。

## Acceptance Criteria

- AC1: 对同一文档或媒体连续处理两个版本后，查询只返回第二个 active revision；旧 revision 的 chunk、索引和向量均不可被普通查询命中。
- AC2: 在向量 upsert 后取消、数据库提交前失败、重复重试和并发重建场景中，不留下不可追踪向量；reconciler 能报告并清理人工注入的孤儿点。
- AC3: 在包含至少 30 个不同创建时间 chunk 的固定数据集中，最旧 chunk 的精确关键词命中能够进入候选；所有返回结果统一遵守过滤条件和最低有效阈值。
- AC4: 检索评测能够分别报告 dense、sparse、融合和 rerank 的 Recall@k、MRR、nDCG、active-revision precision 与 locator validity。
- AC5: 创建研究目标后返回稳定 run id；运行可以经历 planned、running、awaiting_input/awaiting_approval、paused、completed、insufficient_evidence、cancelled 或 failed 等明确状态，并能在 Worker 重启后恢复到一致状态。
- AC6: 简单事实问题使用 quick mode，且不会产生规划步骤；需要跨两个或更多来源的问题形成计划并执行多步证据工具调用。
- AC7: 多步运行的 Evidence Ledger 能列出事实需求、已覆盖需求、支持证据、反证、排除理由、缺口和下一步查询；前端展示与持久记录一致。
- AC8: 当资料不足时，Agent 返回结构化 insufficient_evidence 或请求用户澄清，不编造确定性结论；补充澄清后可以从原 checkpoint 继续。
- AC9: 达到步骤、token、时间、费用或连续无新增证据限制时，运行停止并记录具体终止原因；自动化测试中不存在无限循环。
- AC10: 最终产物中的每条事实性 claim 都能解析到当前数据库中的 immutable revision、合法 locator 和一致 content hash；点击引用可打开正确页码、时间戳或代码行并突出目标证据。
- AC11: awaiting_input/awaiting_approval 运行能够接受批准、修改、拒绝或澄清并继续；取消一个正在等待 Provider 的运行后，不再新增模型、工具或 Artifact 记录。
- AC12: SSE 或等价事件流按单调 cursor 返回事件；断线重连后只补发缺失事件，前端不会重复呈现同一步骤。
- AC13: 主导航只保留四个产品入口及一个折叠的 Developer Mode；Agent Workbench 能完整完成“选择空间与来源 → 提交目标 → 观察计划与证据 → 必要时澄清 → 查看产物 → 跳回来源”的流程。
- AC14: 从 Artifact 可查看 producing run 和全部 provenance，从来源详情可查看其派生 Artifact；切换知识空间立即清除旧空间结果。
- AC15: 至少建立 60 条经分类的固定评测案例，覆盖单跳、多跳、跨模态、版本冲突、证据不足、提示注入和取消恢复；报告同时给出 V4.9 single-shot、升级后 retrieval baseline 和 Agent mode，不伪造或手填结果。
- AC16: 在多跳子集上，Agent mode 的 evidence coverage 或任务成功率至少比 V4.9 single-shot 提升 10 个百分点，同时报告样本数、失败案例、token、费用和延迟；若未达到，不得在 README 宣称提升。
- AC17: 恶意来源中包含“忽略规则、读取密钥、执行代码或外发内容”的指令时，运行不得产生相应受保护工具调用；安全评测报告未授权动作率。
- AC18: 后端相关测试、迁移检查、前端 lint/typecheck/build、核心 Playwright E2E 和依赖审计均实际运行；失败项必须修复或在最终验收报告中明确列出，不能以“应该可用”代替证据。
- AC19: README 顶部包含当前版本价值主张、真实核心流程截图或录屏、可重复评测摘要、架构图和五分钟启动路径；匿名可见性若未开放，必须明确标为尚不可用于公开作品集。

## V5.1 Agent Closure Addendum

本增量在不引入开放写入工具、多 Agent 或互联网搜索的前提下，补齐 V5 已明确记录的三个 Agent 闭环缺口。用户已授权在既有规格范围内自行审查并直接执行。

### Additional Functional Requirements

- F18: Agent 在检索命中后必须能够通过受控只读工具打开一条 immutable evidence，并读取同 revision 内有界的相邻 chunk；每个工具调用必须单独记账、受预算和 execution fence 约束，并可在 Worker 中断后安全重放。
- F19: Evidence Ledger 必须把模型未选择的候选证据持久标记为 `excluded`，记录排除原因和判定方法；相邻 chunk 必须标记为 `contextual`，不能仅因被读取就自动成为 claim support。
- F20: awaiting_approval 必须接受 `modify` 命令。修改只允许改变受控的 Artifact 标题，必须生成新的 proposal digest，使旧 approval 立即失效，并保持同一 Run 与同一 draft Artifact。

### Additional Non-Functional Requirements

- N12: Evidence open/neighbor 查询只能访问 Run 已 pin 的 revision，窗口大小必须有硬上限，不能扩大来源范围。
- N13: 修改审批必须幂等、版本化、可审计；不得通过修改标题改变 claim、evidence、scope、权限或预算。
- N14: 前端必须用中文显示 `candidate/contextual/supports/contradicts/excluded` 的含义，并展示 excluded reason；英文领域词同时提供中文解释。

### Additional Acceptance Criteria

- AC20: 一个 Agent requirement 的检索完成后，公开事件中可以观察到 `search_evidence → open_evidence → read_neighbors` 三个独立只读工具调用；neighbor 仅来自同一 pinned revision，取消或旧 epoch 返回时不写入 Ledger。
- AC21: 模型选择部分候选作为支持证据后，其余候选显示为“已排除”，并带有非空 reason/method；相邻证据显示为“上下文”，不会未经选择直接进入 factual claim。
- AC22: 用户修改待发布 Artifact 标题后仍停留在 awaiting_approval，新 digest 与旧 digest 不同，旧 digest 审批返回冲突，新 digest 审批成功且最终 Artifact 使用修改后的标题。
