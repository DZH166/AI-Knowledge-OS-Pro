# AI Knowledge OS Pro 学习档案

<!-- slug:v1-foundation-rag -->
## V1：基础文档 RAG 知识库闭环

### 版本总结
从零搭建 AI Knowledge OS Pro 的基础闭环，让用户可以创建知识库、上传文档、完成向量入库、基于知识库提问，并沉淀本版本学习档案。

### 本版本实现了什么
- 创建和查看知识库空间。
- 上传 txt、md、pdf 文档并解析文本。
- 将文档内容清洗、切分为 chunks，并保存到 SQLite。
- 调用 embedding 服务生成向量，写入 Qdrant Server。
- 用户基于知识库提问，系统检索相关 chunks 并构建 Prompt。
- 调用 OpenAI-compatible 大模型生成回答，支持普通、小白、项目、面试四种回答模式。
- 展示引用来源和相关知识片段，并保存问答历史。
- 生成学习档案页面和 docs/learning_log.md，用于后续复盘和面试表达沉淀。

### 本版本新增或修改的主要文件
- `backend/app/main.py`：FastAPI 应用入口，注册路由、初始化数据库和学习档案。
- `backend/app/api/`：知识库、文档、问答、Dashboard、学习档案接口。
- `backend/app/models/`：SQLite 数据模型，包括知识库、文档、chunk、问答历史、学习档案。
- `backend/app/services/rag_service.py`：串联文档解析、chunk、embedding、Qdrant 检索、Prompt 和回答生成。
- `backend/app/services/vector_store.py`：封装 Qdrant collection 创建、point 写入、payload filter 和 `query_points` 检索。
- `backend/app/services/learning_log_service.py`：维护版本学习档案的结构化记录与 Markdown 追加写入。
- `frontend/app/`：Next.js 页面，包括 Dashboard、知识库、上传、问答、文档、学习档案。
- `frontend/app/documents/[id]/page.tsx`：文档详情页，展示文档摘要、chunks、上传时间和所属知识库名称。
- `frontend/components/`：上传器、问答组件、引用面板、学习档案面板等复用组件。
- `docs/learning_log.md`：长期追加保存每个版本对应的学习沉淀。
- `README.md`：项目介绍、启动方式、配置说明和学习路线。

### 本版本涉及的 AI 应用开发知识点

#### FastAPI 路由
- 小白解释：路由就是后端给前端开的功能入口，比如创建知识库、上传文档、提问都对应一个 URL。
- 项目用法：V1 用 routers 拆分知识库、文档、问答、学习档案接口，让每类能力都有清晰入口。
- 后续补课：先补 FastAPI 的 APIRouter、依赖注入和 HTTP 状态码，再看文件上传。
- 面试表达：我用 FastAPI 按业务模块拆分 API 路由，使知识库、文档、问答和学习档案接口保持清晰边界。

#### Pydantic 数据校验
- 小白解释：Pydantic 像接口门口的检查员，确保前端传来的字段类型和格式是后端能处理的。
- 项目用法：V1 用 schema 定义创建知识库、提问、学习档案等请求和响应结构。
- 后续补课：重点看 BaseModel、Field、Literal 和 from_attributes。
- 面试表达：我用 Pydantic 固化接口契约，减少脏数据进入业务层，同时让前后端数据结构更稳定。

#### 文件上传
- 小白解释：文件上传就是前端把本地文档交给后端，后端保存文件并开始解析。
- 项目用法：V1 的上传接口接收 space_id 和文件，将原文件保存到 storage/uploads 后创建文档记录。
- 后续补课：补 multipart/form-data、UploadFile、文件类型校验和异常处理。
- 面试表达：我实现了基于 multipart 的文档上传，并在入库前完成类型校验、持久化和状态追踪。

#### 文档解析
- 小白解释：文档解析就是把 txt、md、pdf 里的文字读出来，变成系统可以处理的纯文本。
- 项目用法：V1 对 txt/md 直接读文本，对 pdf 使用 pypdf 提取页面文本，并生成基础摘要。
- 后续补课：先理解不同文件格式的文本提取差异，再了解 Docling 或 Unstructured 的扩展价值。
- 面试表达：我封装了文档解析服务，支持 txt、md、pdf，并为后续多格式解析预留扩展点。

#### chunk 切分
- 小白解释：chunk 是把长文档切成小片段，避免一次塞给模型太多内容。
- 项目用法：V1 按字符长度和重叠窗口切分文档，保存 chunk_index、内容和预览。
- 后续补课：理解 chunk_size、overlap、语义边界和检索效果之间的关系。
- 面试表达：我实现了带 overlap 的文档切片，让检索粒度更稳定，也减少跨段信息丢失。

#### Embedding
- 小白解释：Embedding 可以理解为把文字变成一串数字，意思相近的文字数字距离更近。
- 项目用法：V1 上传文档时把每个 chunk 转成 embedding；提问时把问题也转成 embedding。
- 后续补课：补向量相似度、embedding 模型选择和维度概念。
- 面试表达：我把文档片段和用户问题统一向量化，用语义相似度而不是关键词匹配来找资料。

#### Qdrant 向量数据库
- 小白解释：Qdrant 是专门存和查向量的数据库，适合做语义检索。
- 项目用法：V1 将 chunk embedding、文档名、chunk_id、预览内容等 payload 写入 Qdrant，并按知识库过滤检索；本地验证使用 `<QDRANT_HOME>\qdrant.exe` 启动真正的 Qdrant Server。
- 后续补课：重点学习 collection、point、payload、filter 和 cosine distance。
- 面试表达：我使用 Qdrant 存储向量和元数据，通过 payload filter 实现按知识库隔离检索。

#### RAG 检索增强生成
- 小白解释：RAG 就是先从资料库找相关内容，再把这些内容交给大模型回答，减少胡说。
- 项目用法：V1 的问答流程是问题向量化、Qdrant 检索、拼接上下文、构建 Prompt、调用模型回答。
- 后续补课：按解析、切片、向量化、检索、Prompt、生成、引用这个链路复习。
- 面试表达：我实现了完整 RAG 闭环，让模型基于用户上传资料回答，并返回引用来源提升可信度。

#### Prompt 构建
- 小白解释：Prompt 是给模型的任务说明，告诉它要按什么风格、基于哪些资料回答。
- 项目用法：V1 根据 normal、beginner、project、interview 四种模式构建不同指令。
- 后续补课：补 system prompt、上下文拼接、回答风格约束和无法回答时的处理。
- 面试表达：我通过 Prompt 模板区分普通解释、小白解释、项目解释和面试表达，提升回答可用性。

#### 引用来源展示
- 小白解释：引用来源让你知道答案参考了哪些文档片段，方便检查答案是不是靠谱。
- 项目用法：V1 返回 document_name、chunk_id、chunk 内容预览和相似度分数，并在前端展示。
- 后续补课：理解 citation 对 RAG 产品可信度和可追溯性的意义。
- 面试表达：我在 RAG 回答中返回引用来源和相关片段，增强答案可解释性和用户信任。

#### 问答历史保存
- 小白解释：问答历史就是把你问过什么、系统答过什么保存下来，方便复盘。
- 项目用法：V1 将问题、答案、回答模式、引用和相关片段保存到 SQLite。
- 后续补课：补数据库关系、JSON 字段存储和历史记录页面设计。
- 面试表达：我保存了问答历史和引用信息，为后续学习复盘、错题本和项目记忆打基础。

### 我应该重点理解什么
本版本最重要的是理解 RAG 的完整链路：文档解析 → chunk 切分 → 向量化 → Qdrant 入库 → 问题向量化 → 语义检索 → Prompt 组装 → 模型回答 → 引用来源展示 → 历史保存。

### 后续补课建议
建议先补 FastAPI 文件上传和 Pydantic，再补文档解析与 chunk 切分，然后学习 embedding、Qdrant collection/point/payload，最后集中复盘 RAG Prompt 和引用来源设计。

### 面试表达方式
我在 AI Knowledge OS Pro V1 中实现了基础文档 RAG 知识库闭环，支持知识库空间、txt/md/pdf 文档上传、解析、切片、向量化入库、按知识库语义检索、基于上下文的大模型问答、引用来源展示和问答历史保存。同时我把版本涉及的知识点沉淀为学习档案，方便后续复盘和面试表达。

### 下一版本建议
V2 建议优先做文档管理增强和学习复盘增强，例如删除/重建索引、文档标签、学习卡片和错题本雏形。原因是 V1 已经跑通 RAG 主链路，下一步应提升资料治理和复习效率，而不是过早扩展视频、语音等复杂输入。

<!-- slug:v2-real-mode-governance-learning-coach -->
## V2：真实模式、文档治理、RAG 加固与学习教练

### 版本总结
V2 在 V1 的文档 RAG 闭环上做工程化加固：显式区分真实模式和演示模式，增加系统诊断、Alembic 迁移、文档治理、索引兼容检查、RAG 引用与拒答机制，并把学习档案升级为可确认的版本学习包。

### 本版本实现了什么
- 新增 DEMO_MODE 与 OpenAI-compatible provider adapter，禁止真实模式静默 fallback。
- 新增系统状态和 LLM/Embedding/Qdrant 连通性测试接口。
- 新增 ingestion job，支持上传去重、重试、重新解析、重建索引和删除文档。
- 新增 embedding fingerprint 和 index_version，提问前检查索引兼容性。
- RAG 检索使用 top_k、score_threshold、资料不足拒答和引用编号。
- 新增版本学习包、知识点详情、学习卡片、练习题、笔记与掌握状态。
- 学习包确认后追加 Markdown 学习档案和阶段交付日志，保留历史记录。

### 本版本新增或修改的主要文件
- `backend/app/core/config.py`：集中管理真实/演示模式、provider、Qdrant、检索和索引配置。
- `backend/app/services/providers.py`：封装 LLM 与 Embedding provider adapter。
- `backend/app/services/ingestion_service.py`：管理文档上传、解析、切片、索引、重试和删除流水线。
- `backend/app/services/rag_service.py`：执行提问前检查、检索、Prompt 构建、引用返回和问答历史保存。
- `backend/app/services/learning_package_service.py`：生成、确认和导出版本学习包。
- `backend/alembic/versions`：保存 V1 baseline 与 V2 schema migration。
- `frontend/app/system/page.tsx`：展示运行模式、依赖状态和修复建议。
- `frontend/app/learning/page.tsx`：展示版本学习时间线和 V2 学习包。

### 本版本涉及的 AI 应用开发知识点
#### 真实模式与演示模式
- 小白解释：真实模式会调用你配置的大模型和 embedding 服务；演示模式只是为了无 key 时跑通流程，不能当正式效果。
- 项目用法：V2 用 DEMO_MODE 明确控制 fake/hash provider，避免系统悄悄给出假回答。
- 代码位置：backend/app/core/config.py, backend/app/services/providers.py
- 后续补课：补课环境变量、配置分层、provider adapter 和错误处理。
- 面试表达：我把模型调用从业务流程中抽象成 provider adapter，并显式区分真实模式和演示模式，避免生产环境静默 fallback。

#### 系统诊断接口
- 小白解释：系统诊断像体检表，告诉你数据库、Qdrant、模型和索引配置哪里正常、哪里需要修。
- 项目用法：V2 提供 /api/system/status 和三类测试接口，前端可以直接展示运行状态和修复建议。
- 代码位置：backend/app/services/system_service.py, backend/app/api/routes_system.py
- 后续补课：补课健康检查、依赖探活和不泄露密钥的状态设计。
- 面试表达：我为 RAG 系统增加了诊断接口，能区分配置缺失、外部依赖不可用和 collection 未初始化等问题。

#### Alembic 数据库迁移
- 小白解释：迁移脚本就是数据库结构的版本记录，让你从 V1 平滑升级到 V2，而不是手动改表。
- 项目用法：V2 引入 baseline 和 migration，新增文档治理、学习系统、索引兼容等字段和表。
- 代码位置：alembic.ini, backend/alembic/env.py, backend/alembic/versions
- 后续补课：补课 revision、upgrade、downgrade、baseline 和 SQLite 迁移限制。
- 面试表达：我用 Alembic 管理 schema 演进，保证已有 V1 数据不删除，并让 V2 新表字段可复现升级。

#### 文档治理与 ingestion job
- 小白解释：文档治理就是让上传不再只是保存文件，还要知道进度、失败原因、能否重试和能否删除干净。
- 项目用法：V2 上传时校验扩展名、大小、SHA256 去重，并用 ingestion job 记录解析和索引进度。
- 代码位置：backend/app/services/ingestion_service.py, backend/app/api/routes_documents.py
- 后续补课：补课文件哈希、幂等删除、状态机和后台任务设计。
- 面试表达：我把文档处理抽成 ingestion pipeline，记录任务状态，支持重试、重新解析、重建索引和精确删除向量 points。

#### 索引兼容与 embedding fingerprint
- 小白解释：不同 embedding 模型生成的向量不能混着查，fingerprint 就是给索引贴上模型和版本标签。
- 项目用法：V2 在文档入库时保存 provider、model、dimensions、index_version，提问前检查是否与当前配置一致。
- 代码位置：backend/app/services/embedding_service.py, backend/app/services/rag_service.py
- 后续补课：补课 embedding 模型维度、向量空间一致性和重建索引策略。
- 面试表达：我增加了 embedding fingerprint，避免模型或维度变更后继续检索旧索引导致相关性失真。

#### RAG 拒答与引用加固
- 小白解释：资料不够时，好的 RAG 系统应该说不知道，而不是硬编；引用能告诉你答案来自哪里。
- 项目用法：V2 使用 top_k、score_threshold 和 insufficient_context，答案要求使用 [1]、[2] 引用编号。
- 代码位置：backend/app/services/rag_service.py, backend/app/services/prompt_builder.py
- 后续补课：补课检索阈值、prompt injection 防护、引用生成和置信度设计。
- 面试表达：我在 RAG 链路里加入资料充分性判断和引用编号，降低幻觉，并让回答可追溯。

#### 项目式学习档案
- 小白解释：学习档案不是普通日志，而是把每个版本做了什么、学到什么、怎么面试表达都沉淀下来。
- 项目用法：V2 用版本学习包、知识点、卡片、练习题和 Markdown 导出支撑后续复盘。
- 代码位置：backend/app/services/learning_package_service.py, docs/learning_log.md
- 后续补课：补课学习产品设计、知识点拆解、复习卡片和项目复盘写法。
- 面试表达：我把项目开发过程沉淀为结构化学习资产，使功能演进、技术复盘和面试表达形成闭环。

### 我应该重点理解什么
重点理解 V2 为什么要从“能跑通”升级到“可诊断、可迁移、可治理、可拒答、可复盘”。

### 下一步应该学什么
下一步建议按 provider adapter、Alembic migration、ingestion pipeline、index fingerprint、RAG refusal、learning package 六条线复习。

### 面试表达方式
AI Knowledge OS Pro V2 在 V1 RAG 闭环基础上完成工程化加固：我显式区分真实模式和演示模式，引入 provider adapter、系统诊断、Alembic 迁移、文档治理、索引兼容检查和 RAG 引用拒答机制，同时把版本学习档案升级成可确认、可复习、可面试表达的学习包系统。

### 下一版本学习重点
V3 可以优先接入后台任务队列、网页收藏和更细粒度的学习进度统计，再考虑图片、音频、视频等多模态输入。

<!-- learning:v2-5-product-learning-experience -->
## V2.5???????????????????

### ????????
- ???????????????????????????AI ???????????
- ???????????????????????????????????
- ??????????????????????????????
- ?????????????????????????????????
- ????????????chunks???????????
- PDF ???Markdown ?????? chunk?Qdrant payload ??????
- Chat ?????????????? Markdown ??????
- RAG ???????? citation ??????????????
- ????????????????????????????????? dashboard?
- ???? Git ???????????????

### ????
- `backend/app/services/ingestion_service.py`????????????
- `backend/app/services/rag_service.py`?RAG ???????????????
- `backend/app/services/learning_package_service.py`??????????????????
- `backend/app/services/chat_session_service.py`???????????
- `backend/alembic/versions/0003_v2_5_product_learning.py`?V2.5 ??????
- `frontend/components/AppShell.tsx`???????????
- `frontend/components/DocumentUploader.tsx`?????????
- `frontend/components/KnowledgeChat.tsx`???????????
- `scripts/generate_learning_package.py`???????????????

### ??? 1???????
- ????????????????????????????????????????
- ?????V2.5 ????????????????AI ??????????????????????
- ?????`frontend/components/AppShell.tsx`?`frontend/app/layout.tsx`?
- ????????? AppShell ? ?????????? ? ????? ? ???????
- ??????????????????????????????
- ??????????????????????????????????
- ?????????????????????????????
- ???????????????????????????????????? RAG ????????
- ??????? Dashboard???????????????????

### ??? 2?????????
- ????????????????????????????????????
- ?????????????? job_id????????????? Embedding??? Qdrant?
- ?????`backend/app/services/ingestion_service.py`?`backend/app/api/routes_ingestion_jobs.py`?`frontend/components/DocumentUploader.tsx`?
- ????????? ? ?? Document ? IngestionJob ? ???? ? ?????? ? ?????
- ????????????????????????????????????
- ??????? V2.5 ??????????????? Celery?
- ?????????? 10 ? PDF??? 1 ?????????????
- ?????????????????????????????????????????????
- ??????????????????????????

### ??? 3?RAG ???????
- ???????????????????????????????????????
- ????????????????? `[1]` ??????? `citation_validation_failed`????????????????????
- ?????`backend/app/services/rag_service.py`?`frontend/components/CitationPanel.tsx`?
- ??????? chunks ? ?? citation ids ? LLM ?? ? ?????????? ? ????????????
- ??????????????????????????????
- ??????? `citations` ? `used_citation_ids` ?????
- ????????????? `[9]`???????? `[1]~[5]`????????
- ??????? RAG ???????????????????????????
- ??????? RAG ????????prompt injection ??? grounded answer?

### ??? 4?????????
- ????????????????? PDF ????Markdown ??????????????
- ?????V2.5 ? PDF page_number ? Markdown heading_path ?? chunk?Qdrant payload ??????
- ?????`backend/app/services/document_parser.py`?`backend/app/services/chunker.py`?`backend/app/services/ingestion_service.py`?
- ????????? ? ????/???? ? ?? ? ?????? Qdrant ? ???????????
- ????????????????????????????????
- ??????? Markdown ??????????????
- ???????? V3 ??????????????????
- ????????? chunk ???????????? RAG ??????????????????
- ??????? PDF ?????Markdown AST?metadata schema?

### ??? 5???????
- ?????????????????????????????????????????????
- ?????V2.5 ??? dashboard?????????????????????????
- ?????`backend/app/services/learning_package_service.py`?`frontend/app/learning/page.tsx`?`frontend/app/learning/cards/page.tsx`?
- ???????????? ? ???? ? ?????/??/?? ? ????????????
- ??????????????????????????????????
- ????????????????????????
- ??????????? RAG ??????????
- ?????????????????????????????????????????
- ???????????????????????????????

### ?????????
V2.5 ????????????????? AI ?????????????????????????????????????????

### ????????
????????????????????RAG ????????????????? ??????

### V2.5 ????
- `python -m compileall backend/app`????
- `pytest`?15 passed?
- `npm run typecheck`????
- `npm run build`????
- `alembic upgrade head`?????? head ? `0003_v2_5_product_learning`?

<!-- learning:v2-5-final-polish-20260611 -->
## V2.5 最终补充：产品化交互与学习闭环收口

### 本次补充实现了什么
- 补齐统一 UI 组件：Toast、Modal、ConfirmDialog、Drawer、DataTable、FilterBar、Pagination、ActionMenu、FormField、HelpTooltip、CopyButton。
- 升级知识问答页：支持停止展示本次回答、重新生成、复制、收藏回答、保存为学习笔记、转学习卡片追问、生成面试表达追问。
- 优化 Chat 并发状态：用户停止生成后，晚返回的旧请求不会覆盖新的页面状态。
- 改进学习包生成脚本：未提交仓库也能展开未跟踪目录，且优先展示 UI、Chat、RAG、任务流水线、学习系统等复盘关键文件。
- 更新 V2.5 验收报告，补充本次最终验证结果。

### 主要文件
- `frontend/components/ui.tsx`：统一交互组件库，承载提示、确认、表格、表单、复制等通用体验。
- `frontend/components/KnowledgeChat.tsx`：知识问答主交互，连接会话、RAG 回答、引用、收藏、笔记和学习追问。
- `frontend/app/globals.css`：新增 Toast、Modal、DataTable、ActionMenu、Chat transcript 等样式。
- `scripts/generate_learning_package.py`：根据 Git 状态和路由扫描生成学习包草稿，并排除缓存、数据库、发布包等非复盘文件。
- `docs/v2_5_acceptance_report.md`：记录 V2.5 最终验收范围与测试结果。

### 新增知识点 1：统一 UI 组件库
- 小白解释：组件库就是把常用的提示、弹窗、表格、空状态等做成统一零件，以后每个页面直接复用，体验就不会东一块西一块。
- 项目用法：V2.5 将 Toast、ConfirmDialog、DataTable 等沉淀到 `frontend/components/ui.tsx`，为上传、文档管理、学习中心和系统状态页复用。
- 补课建议：先补 React props 和 children，再补组件组合、可访问性、状态反馈和设计系统。
- 面试表达：我在项目中抽象了统一 UI 组件库，减少重复代码，并保证 loading、empty、error、confirm 和 toast 等交互反馈一致。

### 新增知识点 2：Chat 学习闭环
- 小白解释：好的问答页不只是回答问题，还要能把回答继续变成笔记、卡片、追问和面试表达。
- 项目用法：`KnowledgeChat.tsx` 调用 session、regenerate、favorite、learning notes 等 API，让一次问答能继续进入学习中心。
- 补课建议：补 React 状态管理、异步请求、防止重复提交、乐观/保守更新、会话模型。
- 面试表达：我把 RAG 问答页从单次问答升级为多轮学习工作流，支持回答复用、收藏、笔记沉淀和面试表达生成。

### 新增知识点 3：异步请求取消与陈旧响应保护
- 小白解释：如果用户点了停止，旧请求后来才回来，页面不应该又把旧答案塞回来，这就是防止“过期响应”污染界面。
- 项目用法：`KnowledgeChat.tsx` 使用 request sequence 和 ignore flag，避免停止后的旧响应覆盖当前 UI。
- 补课建议：补 JavaScript Promise、AbortController、请求竞态、React useRef。
- 面试表达：我在前端问答流程中处理了异步竞态，避免用户停止生成后旧响应覆盖新状态，提升交互可靠性。

### 新增知识点 4：版本学习包生成脚本
- 小白解释：学习包脚本像一个项目复盘助手，会收集改了哪些文件、有哪些接口、测试结果如何，再转成可学习的版本档案。
- 项目用法：`scripts/generate_learning_package.py` 会展开未跟踪目录、排除无关产物，并优先列出最值得复盘的关键文件。
- 补课建议：补 Git status、文件遍历、过滤规则、结构化 JSON 输出、发布排除策略。
- 面试表达：我实现了基于 Git 状态的版本学习包生成脚本，把真实工程变更转化为学习档案草稿，支撑项目式学习闭环。

### 我应该重点理解什么
V2.5 的重点不是单个按钮，而是“产品操作反馈 + RAG 可信引用 + 学习资产沉淀”三件事如何连起来。问答页得到答案后，用户可以继续复盘、收藏、写笔记、转卡片和组织面试表达，这才像一个个人 AI 学习操作系统。

### 下一步应该学什么
建议下一轮先补：React 组件设计、异步请求竞态、RAG 引用校验、学习卡片数据模型、版本学习包生成。随后再进入 V3 的多模态解析：图片 OCR、语音转写、视频时间戳引用。

### 最终验证结果
- `python -m compileall backend/app`：通过。
- `pytest`：15 passed。
- `python -m alembic current`：`0003_v2_5_product_learning (head)`。
- `python -m compileall scripts/generate_learning_package.py`：通过。
- `npm run typecheck`：通过。
- `npm run build`：通过。
<!-- learning:v3-task-multimodal-foundation-20260618 -->
## V3：稳定任务引擎与多模态知识中枢基础

### 版本总结
V3 在 V2.5 的产品化学习工作台基础上，把文档处理从轻量线程式后台流程升级为 Redis/RQ Worker 驱动的持久化任务引擎，并建立多模态 Source 数据模型基础。当前版本重点解决任务状态可见、重启后可恢复、取消状态可持久化、数据库迁移可验证、系统诊断可定位问题。V3 只完成多模态底座，不把 OCR、音频转写、视频时间轴解析伪装成已完成能力。

### 本版本实现功能
- 引入 Redis/RQ 任务队列和独立 Worker 入口。
- 扩展 `IngestionJob`，记录步骤、队列、Worker、尝试次数、心跳、耗时、错误码、父任务和取消时间。
- 新增 `JobEvent`，持久化记录任务排队、运行、失败、取消和完成事件。
- 文档上传、重试、重新解析、重建索引改为创建后台任务并返回 `job_id`。
- 新增任务中心 `/tasks`，展示任务列表、进度、事件时间线、重试和取消。
- 系统状态页增加 Redis、Worker 心跳和任务队列诊断，并对 Redis/数据库 URL 脱敏。
- 新增 V3 Alembic migration：`0004_v3_task_multimodal_foundation`。
- 新增多模态基础模型：Source、SourceRevision、MediaAsset、TranscriptSegment、VisualFrame、MultimodalChunk、CitationLocator、IndexRevision。
- 重写学习包生成脚本，让它基于真实 Git 变更、路由、依赖、迁移和测试报告生成草稿。
- 更新 README、架构文档、路线图、任务流文档、V3 验收报告和环境变量示例。
- 保持旧学习档案不覆盖，只追加 V3 记录。

### 本版本主要文件
- `backend/app/services/task_broker.py`：Redis/RQ 任务入队、取消和陈旧任务中断标记。
- `backend/app/worker.py`：独立 Worker 启动入口，启动时恢复可重试任务。
- `backend/app/tasks/ingestion_tasks.py`：Worker 执行 ingestion job 的任务函数。
- `backend/app/services/ingestion_service.py`：文档处理流水线、任务事件、持久化取消和后台入队。
- `backend/app/models/ingestion_job.py`：V3 任务状态字段。
- `backend/app/models/task_event.py`：任务事件模型。
- `backend/app/models/source.py`：多模态 Source 和引用定位基础模型。
- `backend/alembic/versions/0004_v3_task_multimodal_foundation.py`：V3 数据库迁移。
- `backend/app/services/system_service.py`：DB、Redis、Worker、Qdrant、LLM、Embedding 和索引状态诊断。
- `frontend/app/tasks/page.tsx`：任务中心页面。
- `frontend/app/system/page.tsx`：V3 系统状态页。
- `frontend/components/DocumentUploader.tsx`：上传队列与后台任务轮询。
- `frontend/components/AppShell.tsx`：V3 导航和任务中心入口。
- `scripts/generate_learning_package.py`：真实变更驱动的学习包草稿生成脚本。
- `docs/v3_acceptance_report.md`：V3 验收报告。

### 知识点 1：Redis/RQ 后台任务队列
- 小白解释：以前上传文件时，后端像是在一个请求里把所有活都干完；现在是先把活放进任务队列，再由 Worker 慢慢处理。
- 项目用法：上传接口创建 `IngestionJob` 后调用 `task_broker.enqueue_ingestion()`，Worker 执行 `run_ingestion_job()`。
- 后续补课建议：学习 Redis、RQ、队列、Worker、任务超时、失败重试和幂等处理。
- 面试表达：我把文档 ingestion 从请求内同步处理升级为 Redis/RQ 后台任务，提升了长耗时 AI 流程的可靠性和可恢复性。

### 知识点 2：任务状态机与事件表
- 小白解释：状态机就是规定任务从“等待”到“运行”到“完成/失败/取消”的合法路径；事件表就是任务过程的流水账。
- 项目用法：`IngestionJob.status` 保存当前状态，`JobEvent` 保存每次状态变化、步骤、进度和错误详情。
- 后续补课建议：复习状态机设计、任务日志、事件溯源、前端轮询和错误展示。
- 面试表达：我为后台任务增加了持久化事件表，让解析、切片、Embedding 和索引过程可观察、可追踪、可诊断。

### 知识点 3：Worker 心跳和陈旧任务恢复
- 小白解释：Worker 心跳像“我还活着”的信号；如果长时间没有心跳，系统就知道任务可能卡住了。
- 项目用法：任务记录 `heartbeat_at`，`mark_stale_jobs_interrupted()` 把超时运行任务标记为 `interrupted`，Worker 启动时重新入队。
- 后续补课建议：学习分布式任务的 heartbeat、lease、timeout、retry 和 dead letter queue。
- 面试表达：我通过 Worker 心跳和 interrupted 状态处理进程重启或任务中断问题，避免任务永远卡在 running。

### 知识点 4：Alembic 迁移与回滚验证
- 小白解释：迁移脚本是数据库结构的版本记录，让项目升级时不用手工改表，也能知道怎么回退。
- 项目用法：V3 migration 扩展 `ingestion_jobs` 并创建多模态基础表，同时验证空库 upgrade、downgrade、旧 V2.5 数据库升级。
- 后续补课建议：复习 Alembic revision、upgrade/downgrade、SQLite batch alter、数据迁移和回滚测试。
- 面试表达：我用 Alembic 管理 V3 schema 演进，并在临时库和真实库上验证升级链路，保证学习档案和既有数据不被破坏。

### 知识点 5：多模态统一 Source 模型
- 小白解释：文档、图片、音频、视频虽然格式不同，但都可以抽象成“来源”和“片段”，以后统一检索和引用。
- 项目用法：V3 新增 Source、MediaAsset、TranscriptSegment、VisualFrame、MultimodalChunk、CitationLocator 等表，为 OCR、转写和视频时间轴引用做准备。
- 后续补课建议：学习实体建模、revision/staging/active、媒体元数据、时间戳引用和多模态 RAG。
- 面试表达：我先为多模态资料设计统一 schema，而不是直接堆功能，保证后续图片、音频、视频都能进入同一套 RAG 和学习沉淀流程。

### 知识点 6：系统诊断与密钥脱敏
- 小白解释：系统诊断页像体检报告，告诉你数据库、Redis、Worker、Qdrant 和模型服务哪里正常、哪里需要修。
- 项目用法：`/api/system/status` 返回 Redis 队列、Worker 心跳、Qdrant、LLM、Embedding 和索引状态，同时隐藏 URL 中的密码。
- 后续补课建议：学习健康检查、依赖探活、错误分级、密钥脱敏和面向用户的修复建议。
- 面试表达：我把关键外部依赖集中到系统诊断接口，并确保密钥不会泄露到前端响应。

### 知识点 7：前端任务中心
- 小白解释：任务中心让用户不用猜后台在干什么，可以看到每个文件处理到哪一步、是否失败、能不能重试。
- 项目用法：`/tasks` 轮询任务列表和事件接口，展示进度条、步骤、Worker、错误详情、重试和取消操作。
- 后续补课建议：复习 React 状态管理、轮询、列表选中态、loading/empty/error 和操作反馈。
- 面试表达：我做了任务中心，把长耗时 AI 处理过程产品化展示，降低用户等待焦虑，也方便排查失败原因。

### 我应该重点理解什么
V3 的重点不是“多加几个页面”，而是理解 AI 应用里的长耗时处理为什么需要任务队列、状态持久化、事件记录、Worker 恢复和系统诊断。只有任务处理稳定了，后续图片 OCR、音频转写和视频解析才不会变成不可控的黑盒。

### 下一步应该学什么
下一步建议按顺序学习：Redis/RQ Worker、任务状态机、Alembic 数据迁移、多模态数据建模、系统诊断、前端轮询体验。之后再进入真实 OCR、音频转写、视频关键帧和时间轴引用。

### 面试表达方式
AI Knowledge OS Pro V3 中，我把原来的文档 RAG 系统升级为稳定任务引擎驱动的多模态知识中枢基础。后端使用 Redis/RQ 和独立 Worker 处理文档 ingestion，任务状态和事件持久化到 SQLite；前端新增任务中心和系统诊断页，用户能看到处理进度、Worker 状态和错误原因。同时我通过 Alembic 增加 Source、MediaAsset、TranscriptSegment、VisualFrame、MultimodalChunk 等多模态基础模型，为后续图片 OCR、音频转写和视频时间轴引用打好数据底座。

### 本阶段验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：19 passed。
- `python -m alembic upgrade head`：通过，当前版本 `0004_v3_task_multimodal_foundation`。
- `npm run typecheck`：通过。
- `npm run build`：通过，包含 `/tasks` 页面。

<!-- learning:v3-1-image-metadata-ingestion-20260618 -->
## V3.1：图片元数据接入与媒体资料库

### 版本总结
V3.1 是 V3 多模态能力的第一个小闭环：不直接假装完成 OCR 或图像理解，而是先把图片作为真实资料来源接入系统，保存文件、尺寸、格式、哈希、来源记录和媒体资产，并在前端提供媒体资料库和来源详情页。这个阶段的关键价值是“可信地开始多模态”，让后续 OCR、截图报错识别和视觉描述都能接到同一套 Source/MediaAsset 结构上。

### 本版本新增功能
- 支持上传 png、jpg、jpeg、webp、bmp 图片到指定知识库。
- 后端使用 Pillow 读取真实图片宽度、高度和格式。
- 同一知识库内按 SHA256 检测重复图片，避免重复入库。
- 创建 `Source`、`SourceRevision`、`MediaAsset`，把图片纳入 V3 多模态资料模型。
- 图片元数据里明确记录 `ocr_status=not_configured` 和 `vision_description_status=not_configured`。
- 上传页新增图片资料接入面板。
- 新增 `/media` 媒体资料库页面。
- 新增 `/media/sources/[id]` 媒体来源详情页。
- AppShell 侧边栏新增“媒体资料库”入口。
- 新增图片上传相关测试。

### 本版本主要文件
- `backend/app/services/media_service.py`：图片上传、校验、保存、哈希去重、Pillow 元数据读取、Source/MediaAsset 入库。
- `backend/app/api/routes_media.py`：图片上传、来源列表、来源详情 API。
- `backend/app/schemas/media_schema.py`：媒体来源和媒体资产的响应结构。
- `backend/app/models/source.py`：V3 多模态 Source、Revision、Asset 基础模型。
- `backend/tests/test_v3_image_upload.py`：图片元数据入库、边界说明、重复检测测试。
- `frontend/app/upload/page.tsx`：上传页新增图片接入面板和最近图片入口。
- `frontend/app/media/page.tsx`：媒体资料库列表、筛选、统计和能力边界展示。
- `frontend/app/media/sources/[id]/page.tsx`：单个媒体来源详情页。
- `frontend/components/AppShell.tsx`：侧边栏新增媒体资料库导航。
- `docs/v3_1_image_metadata_report.md`：V3.1 图片元数据接入报告。

### 知识点 1：可信多模态接入
- 小白解释：可信多模态不是先把“识别结果”编出来，而是先保存真实文件和真实元数据，没做的能力明确告诉用户没做。
- 项目用法：图片元数据记录 `image_metadata_only`、`ocr_status=not_configured`、`vision_description_status=not_configured`，前端也展示“OCR 未启用”。
- 后续补课建议：学习 AI 产品里的能力边界、幻觉控制、模型可用性提示和真实/演示模式区分。
- 面试表达：我在图片接入阶段没有伪造 OCR 或视觉描述，而是先建立真实元数据闭环，并在前后端明确展示能力边界，保证产品可信。

### 知识点 2：文件哈希去重
- 小白解释：哈希可以理解成文件内容的指纹；两个文件内容一样，指纹就一样。
- 项目用法：上传图片时计算 SHA256，并在同一知识库内检查已有 `Source.content_hash`，重复时拒绝入库并删除临时保存文件。
- 后续补课建议：学习 SHA256、文件去重、幂等上传、重复数据清理和错误提示设计。
- 面试表达：我用 SHA256 做知识库内媒体去重，避免同一张图片重复进入资料库，也为后续索引去重打基础。

### 知识点 3：Pillow 图片元数据解析
- 小白解释：Pillow 是 Python 里常用的图片处理库，可以读取图片尺寸、格式，也能判断文件是不是真图片。
- 项目用法：`media_service._inspect_image()` 使用 Pillow `verify()` 校验图片，再读取 `image.size` 和 `image.format`。
- 后续补课建议：学习 Pillow、图片 MIME、文件扩展名和真实内容校验之间的区别。
- 面试表达：我在上传链路里用 Pillow 做图片内容校验和尺寸读取，避免只靠扩展名判断文件类型。

### 知识点 4：Source / MediaAsset 分层
- 小白解释：Source 是“这份资料是什么”，MediaAsset 是“这份资料对应的实际文件或衍生文件”。
- 项目用法：上传图片后创建 Source 记录来源信息，再创建 MediaAsset 记录原始图片文件；后续 OCR 文本、缩略图、关键帧也可以作为资产或片段继续挂载。
- 后续补课建议：学习实体建模、资源与资产分层、revision、metadata_json 和可扩展 schema。
- 面试表达：我把图片接入建模为 Source 与 MediaAsset 两层，为后续 OCR、视觉描述、音频转写和视频关键帧复用同一套多模态数据结构。

### 知识点 5：媒体资料库产品化
- 小白解释：后端存了数据不代表用户能用；媒体资料库就是让用户能看见、筛选、进入详情、理解当前资料状态。
- 项目用法：`/media` 展示来源统计、类型筛选、知识库筛选和能力说明；`/media/sources/[id]` 展示文件名、MIME、尺寸、资产和元数据 JSON。
- 后续补课建议：学习信息架构、列表页/详情页设计、空状态、筛选和技术详情折叠。
- 面试表达：我不仅完成了图片入库 API，还补了媒体资料库和详情页，让多模态资料从工程能力变成可见、可理解的产品能力。

### 我应该重点理解什么
V3.1 的重点是“先可信，再智能”。多模态 AI 应用不能为了看起来完整而伪造 OCR、图像描述或转写内容。正确做法是先建立真实文件、真实元数据、真实状态和清晰边界，再逐步接入真实模型能力。

### 下一步应该学什么
下一步建议学习 OCR pipeline：图片预处理、OCR provider adapter、错误截图结构化提取、OCR 文本如何变成 MultimodalChunk、图片引用如何落到 CitationLocator。

### 面试表达方式
AI Knowledge OS Pro V3.1 中，我完成了图片资料的可信接入闭环。系统支持图片上传、类型校验、大小限制、SHA256 去重、Pillow 元数据解析，并把图片保存为 Source、SourceRevision 和 MediaAsset。前端新增媒体资料库和来源详情页，明确展示当前是 metadata-only 模式，不伪造 OCR 或视觉描述，为后续真实 OCR、截图错误识别和图像引用问答打好了产品和数据基础。

<!-- learning:v3-2-configurable-image-ocr-20260618 -->
## V3.2：可配置图片 OCR 与图片文字检索

### 版本总结
V3.2 在 V3.1 图片元数据接入的基础上，补上了“真实 OCR 可接入”的第一条多模态内容流水线。系统现在支持在图片详情页手动触发 OCR；如果没有配置真实 OCR provider，会明确返回 `OCR_NOT_CONFIGURED`，不生成伪文本；如果 OCR 成功，识别文本会保存为 `MultimodalChunk`，写入 `CitationLocator`，生成 embedding 并进入 Qdrant，让 Chat 可以检索并引用图片来源。

### 本版本新增功能
- 新增 OCR 配置项：`OCR_PROVIDER`、`OCR_API_KEY`、`OCR_BASE_URL`、`OCR_MODEL`、`OCR_TIMEOUT_SECONDS`、`OCR_MAX_RETRIES`。
- 新增 OpenAI-compatible vision OCR provider。
- 新增 `POST /api/media/sources/{source_id}/ocr`。
- OCR 未配置时返回 `OCR_NOT_CONFIGURED`，不会静默 fake。
- OCR 成功后创建新的 `SourceRevision`。
- OCR 文本保存为 `MultimodalChunk`。
- 图片来源位置保存为 `CitationLocator`。
- OCR chunk 生成 embedding 并写入 Qdrant。
- RAG 问答支持检索图片 OCR chunk。
- 系统状态页新增 OCR provider 诊断。
- 媒体详情页新增“执行真实 OCR”按钮和 OCR 片段展示。
- 新增 OCR 相关后端测试。

### 本版本主要文件
- `backend/app/services/ocr_service.py`：OCR provider 抽象与 OpenAI-compatible vision OCR 调用。
- `backend/app/services/media_service.py`：图片 OCR 处理、SourceRevision/MultimodalChunk/CitationLocator/IndexRevision 写入。
- `backend/app/api/routes_media.py`：图片 OCR API。
- `backend/app/services/rag_service.py`：问答前检查多模态索引，并允许图片 OCR chunk 参与检索。
- `backend/app/services/system_service.py`：OCR provider 系统诊断。
- `backend/app/schemas/media_schema.py`：SourceRevision 和 MultimodalChunk 响应结构。
- `backend/app/schemas/system_schema.py`：OCR 状态字段。
- `backend/tests/test_v3_image_ocr.py`：OCR 未配置和 OCR 入库/RAG 检索测试。
- `frontend/app/media/sources/[id]/page.tsx`：图片详情页 OCR 操作与 OCR chunk 展示。
- `frontend/app/system/page.tsx`：系统页 OCR 状态卡片。
- `.env.example`、`backend/.env.example`：OCR 配置样例。
- `docs/rag_pipeline.md`、`docs/architecture.md`、`docs/index_compatibility.md`：OCR 与多模态索引文档更新。

### 知识点 1：OCR provider adapter
- 小白解释：adapter 就是把不同模型服务包装成统一接口，业务代码不用关心底层到底是哪家模型。
- 项目用法：`OCRProvider.extract_text()` 负责图片文字提取，当前实现 `OpenAICompatibleVisionOCRProvider`，以后可以加本地 OCR 或其他视觉模型。
- 后续补课建议：学习接口抽象、provider pattern、OpenAI-compatible API、多模态 message 格式和 base64 image data URL。
- 面试表达：我为图片 OCR 增加了 provider adapter，让业务层只依赖统一 OCR 接口，并为后续替换本地 OCR 或其他视觉模型保留扩展点。

### 知识点 2：能力边界与真实模式
- 小白解释：没有模型 key 时，系统应该说“我不能做”，而不是装作识别成功。
- 项目用法：OCR 未配置时返回 `OCR_NOT_CONFIGURED`；系统状态页也显示 OCR 未配置，前端提示不会生成伪识别文本。
- 后续补课建议：学习真实模式、演示模式、错误码、用户提示和 AI 产品可信度设计。
- 面试表达：我坚持真实模式不静默 fallback，图片 OCR 未配置时明确阻断，避免伪造识别结果污染知识库。

### 知识点 3：MultimodalChunk
- 小白解释：不同来源的内容最终都要变成“可检索片段”，图片 OCR 文字也可以像文档 chunk 一样被搜索。
- 项目用法：OCR 成功后把识别文本写入 `MultimodalChunk.content_text/search_text`，并设置 `modality=image_text`。
- 后续补课建议：学习多模态 RAG、chunk 建模、search_text 和 content_text 的区别。
- 面试表达：我把图片 OCR 结果统一落到 MultimodalChunk，使图片文字能复用同一套 embedding、Qdrant 检索和 Chat 引用链路。

### 知识点 4：CitationLocator
- 小白解释：引用不仅要知道“来自哪个文件”，还要知道“在这个来源里的哪里”。
- 项目用法：图片 OCR chunk 会生成 `CitationLocator`，locator 中标记 source id、类型和原始图片资产。
- 后续补课建议：学习引用定位、页码、时间戳、frame、source locator 和可跳转引用设计。
- 面试表达：我为图片 OCR 结果建立 CitationLocator，后续可以扩展到点击引用跳转图片、音频时间点或视频关键帧。

### 知识点 5：多模态索引兼容
- 小白解释：不同 embedding 模型生成的向量不能混着查，否则相似度会失真。
- 项目用法：OCR chunk 写入 `IndexRevision`，保存 embedding provider、model、dimensions、fingerprint 和 index version；RAG 查询前会检查多模态索引兼容性。
- 后续补课建议：学习 embedding fingerprint、index version、向量库 collection 设计和重建索引策略。
- 面试表达：我把多模态索引也纳入 embedding fingerprint 校验，避免图片 OCR chunk 与文档 chunk 使用不同向量配置时被混合检索。

### 我应该重点理解什么
V3.2 的关键是图片 OCR 不只是一个模型调用，而是一条完整链路：配置诊断 → 真实 OCR → 文本入库 → chunk 建模 → 引用定位 → embedding → Qdrant → RAG 检索。只有整条链路打通，图片才真正成为知识库里可问答、可引用的资料。

### 下一步应该学什么
下一步建议学习截图报错识别：如何从 OCR 文本中抽取错误类型、错误堆栈、可能原因、修复步骤，并沉淀到报错归档和学习卡片。之后再推进音频转写和视频时间轴引用。

### 面试表达方式
AI Knowledge OS Pro V3.2 中，我把图片从“只保存元数据”升级为“可配置真实 OCR 并进入 RAG 检索”的多模态资料。后端新增 OCR provider adapter，未配置时返回 `OCR_NOT_CONFIGURED`，不会伪造识别结果；OCR 成功后创建 SourceRevision、MultimodalChunk、CitationLocator 和 IndexRevision，并将 OCR 文本向量化写入 Qdrant。前端媒体详情页支持执行 OCR 和查看识别片段，系统状态页也能诊断 OCR 配置。

<!-- learning:v3-3-screenshot-error-archive-20260618 -->
## V3.3：截图报错识别与报错归档

### 版本总结
V3.3 把图片 OCR 的识别文本继续转化为可复盘的学习资产。系统只在 OCR 文本中出现明确异常类名、HTTP 状态或 error/fatal/failed 标记时创建报错档案，并保存来源图片、OCR chunk、错误类型、消息、堆栈片段、置信度、严重度和排查清单。无法确认时拒绝归档，不虚构根因。

### 本版本新增功能
- 新增 `ErrorArchive` 数据模型。
- 新增 Alembic `0005_v3_3_error_archive` migration。
- 从图片 OCR chunk 中确定性识别异常类名、HTTP 状态和错误标记。
- 同一来源和错误指纹自动去重。
- 保存图片 Source 和 MultimodalChunk 引用。
- 支持待处理、排查中、已解决、已忽略四种状态。
- 新增 `/api/errors` 列表、详情、更新和来源提取 API。
- 新增 `/errors` 报错档案页面。
- 图片详情页新增“识别并归档报错”和关联档案展示。
- 真实数据库升级前自动备份，并在临时库验证 downgrade/upgrade。

### 本版本主要文件
- `backend/app/models/error_archive.py`：报错档案数据模型。
- `backend/alembic/versions/0005_v3_3_error_archive.py`：V3.3 数据库迁移与回滚。
- `backend/app/services/error_archive_service.py`：报错识别、去重、排查建议和状态更新。
- `backend/app/api/routes_errors.py`：报错档案 API。
- `backend/app/schemas/error_schema.py`：报错档案请求与响应结构。
- `backend/tests/test_v3_error_archive.py`：识别、去重、状态更新和无 OCR 拒绝测试。
- `frontend/app/errors/page.tsx`：报错档案工作页。
- `frontend/app/media/sources/[id]/page.tsx`：来源图片归档操作和关联记录。
- `docs/error_archive.md`：报错归档设计文档。
- `docs/v3_3_error_archive_report.md`：V3.3 验收报告。

### 知识点 1：确定性信息抽取
- 小白解释：确定性抽取是按明确规则识别文本，不让模型自由猜测；同样输入会得到同样结果。
- 项目用法：系统使用正则识别 `ModuleNotFoundError`、`TypeError`、`HTTP 404` 和明确 error 行，没有匹配就拒绝创建档案。
- 后续补课建议：学习正则表达式、命名实体抽取、规则引擎和低置信度拒绝策略。
- 面试表达：我对高风险报错归档采用确定性规则和拒绝策略，避免模型幻觉把不确定文本写入长期知识库。

### 知识点 2：错误指纹与幂等归档
- 小白解释：错误指纹是来源、错误类型和错误消息的哈希；同一个错误重复点击不会产生多条记录。
- 项目用法：`ErrorArchiveService` 计算 SHA256 fingerprint，并按 `source_id + fingerprint` 查询和建立唯一索引。
- 后续补课建议：学习幂等 API、业务唯一键、数据库唯一索引和并发重复写入。
- 面试表达：我为报错归档设计业务指纹和唯一约束，使重复提取返回既有记录，保证长期档案不会被重复污染。

### 知识点 3：可追溯学习资产
- 小白解释：一条报错记录必须能回到原截图和 OCR 片段，未来复盘时才知道证据来自哪里。
- 项目用法：ErrorArchive 同时保存 `source_id` 和 `chunk_id`，前端可以跳回来源图片。
- 后续补课建议：学习数据血缘、引用完整性、外键、source locator 和证据链设计。
- 面试表达：我让报错档案保留 Source 与 MultimodalChunk 双重引用，形成从截图到 OCR 再到学习记录的可追溯证据链。

### 知识点 4：数据库迁移安全
- 小白解释：增加新表之前先备份真实数据库，回滚测试在临时数据库做，避免为了测试破坏用户数据。
- 项目用法：真实库只执行 upgrade；E 盘临时库执行 upgrade → downgrade 0004 → upgrade，并验证 head 为 0005。
- 后续补课建议：学习 Alembic upgrade/downgrade、生产备份、迁移演练和回滚边界。
- 面试表达：我在真实库升级前生成带 SHA256 的备份，并把 downgrade 演练隔离到临时库，兼顾迁移可验证性和数据安全。

### 知识点 5：错误处理生命周期
- 小白解释：报错不是保存完就结束，还要记录正在排查、已经解决或不处理。
- 项目用法：报错档案支持 open、investigating、resolved、ignored；解决时记录 resolved_at 和 resolution_notes。
- 后续补课建议：学习状态机、问题管理、复盘模板和回归测试记录。
- 面试表达：我把报错从一次性截图升级为有状态的学习档案，支持排查、解决、标签和复盘记录。

### 我应该重点理解什么
V3.3 的重点是“证据优先”。OCR 文字是证据，异常名和错误消息必须来自证据；排查清单只是建议，不能写成已经确认的根因。长期知识库比一次聊天更需要可追溯和克制。

### 下一步应该学什么
下一步优先学习音频接入：文件校验、媒体元数据、转写 provider、分段时间戳、TranscriptSegment、MultimodalChunk 和可跳转引用。

### 面试表达方式
AI Knowledge OS Pro V3.3 中，我把图片 OCR 继续扩展为可追溯的报错学习档案。系统使用确定性规则抽取异常类型和错误消息，没有明确证据时拒绝归档；通过 SHA256 指纹和唯一索引保证幂等，并保存 Source 与 MultimodalChunk 引用。前端提供报错档案工作页和处理状态，数据库迁移则采用真实库先备份、临时库验证 downgrade/upgrade 的安全策略。

### 本阶段验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：25 passed，5 warnings。
- `npm run typecheck`：通过。
- `npm run build`：通过，包含 `/errors` 页面。
- Alembic：真实库升级到 `0005_v3_3_error_archive`；临时库 upgrade/downgrade/upgrade 通过。

<!-- learning:v3-4-audio-transcription-20260618 -->
## V3.4：音频转写与时间戳引用

### 版本总结
V3.4 把多模态资料从图片扩展到音频。系统支持 MP3、WAV、M4A 上传，读取真实时长；配置真实转写 provider 后，将音频转成带开始/结束时间的 TranscriptSegment，并同步生成 MultimodalChunk、CitationLocator 和 Qdrant 向量。Chat 返回引用时会带时间戳，音频详情页可以播放原音频并查看转写时间轴。

### 本版本新增功能
- 新增 mutagen 项目依赖，读取 MP3/WAV/M4A 时长。
- 新增音频上传 API 和文件播放 API。
- 新增 OpenAI-compatible 音频转写 provider。
- 未配置时返回 `TRANSCRIPTION_NOT_CONFIGURED`，不生成伪转写。
- 转写结果保存语言、分段开始/结束时间和可选可信度。
- 写入 TranscriptSegment、MultimodalChunk、CitationLocator 和 IndexRevision。
- 音频转写片段生成 embedding 并进入 Qdrant。
- RAG 引用新增 source_type、start_ms、end_ms。
- 上传中心新增音频入口。
- 媒体资料库新增音频统计和时长。
- 来源详情页新增音频播放器、转写操作和时间轴。
- 系统状态页新增音频转写 provider 诊断。

### 本版本主要文件
- `backend/app/services/transcription_service.py`：真实音频转写 provider。
- `backend/app/services/media_service.py`：音频上传、时长解析、转写入库和索引。
- `backend/app/api/routes_media.py`：音频上传、文件播放和转写 API。
- `backend/app/schemas/media_schema.py`：TranscriptSegment 响应结构。
- `backend/app/services/rag_service.py`：时间戳引用上下文。
- `backend/app/schemas/chat_schema.py`：音频引用字段。
- `backend/tests/test_v3_audio_transcription.py`：WAV 元数据、转写、索引、RAG 和未配置拒绝测试。
- `frontend/app/upload/page.tsx`：音频上传入口。
- `frontend/app/media/page.tsx`：音频资料统计与展示。
- `frontend/app/media/sources/[id]/page.tsx`：播放器与转写时间轴。
- `frontend/components/CitationPanel.tsx`：时间戳引用展示。
- `docs/audio_transcription.md`：音频转写设计文档。

### 知识点 1：Multipart 音频转写 API
- 小白解释：音频不能像普通 JSON 文本那样发送，需要用 multipart 把文件和模型参数一起上传。
- 项目用法：TranscriptionProvider 把原始音频发送到 OpenAI-compatible `/audio/transcriptions`，请求 verbose JSON 获取分段时间。
- 后续补课建议：学习 multipart/form-data、流式文件上传、超时、429/5xx 重试和大文件限制。
- 面试表达：我为音频转写实现 multipart provider adapter，并只对超时、网络、429 和 5xx 做有限退避重试。

### 知识点 2：音频时长元数据
- 小白解释：在转写前先读取真实时长，可以帮助用户确认文件有效，也为时间轴和资源消耗估算提供基础。
- 项目用法：使用 mutagen 读取 MP3/WAV/M4A `info.length`，保存到 Source 和 MediaAsset 的 duration_ms。
- 后续补课建议：学习音频容器、编码格式、采样率、声道、bitrate 和时长元数据。
- 面试表达：我用 mutagen 做跨格式音频元数据解析，无需依赖系统级 FFmpeg 就能读取真实时长。

### 知识点 3：TranscriptSegment
- 小白解释：整段音频文本太长，按时间切成小段后才能定位、检索和引用。
- 项目用法：每个转写 segment 保存 start_ms、end_ms、language、speaker、text 和 confidence。
- 后续补课建议：学习语音识别分段、VAD、speaker diarization、语言识别和时间戳对齐。
- 面试表达：我把转写结果结构化为 TranscriptSegment，使音频问答可以返回精确时间范围，而不是只引用整个文件。

### 知识点 4：时间戳 RAG 引用
- 小白解释：回答引用音频时，应该告诉用户答案来自 01:30，而不是只说来自某个 mp3。
- 项目用法：时间戳写入 MultimodalChunk locator 和 Qdrant payload，RAG response 与前端 CitationPanel 都保留 start_ms/end_ms。
- 后续补课建议：学习多模态 citation schema、播放器 seek、毫秒/秒转换和前端媒体控制。
- 面试表达：我把音频时间戳贯穿数据库、向量 payload、RAG response 和前端引用面板，建立可定位的音频证据链。

### 知识点 5：真实能力边界
- 小白解释：可以上传音频，不等于已经能转写；没有 provider key 时必须明确区分。
- 项目用法：音频上传始终保存真实元数据；转写按钮在 provider 未配置时返回 `TRANSCRIPTION_NOT_CONFIGURED`，不写 fake segment。
- 后续补课建议：学习配置诊断、provider health check、能力状态和用户错误提示。
- 面试表达：我将音频接入和模型转写解耦，保证无 key 时仍可管理资料，同时严格禁止伪转写进入长期知识库。

### 我应该重点理解什么
V3.4 的关键不是“调用一次 Whisper”，而是完整数据链：音频文件 → 时长元数据 → 转写 segment → 时间戳 locator → embedding → Qdrant → RAG citation → 播放器时间轴。每一层都要保留来源和时间。

### 下一步应该学什么
下一步进入视频：先用 FFmpeg/ffprobe 提取真实元数据和音轨，再复用音频转写链路，最后增加关键帧、章节和播放器跳转。

### 面试表达方式
AI Knowledge OS Pro V3.4 中，我完成了 MP3/WAV/M4A 的统一接入和可配置真实转写。系统用 mutagen 读取真实时长，通过 provider adapter 调用转写服务，将结果保存为带时间戳的 TranscriptSegment 和 MultimodalChunk，再向量化写入 Qdrant。RAG 引用会携带 start_ms/end_ms，前端音频详情页提供播放器与转写时间轴。未配置 provider 时系统明确拒绝，避免伪字幕污染知识库。

### 本阶段验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：27 passed，11 warnings。
- `npm run typecheck`：通过。
- `npm run build`：通过。
- Alembic head 保持 `0005_v3_3_error_archive`，V3.4 复用已有多模态表。

<!-- learning:v3-5-video-pipeline-20260619 -->
## V3.5：视频接入、关键帧与视频时间戳引用

### 版本总结
V3.5 把多模态资料从音频继续扩展到视频。系统支持 MP4/MOV 上传，使用 FFmpeg/ffprobe 读取真实时长、宽高和是否包含音轨；上传后保存原视频并提取至少一个真实关键帧。配置真实转写 provider 后，视频会先抽取 WAV 音轨，再复用转写链路生成 TranscriptSegment、MultimodalChunk、CitationLocator 和 IndexRevision。Chat 检索视频转写时会返回 `source_type=video` 与 start/end 时间戳，前端视频详情页提供播放器、关键帧、元数据、转写动作和时间轴。

### 本版本新增功能
- 新增 MP4/MOV 视频上传的真实元数据读取。
- 上传阶段保存 original_video MediaAsset，并提取 keyframe MediaAsset。
- 上传阶段写入 VisualFrame，保证视频资料即使未转写也有可追溯关键帧。
- 视频转写前先检查真实 provider 配置，未配置时返回 `TRANSCRIPTION_NOT_CONFIGURED`，不抽音轨、不写伪字幕。
- 视频转写时用 FFmpeg 抽取 WAV 音轨，并调用真实 transcription provider。
- 视频转写结果保存为带时间戳的 TranscriptSegment。
- 生成 `video_transcript` MultimodalChunk、CitationLocator 和 IndexRevision。
- Qdrant payload 保留 `source_type=video`、`start_ms` 和 `end_ms`。
- RAG 回答可返回视频时间戳引用。
- 媒体详情页新增视频播放器、关键帧 poster/预览、转写按钮和视频转写时间轴。
- 新增媒体资产文件 API，用于安全读取已登记的关键帧资源。
- 新增后端视频测试覆盖上传、未配置拒绝和成功转写/RAG 路径。

### 本版本主要文件
- `backend/app/services/video_service.py`：FFmpeg/ffprobe 视频探测、音轨抽取和关键帧抽取。
- `backend/app/services/media_service.py`：视频上传、关键帧、转写入库、索引和真实模式边界。
- `backend/app/api/routes_media.py`：视频上传、媒体资产文件读取和音视频转写 API。
- `backend/tests/test_v3_5_video_transcription.py`：视频上传、未配置拒绝、成功转写和 RAG 引用测试。
- `frontend/app/media/sources/[id]/page.tsx`：视频播放器、关键帧、转写时间轴和状态展示。
- `frontend/app/media/page.tsx`：视频资料统计和媒体库展示。
- `frontend/services/api.ts`：媒体资产 URL 与通用转写 API。
- `docs/audio_transcription.md`：扩展为音频/视频共用转写链路说明。
- `docs/rag_pipeline.md`：新增视频 RAG ingestion 说明。
- `docs/v3_5_video_pipeline_report.md`：V3.5 验收报告。

### 知识点 1：FFmpeg/ffprobe 视频元数据
- 小白解释：视频文件不是只看扩展名，要读取容器里的真实时长、画面尺寸和音轨。
- 项目用法：`VideoTooling.probe()` 调 ffprobe 获取 JSON，失败时用 ffmpeg stderr 兜底解析 duration、width、height 和 audio stream。
- 后续补课建议：学习视频容器、编码、stream、duration、frame、音轨和 ffprobe JSON。
- 面试表达：我用 FFmpeg/ffprobe 建立视频真实元数据边界，避免只依赖文件名或 MIME 类型判断视频能力。

### 知识点 2：视频关键帧资产
- 小白解释：关键帧是视频里的某一张截图，能让用户快速确认视频内容，也能作为未来视觉检索的基础。
- 项目用法：上传视频后提取 keyframe，保存为 `VisualFrame` 和 `MediaAsset`；转写新修订时复用关键帧并挂到活动 revision。
- 后续补课建议：学习 scene detection、thumbnail、poster、frame timestamp 和媒体派生资产管理。
- 面试表达：我把关键帧当作可追溯派生资产保存，而不是只在前端临时截图，因此后续可继续扩展视觉 OCR 或镜头级索引。

### 知识点 3：视频转写的两阶段处理
- 小白解释：转写服务通常吃音频，不直接吃视频；所以要先从视频里抽音轨，再把音频交给 provider。
- 项目用法：`process_audio_transcription()` 对 video source 先检查 provider，再用 FFmpeg 抽 WAV，最后调用 OpenAI-compatible `/audio/transcriptions`。
- 后续补课建议：学习音视频分离、采样率、单声道 WAV、临时文件清理和失败回滚。
- 面试表达：我把视频转写拆成“抽取真实音轨”和“调用真实 provider”两个步骤，并在未配置时提前拒绝，避免生成伪字幕或无意义派生文件。

### 知识点 4：视频时间戳 Citation
- 小白解释：视频引用不能只说“来自 lesson.mp4”，还要告诉用户在 00:30 到 00:45。
- 项目用法：视频 transcript chunk 的 locator 保存 `type=video`、`asset=original_video`、`start_ms` 和 `end_ms`，Qdrant payload 和 Chat citation 同步透传。
- 后续补课建议：学习 citation locator、播放器 seek、SRT/VTT 字幕、毫秒与时间码转换。
- 面试表达：我让视频证据链从数据库、向量 payload 到 RAG response 都保留时间戳，回答可以精确引用视频片段。

### 知识点 5：真实模式下的拒绝策略
- 小白解释：没有转写 key 时，可以保存视频和关键帧，但不能假装已经识别字幕。
- 项目用法：转写前调用 `_ensure_transcription_provider_configured()`；缺 key 直接抛 `TRANSCRIPTION_NOT_CONFIGURED`，并且测试确认不会写 extracted_audio。
- 后续补课建议：学习能力状态、配置诊断、事务回滚、错误码和长期知识库污染风险。
- 面试表达：我把“可上传管理”和“可真实转写”分开设计，缺少 provider 时明确拒绝，让真实模式不会产生伪字幕污染 RAG。

### 我应该重点理解什么
V3.5 的重点是视频不是“一个更大的音频文件”。它同时有容器元数据、画面帧、音轨、转写分段和引用定位。可靠的视频 RAG 要把这些数据层拆开保存，再用 SourceRevision、MediaAsset、VisualFrame、TranscriptSegment 和 MultimodalChunk 串成证据链。

### 下一步应该学什么
下一步可以学习字幕导出、播放器 seek 到引用时间、镜头切分、多关键帧检索和图像描述，把视频从“可转写”推进到“可理解画面内容”。

### 面试表达方式
AI Knowledge OS Pro V3.5 中，我实现了视频资料的真实接入和 RAG 引用闭环。系统支持 MP4/MOV 上传，使用 FFmpeg/ffprobe 读取真实时长、宽高和音轨，并保存原视频与关键帧资产。视频转写前先校验真实 provider，缺 key 返回 `TRANSCRIPTION_NOT_CONFIGURED`；配置后抽取 WAV 音轨调用转写服务，保存带时间戳的 TranscriptSegment 和 video_transcript chunk，再写入 Qdrant。Chat 引用会携带视频 start_ms/end_ms，前端详情页提供视频播放器、关键帧和转写时间轴。

### 本阶段验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：31 passed，10 warnings。
- `frontend typecheck`：通过。
- `frontend build`：通过。
- Alembic head 保持 `0005_v3_3_error_archive`，V3.5 复用已有多模态表。

<!-- learning:v3-6-unified-media-tasks-20260619 -->
## V3.6：统一多模态任务中心与来源学习资产

### 版本总结
V3.6 把 V3.5 已经能运行的视频、音频、图片处理能力收束到统一任务模型里。文档任务和媒体任务现在共用 `ingestion_jobs`、`job_events`、Redis/RQ dispatch 和任务中心；媒体任务通过 `source_id` 与 `target_type=media` 明确归属，支持排队、进度、失败、重试和取消。同时，Chat 引用补齐 `source_id/document_id`，前端可以从引用直接跳到文档 chunk 或媒体时间戳。学习系统新增 `learning_artifacts`，只从真实文档片段或多模态 chunk 生成知识点、卡片、练习题、笔记和面试表达，避免空媒体或未配置 provider 产生伪学习资料。

### 本版本新增功能
- 新增 Alembic `0006_v3_6_unified_media_tasks`。
- `ingestion_jobs.document_id` 改为可空，新增 `source_id` 与 `target_type`。
- 新增统一任务入口 `run_task_job`，兼容旧 `run_ingestion_job`。
- 新增媒体任务服务：图片 OCR、视觉描述、截图分析、图片全量分析、音频转写、视频转写、视频关键帧、关键帧 OCR、关键帧视觉描述和视频全流程。
- 视频关键帧支持多帧提取和去重；视觉描述走真实 provider，未配置时返回明确错误。
- 媒体详情页支持播放器 seek、转写片段高亮、关键帧时间线、任务中心链接、证据 chunk 选择和学习资料生成。
- CitationPanel 支持媒体引用跳转 `/media/sources/{source_id}?t=...&chunk=...`，文档引用跳转 `/documents/{document_id}?chunk=...`。
- 新增 `LearningArtifact` 模型、schema、service 和 `POST /api/learning/from-source`。
- 学习资料生成只使用真实 chunk 文本或已有视觉描述；没有真实文本时拒绝。

### 主要文件
- `backend/alembic/versions/0006_v3_6_unified_media_tasks.py`：统一任务字段和学习资产表迁移。
- `backend/app/models/ingestion_job.py`：媒体任务所需的 nullable document、source 和 target type。
- `backend/app/services/task_broker.py`：统一 `enqueue_task`。
- `backend/app/tasks/ingestion_tasks.py`：统一任务分发入口。
- `backend/app/services/media_task_service.py`：媒体任务状态机、事件、重试和取消。
- `backend/app/services/media_service.py`：多关键帧、视觉描述、关键帧 OCR 和状态刷新。
- `backend/app/services/learning_artifact_service.py`：从真实来源片段生成学习资产。
- `backend/app/services/rag_service.py`：RAG citation payload 补齐 source/document 标识。
- `frontend/app/media/sources/[id]/page.tsx`：媒体任务、播放器同步、关键帧和学习动作。
- `frontend/app/tasks/page.tsx`：文档/媒体任务筛选和结果跳转。
- `frontend/components/CitationPanel.tsx`：引用深链跳转。
- `backend/tests/test_v3_6_media_tasks.py`：媒体任务成功与未配置转写拒绝。
- `backend/tests/test_v3_6_learning_artifacts.py`：真实 chunk 学习资产生成与空媒体拒绝。

### 知识点 1：统一任务模型
- 小白解释：任务中心不应该只认识文档，也应该认识图片、音频、视频这种媒体来源。
- 项目用法：V3.6 用 `target_type` 区分 document/media，用 `source_id` 关联媒体任务，让统一任务中心能追踪所有长耗时处理。
- 补课建议：复习任务状态机、兼容迁移、nullable foreign key 和 worker dispatch。
- 面试表达：我把文档和媒体处理统一到一个可观察任务模型里，保留旧队列入口兼容性，同时让媒体任务具备进度、事件、失败码、重试和取消能力。

### 知识点 2：真实模式边界
- 小白解释：能上传媒体不代表能自动理解媒体；没有 provider key 时必须明确拒绝。
- 项目用法：OCR、视觉描述和转写都沿用 NOT_CONFIGURED 错误，不生成假 OCR、假字幕或假描述。
- 补课建议：复习 provider adapter、错误码设计和数据污染风险。
- 面试表达：我把真实能力和资料管理分开设计，缺少模型配置时任务会失败并给出明确错误，而不会把伪内容写进长期知识库。

### 知识点 3：媒体引用跳转
- 小白解释：一个引用应该能带用户回到证据现场，而不是只告诉用户来自哪个文件。
- 项目用法：RAG citation 现在携带 `source_id`、`document_id`、`start_ms`、`end_ms` 和 chunk id，前端可跳到媒体播放器时间点并高亮片段。
- 补课建议：复习 URL query、播放器 seek、chunk locator 和 citation schema。
- 面试表达：我把多模态引用从后端 payload 贯穿到前端路由，让视频和音频证据可以一键跳到具体时间戳。

### 知识点 4：学习资产来源审计
- 小白解释：学习卡片和笔记必须知道自己来自哪段资料，未来复盘才可信。
- 项目用法：`LearningArtifact` 保存 artifact type、source/document、chunk id 和 locator；服务只从真实 chunk 文本生成内容。
- 补课建议：复习审计表、来源追踪、确定性生成和学习系统数据建模。
- 面试表达：我把学习资料生成设计成可追溯的确定性流程，避免 LLM 幻觉或空媒体伪造学习内容。

### 我应该重点理解什么
V3.6 的重点不是再加一个媒体按钮，而是把图片、音频、视频的处理流程统一纳入“任务中心 + 证据引用 + 学习沉淀”这条主线。可靠的个人知识 OS 需要让处理过程可观察、让引用能回到证据、让学习资料有真实来源。

### 下一步建议
下一步可以补字幕导出、镜头级 scene segmentation、更细粒度 keyframe 检索和 provider 诊断页，同时继续坚持真实模式不造假。

### 面试表达方式
AI Knowledge OS Pro V3.6 中，我把多模态处理从分散的同步按钮升级为统一任务中心。文档和媒体任务共用 durable job/event 模型，媒体任务通过 `source_id` 和 `target_type=media` 关联来源；图片 OCR、截图分析、音频转写、视频关键帧、视频转写和视觉描述都可以排队、追踪、失败重试。RAG 引用补齐 source/document 标识，前端可以从引用跳到媒体时间戳或文档 chunk。学习系统新增从真实来源 chunk 生成知识点、卡片、练习题和笔记的能力，没有真实文本时拒绝生成，避免伪内容污染学习档案。

### 本阶段验证结果
- `python -m compileall backend/app backend/alembic`：通过。
- `pytest`：39 passed，19 warnings。
- `frontend typecheck`：通过。
- `frontend build`：通过。
- Alembic head：`0006_v3_6_unified_media_tasks`。

<!-- learning:v3-6-final-completion-audit-20260619 -->
## V3.6 最终收口审计补充

### 本次补充做了什么
- 修正文档上传不支持格式时仍显示 `V2.5 当前支持...` 的旧版本提示，避免 V3.6 演示时出现版本错配。
- 修正学习包确认后的阶段交付追加逻辑：V3.6 学习包会追加 V3.6 阶段确认记录，不再落回 V2.5 文案。
- 移除学习包服务里已被同名方法覆盖的旧 V2.5 草稿读取/兜底 helper，减少后续维护歧义。
- 新增测试锁定 V3.6 学习包确认记录的版本文案和幂等追加行为。
- 对历史乱码段采用追加说明方式保留原文，不回写、不覆盖旧学习档案。

### 本阶段验证结果
- `python -m compileall backend/app backend/alembic scripts`：通过。
- `pytest`：40 passed，18 warnings。
- `python -m alembic current`：`0006_v3_6_unified_media_tasks (head)`。
- `frontend typecheck`：通过。
- `frontend build`：通过。

<!-- learning:v3-6-github-portfolio-release-20260621 -->
## V3.6：GitHub 作品集发布收口

### 本次补充做了什么
- 统一后端、前端、OpenAPI、系统状态和发布工具的 `V3.6 / 3.6.0` 版本表达。
- 将 README 重构为完整作品集说明，补齐架构、RAG/多模态流程、启动、环境变量、测试、路线图和简历表达。
- 新增 GitHub Actions、Issue/PR 模板、SECURITY、CONTRIBUTING、LICENSE 和 release checklist。
- 使用独立 `showcase.db` 与合成资料生成 7 张可复现截图，不读取正式数据库或私人上传内容。
- 修复媒体任务响应模型：`document_id` 可空，并公开 `source_id`、`target_type`，消除合法媒体任务的 500 响应校验错误。
- 修复展示学习日志、问答引用和相关片段的 Schema 数据结构，并新增 API 路由级回归测试。
- 截图工具按页面等待真实数据，拒绝 `Failed to fetch` 和空白截图；视频截图展示多关键帧、时间戳和高亮转写。
- 学习包草稿基于 `ba4166f..9dca572` 的真实 Git 差异、79 条 API 路由、依赖变化和验证报告生成。
- 发布器改为优先打包 Git 跟踪文件，排除被忽略的嵌套仓库、代理元数据、数据库、上传、密钥、依赖和构建缓存。

### 我应该重点理解什么
一个可展示的 AI 项目不只是功能能运行，还要让版本、接口契约、演示数据、CI、文档和发布边界彼此一致。展示环境必须可复现且与真实用户数据隔离；发布器必须按仓库所有权打包，而不是盲目遍历工作区。

### 面试表达方式
我把 AI Knowledge OS Pro V3.6 收口成可运行、可测试、可讲解的 GitHub 作品。除了统一多模态任务、时间戳引用和来源学习资产，我还建立了真实 CI、UTF-8/版本检查、隔离展示数据、自动截图验证和基于 Git 跟踪文件的安全发布流程，并用 API 回归测试修复了媒体任务可空外键的响应契约问题。

### 最终验证
- backend compileall：通过。
- pytest：41 passed，18 warnings。
- 全新 SQLite 数据库 Alembic upgrade/current：`0006_v3_6_unified_media_tasks (head)`。
- frontend typecheck/build：通过，15 个 App Router 页面构建成功。
- UTF-8 与版本一致性检查：通过。
- release 检查：199 files，forbidden=0，missing=0。

<!-- learning:v3-7-github-showcase-demo-20260701 -->
## V3.7：GitHub 作品集化、一键演示与工程可信度强化

### 本次补充做了什么
- 将当前版本表面升级为 `V3.7 / 3.7.0`，保留 V1-V3.6 历史记录不覆盖。
- 新增 V3.7 开发前审计，记录分支、提交、远程、README、CI、规范文件、截图、Demo、敏感文件和验证基线。
- 重构 README 为 GitHub 作品集首页，补齐 Demo 路径、功能矩阵、架构/RAG/多模态/学习闭环流程、Docker Demo、限制和简历表达。
- 新增一键 Demo 准备脚本：`setup_demo.py`、`seed_demo_data.py`、`check_demo_ready.py`，使用隔离 synthetic demo 数据库。
- 新增 `check_secrets.py`、`check_repo_clean.py`，并增强 `release.py --dry-run` 输出风险项。
- 新增 `docs/architecture_diagram.md`、`docs/resume_pitch.md`、`docs/demo_script.md` 和 GitHub release checklist。
- 系统状态页新增能力可用性矩阵，区分可直接使用、需要本地服务、需要真实 Provider、Demo 可展示和尚未实现。
- CI 质量门增加 secret、repo-clean 和 release dry-run，不调用真实付费 API。

### 我应该重点理解什么
V3.7 的重点是工程可信度：一个 AI 项目要能被陌生人打开、理解、演示、验证和安全发布。Demo 数据必须隔离且标注，README 必须诚实表达 provider 边界，release 必须在打包前证明不会带入密钥、数据库、上传文件或缓存。

### 面试表达方式
AI Knowledge OS Pro V3.7 中，我把已有多模态 RAG 系统进一步作品集化：补齐 GitHub 首页、演示脚本、架构图、求职表达、一键 Demo seed、secret 检查、repo-clean 检查和 release dry-run。系统状态页也把能力按真实依赖分组，明确哪些零配置可用，哪些需要 Redis/Qdrant/Worker，哪些需要真实模型 provider，避免把 Demo 流程冒充真实 AI 能力。

### 本阶段验证结果
- `python -m compileall backend/app scripts`：通过。
- `python -m pytest`：44 passed，19 warnings。
- `frontend typecheck`：全局 `npm` 不在当前 PowerShell PATH；使用 bundled Node 执行项目本地 TypeScript CLI，通过。
- `frontend build`：全局 `npm` 不在当前 PowerShell PATH；使用 bundled Node 执行项目本地 Next.js CLI，通过，15 个 App Router 页面构建成功。
- `python scripts/check_encoding.py`：通过，204 个 UTF-8 文本文件。
- `python scripts/check_secrets.py`：通过，202 个 tracked text 文件 findings=0。
- `python scripts/check_repo_clean.py`：通过，forbidden tracked files=0。
- `python scripts/release.py --version V3.7 --dry-run`：通过，included_files=213，excluded_files=0，secrets/database/uploads/cache 均为 no。

<!-- learning:v3-8-portfolio-demo-docs-20260702 -->
## V3.8：GitHub 作品集 Demo 文档化与可重置演示流程

### 本次补充做了什么
- 将当前运行版本升级为 `V3.8 / 3.8.0`，同步后端配置、健康检查测试、前端 package、README badge、CI release artifact 命名和版本检查脚本。
- 新增 `docs/v4_0_long_run_predevelopment_audit.md`，在进入 V4.0 长期迭代前按 44 项真实审计当前仓库、文档、CI、测试、Demo、发布和能力缺口。
- 新增 quickstart、demo mode、local development、environment variables、deployment、Docker、release process、versioning、commit convention 和 document quality checklist 文档。
- 新增 RAG、multimodal、media、task queue、citation locator、citation flow 和 learning loop 流程文档。
- 新增 RAG evaluation、hybrid retrieval、code repository ingestion、portfolio system、interview system、observability 和 performance notes 设计文档，明确这些是 V4.0 目标，不冒充已实现。
- 新增 `docs/demo_storyboard.md` 和 `docs/interview_qa.md`，其中 interview QA 覆盖 30 个项目讲解问题。
- 新增 `scripts/reset_demo_data.py`，只允许重置 `backend/data/demo_showcase.db`，拒绝非 Demo 数据库路径。
- 泛化 `scripts/generate_learning_package.py`，支持 Markdown 输出，并减少旧 V3.6 固定文案残留。
- README 新增 Documentation Map，把 GitHub 访客最需要的启动、Demo、架构、流程、发布和路线图文档串起来。

### 我应该重点理解什么
V3.8 的重点不是新增模型能力，而是把项目变成“陌生人可运行、可验证、可讲解”的作品集。真正专业的 AI 项目需要同时交代：哪些功能已实现，哪些需要本地服务，哪些需要真实 provider，哪些只是 Demo 展示，哪些仍是计划。文档、版本号、Demo 数据、release 检查和学习包也都是工程边界的一部分。

### 面试表达方式
AI Knowledge OS Pro V3.8 中，我把已有多模态 RAG 项目进一步整理为可复现的 GitHub 作品集：统一版本号，补齐 quickstart、demo/real 边界、本地开发、部署、发布和面试问答文档；增加安全的 Demo reset 脚本；并用真实 diff 生成学习包。这个阶段强调工程可信度和讲解能力，而不是用假模型输出堆功能。

### 本阶段验证结果
- `python\python.exe -m compileall backend/app scripts`：通过。
- `python\python.exe -m pytest`：46 passed，22 warnings。
- frontend typecheck：使用 bundled Node + 项目本地 TypeScript CLI，通过。
- frontend build：使用 bundled Node + 项目本地 Next.js CLI，通过，15 个 App Router 页面构建成功。
- `python scripts/check_encoding.py`：通过，235 个 UTF-8 文本文件。
- `python scripts/check_secrets.py`：通过，233 个 tracked text 文件 findings=0。
- `python scripts/check_repo_clean.py`：通过，forbidden tracked files=0。
- `python scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `python scripts/release.py --version V3.8 --dry-run`：通过，included_files=244，未发现 secrets/database/uploads/cache。
- `python scripts/reset_demo_data.py`：通过，重建 isolated synthetic demo 数据库并通过 readiness check。

<!-- learning:v3-9-quality-gates-in-progress-20260702 -->
## V3.9 进行中：RAG Demo 评估与前端 Smoke 质量门

### 本次补充做了什么
- 新增 `scripts/evaluate_rag.py --demo`，验证 synthetic demo 数据里的 QA、grounded 状态、citation ids、related chunks、音视频时间戳引用、MultimodalChunk 和 CitationLocator。
- 新增 `scripts/check_frontend_smoke.py`，检查关键页面是否存在、AppShell 导航是否指向真实页面、前端页面是否出现明显 raw/debug 文案。
- 将 demo seed、demo readiness、RAG demo evaluation 和 frontend smoke 接入 GitHub Actions。
- 修复系统状态页和媒体详情页直接展示 `JSON.stringify` 元数据的问题，改为用户可读的摘要。
- 在系统状态页新增 Provider/服务配置向导，按 Redis/Worker、Qdrant、LLM、Embedding、OCR/Vision、Speech-to-Text 说明影响面、修复方式和可复制的占位环境变量。
- 在任务中心新增“恢复建议”，针对运行中、取消、中断、转写未配置、OCR/Vision 未配置、Embedding/Qdrant/索引问题给出下一步。
- 新增 V3.9 质量门测试：`test_v3_9_rag_evaluation.py` 和 `test_v3_9_frontend_smoke.py`。

### 我应该重点理解什么
V3.9 开始从“能展示”转向“可验证、可收口”。RAG 评估不能只看有没有回答，还要检查引用是否能对应证据；前端质量也不能只看 build 是否过，还要检查导航、关键页面和普通用户界面是否泄露 raw/debug 信息。

### 面试表达方式
在 V3.9 中，我开始把质量门前移：新增 demo RAG evaluation 来验证 seeded evidence 和 citation plumbing；新增 frontend smoke check 来保护关键页面和导航；同时清理系统/媒体页面的 raw JSON 展示，并给系统能力和任务失败补充可执行的恢复建议。

### 当前验证结果
- `python -m compileall backend/app scripts`：通过。
- `python -m pytest`：49 passed，22 warnings。
- `python -m pytest backend/tests/test_v3_9_frontend_smoke.py backend/tests/test_v3_9_rag_evaluation.py`：3 passed。
- `python scripts/evaluate_rag.py --demo --database-path backend/data/demo_showcase.db`：通过，1 条 QA、1 个时间戳引用、7 个 MultimodalChunk、7 个 CitationLocator。
- `python scripts/check_frontend_smoke.py`：通过，当前有 4 个导航复用 warning，留给 V4.0 IA 拆分。
- frontend typecheck/build：通过，15 个 App Router 页面。
- `python scripts/check_encoding.py`：通过，241 个 UTF-8 文本文件。
- `python scripts/check_secrets.py`：通过，239 个 tracked text 文件 findings=0。
- `python scripts/release.py --version V3.8 --dry-run`：通过，included_files=250，未发现 secrets/database/uploads/cache。

<!-- learning:v3-9-navigation-ia-split-20260702 -->
## V3.9 进行中：导航信息架构拆分与 Smoke 门禁升级

### 本次补充做了什么
- 将 AppShell 中复用同一路由的菜单拆成独立页面：`/chat/history`、`/learning/knowledge-points`、`/learning/quizzes`、`/learning/notes` 和 `/system/settings`。
- 新页面复用现有真实 API，分别展示会话记录、知识点、练习题、学习笔记和配置安全边界，不引入假模型输出。
- 将 `scripts/check_frontend_smoke.py` 的必检路由扩展到 19 个，并把重复导航目标从 warning 升级为 failure。
- 更新 `test_v3_9_frontend_smoke.py`，让后端测试固定检查新的路由数量和 `warnings=0`。

### 我应该重点理解什么
信息架构不是“菜单多一点”这么简单。对于作品集项目，导航每一项都应该指向真实、有边界说明、有空状态或错误恢复的页面；如果多个入口实际落到同一页，面试官会感觉功能还没收口。把这个规则写进 smoke gate，可以防止后续改 UI 时悄悄退化。

### 面试表达方式
在 V3.9 中，我把前端导航从展示型菜单进一步收口成可验证的信息架构：会话记录、知识点、练习、笔记和设置都有独立页面，并把“重复导航目标”升级为 CI 可检测的失败条件。这体现了我不只关注功能存在，也会用自动化质量门保护产品体验。

### 当前验证结果
- `python\python.exe -m compileall backend/app scripts`：通过。
- `python\python.exe -m pytest`：49 passed，21 warnings。
- `python\python.exe -m pytest backend/tests/test_v3_9_frontend_smoke.py`：1 passed。
- `python\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=19，nav_targets=16，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，20 个 build entries（含 `_not-found`）。
- `python\python.exe scripts/check_encoding.py`：通过，246 个 UTF-8 文本文件。
- `python\python.exe scripts/check_secrets.py`：通过，findings=0。
- `python\python.exe scripts/check_repo_clean.py`：通过。

<!-- learning:v4-0-learning-roadmap-relations-start-20260702 -->
## V4.0 起步：学习路线与轻量知识关系

### 本次补充做了什么
- 新增 `GET /api/learning/roadmap`，根据已有 KnowledgePoint、学习卡片、练习、笔记和版本学习包派生学习顺序。
- 新增 `GET /api/learning/knowledge-graph`，派生 `prerequisite`、`related`、`used_by_project`、`next_to_learn` 关系。
- 新增 `/learning/roadmap` 和 `/learning/knowledge-graph` 页面，并更新 AppShell 导航，保留 `/learning` 作为版本档案入口。
- 新增 `backend/tests/test_v4_0_learning_roadmap.py`，覆盖路线排序、关系类型和 API 响应契约。
- 更新 `docs/learning_system.md`，明确当前是派生关系视图，不是持久化图数据库，也不使用假 LLM 生成关系。

### 我应该重点理解什么
学习路线不是简单把知识点列出来，而是根据掌握状态决定下一步：不会/模糊/待复习优先，未开始其次，已掌握则练习面试表达。知识关系也必须有证据来源：同一版本包顺序、共享关键词、项目文件位置，而不是模型随口生成。

### 面试表达方式
V4.0 中我把学习系统从“知识点列表”推进到“路线和关系”：后端从现有学习资产派生学习顺序和知识关系，前端提供学习路线与知识关系页面。这个阶段先保证可解释和可验证，后续再加入持久化 KnowledgeRelation 和真实 LLM provider 生成个性化路线。

### 当前验证结果
- `python\python.exe -m pytest backend/tests/test_v4_0_learning_roadmap.py backend/tests/test_v3_9_frontend_smoke.py -q`：3 passed。
- `python\python.exe -m compileall backend/app scripts`：通过。
- `python\python.exe -m pytest`：58 passed，20 warnings。
- `python\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=27，nav_targets=24，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，28 个 build entries（含 `_not-found`）。
- `python\python.exe scripts/check_encoding.py`：通过，266 个 UTF-8 文本文件。
- `python\python.exe scripts/check_secrets.py`：通过，findings=0。
- `python\python.exe scripts/check_repo_clean.py`：通过。
- `python\python.exe scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `python\python.exe scripts/evaluate_rag.py --demo`：通过。
- `python\python.exe scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `python\python.exe scripts/evaluate_rag.py --demo`：通过。

<!-- learning:v4-0-hybrid-retrieval-start-20260702 -->
## V4.0 起步：轻量混合检索与 Rerank 降级边界

### 本次补充做了什么
- 新增 `backend/app/services/hybrid_retriever.py`，把 Qdrant dense 检索与 SQLite 中已索引文档/多模态片段的 keyword 检索做去重和分数融合。
- 新增 `backend/app/services/rerank_provider.py`，先提供明确 disabled provider 边界；未配置 rerank 时不生成假分数，只在 reason 中标记 `rerank_not_configured`。
- `RAGService` 改为通过 `HybridRetriever` 取候选片段，并在 `Citation`/`RelatedChunk` 中返回 `dense_score`、`keyword_score`、`rerank_score`、`final_score`、`retrieval_reason` 和 `citation_ready`。
- 新增 `backend/tests/test_v4_0_hybrid_retrieval.py`，覆盖 dense 漏召回时的 keyword fallback，以及 RAG 响应不伪造 rerank_score。
- 更新 `docs/hybrid_retrieval.md` 和 `docs/rag_evaluation.md`，把“planned”修正为当前真实实现状态和限制。

### 我应该重点理解什么
向量检索擅长语义相似，但容易漏掉精确术语、文件名、错误码和代码符号；关键词检索能补这些硬匹配，但不懂同义表达。混合检索的关键不是把两边结果简单拼起来，而是去重、融合分数、保留证据定位，并诚实标记 rerank 是否真的执行。没有真实 rerank provider 时，`rerank_score` 必须为空，不能编一个看起来专业的分数。

### 面试表达方式
V4.0 中我开始把 RAG 从单一路径向混合检索升级：dense retrieval 继续由 Qdrant 负责，keyword fallback 从 SQLite 中已索引的文档和多模态片段召回精确术语，HybridRetriever 对候选做去重、score fusion 和 trace 记录；rerank adapter 先保留真实 provider 边界，未配置时降级为 deterministic fusion，不伪造 rerank 分数。

### 当前验证结果
- `python\python.exe -m compileall backend/app scripts`：通过。
- `python\python.exe -m pytest`：53 passed，22 warnings。
- `python\python.exe -m pytest backend/tests/test_v3_audio_transcription.py::test_audio_upload_and_transcription_create_timestamped_rag_chunks backend/tests/test_v4_0_hybrid_retrieval.py -q`：3 passed。
- `python\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=24，nav_targets=21，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，25 个 build entries（含 `_not-found`）。
- `python\python.exe scripts/check_encoding.py`：通过，258 个 UTF-8 文本文件。
- `python\python.exe scripts/check_secrets.py`：通过，findings=0。
- `python\python.exe scripts/check_repo_clean.py`：通过。
- `python\python.exe scripts/evaluate_rag.py --demo`：通过。

<!-- learning:v4-0-code-repository-ingestion-start-20260702 -->
## V4.0 起步：代码仓库接入、文件行号 Locator 与代码问答证据

### 本次补充做了什么
- 新增 `backend/app/services/code_repository_service.py`，支持本地代码仓库路径扫描、安全跳过 `.env`、数据库、媒体、依赖目录、构建产物和缓存。
- 新增 `POST /api/code-repositories/ingest-local`、`GET /api/code-repositories` 和详情接口，复用 `Source`、`SourceRevision`、`MultimodalChunk`、`CitationLocator` 与 `IndexRevision`。
- 代码片段以 `source_type=code_repository`、`modality=code_file` 入库，并保存 `file_path`、`line_start`、`line_end`、`symbol_name` locator。
- RAG 引用结构补充代码 locator 字段，代码问答可以返回文件路径与行号。
- 新增 `/code` 前端页面和 AppShell 导航入口，上传中心也增加代码仓库流程卡。
- 作品集概览新增代码仓库指标，展示这块能力的真实进展。
- 新增 `backend/tests/test_v4_0_code_repository_ingestion.py`，覆盖敏感文件跳过、未配置 embedding 拒绝、API 响应契约和代码 RAG 引用。

### 我应该重点理解什么
代码仓库接入不是把整个项目目录塞进模型。安全扫描必须先排除 `.env`、数据库、媒体、依赖、构建和缓存；然后只读取白名单文本文件，按文件和行号切片，再把 locator 保存进 citation。这样后续问“这个接口在哪里”“这个模块怎么讲”时，答案可以指向真实文件行号，而不是泛泛解释。

### 面试表达方式
V4.0 中我开始实现代码仓库理解能力：系统可以读取本地仓库，按安全白名单扫描代码文件，生成带 `file_path`、`line_start`、`line_end` 和 `symbol_name` 的代码片段，并写入向量索引。缺少 Embedding provider 时返回 `EMBEDDING_NOT_CONFIGURED`，不会生成假向量或假代码解释。

### 当前验证结果
- `python\python.exe -m compileall backend/app scripts`：通过。
- `python\python.exe -m pytest`：56 passed，25 warnings。
- `python\python.exe -m pytest backend/tests/test_v4_0_code_repository_ingestion.py -q`：3 passed。
- `python\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=25，nav_targets=22，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，26 个 build entries（含 `_not-found`）。
- `python\python.exe scripts/check_encoding.py`：通过，263 个 UTF-8 文本文件。
- `python\python.exe scripts/check_secrets.py`：通过，findings=0。
- `python\python.exe scripts/check_repo_clean.py`：通过。
- `python\python.exe scripts/release.py --version V3.8 --dry-run`：通过，未发现 secrets/database/uploads/cache。

<!-- learning:v4-0-portfolio-summary-start-20260702 -->
## V4.0 起步：作品集概览 API 与求职页面

### 本次补充做了什么
- 新增 `GET /api/portfolio/summary`，从真实数据库聚合知识库、文档、多模态 Source、CitationLocator、任务、问答和学习资产计数。
- 新增 portfolio schema/service/route，并补充 `test_v4_0_portfolio_summary.py`，覆盖 service 聚合和 API 响应契约。
- 新增 `/portfolio`、`/portfolio/resume`、`/portfolio/interview`、`/portfolio/project-review` 页面，把真实项目事实组织成项目复盘、简历表达、面试讲解和演示路线。
- 新增 `/system/observability` 页面，整理 request_id、task_id、retrieval_trace_id 等后续可观测性字段边界。
- 更新 AppShell 作品集求职导航和 frontend smoke，必检路由扩展到 24 个，nav_targets=21，继续要求 warnings=0。

### 我应该重点理解什么
作品集系统不能一上来就“编简历”。更稳的第一步是把项目里真实存在的工程事实聚合出来：有多少资料、多少引用定位、多少任务、多少学习资产，哪些能力已实现，哪些仍需要 Provider。这样后续即使用 LLM 生成简历或面试回答，也能基于真实事实，而不是凭空包装。

### 面试表达方式
V4.0 起步阶段，我先实现了作品集概览 API：后端从数据库统计资料、任务、引用和学习资产，并返回能力证据、简历要点、面试讲解点和诚实边界；前端提供作品集、简历、面试和项目复盘页面。自动生成部分仍保留为后续真实 Provider 能力，未配置时不能生成假内容。

### 当前验证结果
- `python\python.exe -m compileall backend/app scripts`：通过。
- `python\python.exe -m pytest`：51 passed，22 warnings。
- `python\python.exe -m pytest backend/tests/test_v4_0_portfolio_summary.py backend/tests/test_v3_9_frontend_smoke.py`：3 passed。
- `python\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=24，nav_targets=21，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，25 个 build entries（含 `_not-found`）。
- `python\python.exe scripts/check_encoding.py`：通过，255 个 UTF-8 文本文件。
- `python\python.exe scripts/check_secrets.py`：通过，findings=0。
- `python\python.exe scripts/check_repo_clean.py`：通过。
- `python\python.exe scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `python\python.exe scripts/evaluate_rag.py --demo`：通过。
<!-- learning:v4-0-portfolio-ui-resilience-20260702 -->
## V4.0 起步：作品集页面的服务边界和烟雾校验
### 本次补充做了什么?
- 将 `/portfolio`、`/portfolio/resume`、`/portfolio/interview`、`/portfolio/project-review` 的真实摘要加载与可选 markdown 生成拆开，避免 LLM provider 未配置时整页失败。
- 根作品集页补入“真实项目概览”文案，满足 frontend smoke 对关键文本的校验。
- 继续保留真实模式边界：生成接口缺 provider 仍然返回明确 `NOT_CONFIGURED`，不伪造内容。
### 本阶段验证结果
- `python\python.exe -m pytest`：61 passed, 25 warnings。
- `python\python.exe scripts/check_frontend_smoke.py`：passed，required_routes=27，nav_targets=24，warnings=0。
- `<HOME>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe .\node_modules\typescript\bin\tsc --noEmit`：passed。
- `<HOME>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe .\node_modules\next\dist\bin\next build`：passed，28 个 App Router routes built successfully。

<!-- learning:v4-1-codebase-cleanup-architecture-consolidation-20260702 -->
## V4.1 进行中：全量代码体检、历史归档与架构收口

### 本次补充做了什么
- 新增 `scripts/audit_codebase.py`，生成 V4.1 predevelopment audit、代码资产清单、dead-code report 和 cleanup plan。
- 将 V2、V3、V4.0 历史报告移动到 `docs/archive/v2`、`docs/archive/v3`、`docs/archive/v4`，保留历史但降低 docs 根目录噪音。
- 修复 `docs/version_learning_package.md` 的可读性和历史草稿路径，保留 append-only 学习日志原文不覆盖。
- 新增后端、前端、模块边界、脚本参考、依赖审计、测试审计、配置审计、CI/release 审计和文档清理报告。
- 清理前端 `react-hooks/exhaustive-deps` suppression，使用 `useCallback` 收口页面加载函数。
- 继续保留真实模式边界：未配置 provider 时必须明确拒绝，不生成假 OCR、假转写、假回答或假学习材料。

### 我应该重点理解什么
V4.1 的重点不是堆新功能，而是把大项目变得可维护：先用资产清单识别代码和文档，再按风险归档、清理、验证。历史学习档案是资产，不是垃圾；真正能删的东西必须先证明没有入口、没有引用、没有测试依赖、没有文档依赖。

### 面试表达方式
在 V4.1 中，我把 AI Knowledge OS Pro 从持续迭代状态推进到工程治理状态：建立全仓代码资产清单，归档历史报告，补齐模块边界和脚本参考，清理前端 hooks 技术债，并用 compileall、pytest、typecheck、build、encoding、Alembic 等门禁验证。这个阶段体现的是长期项目维护能力，而不是单纯功能开发。

### 当前验证结果
- `python -m compileall backend/app scripts`：通过。
- `python -m pytest`：61 passed，8 warnings。
- frontend typecheck：通过。
- frontend production build：通过，28 个 App Router routes。
- Alembic 临时 SQLite upgrade/current：通过，`0006_v3_6_unified_media_tasks (head)`。
- `python scripts/check_encoding.py`：通过，282 个 UTF-8 文本文件；legacy append-only log 警告保留。
- `python scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `python scripts/check_frontend_smoke.py`：通过，required_routes=27，nav_targets=24，warnings=0。

<!-- learning:v4-1-final-reverification-20260703 -->
## V4.1 最终复验：代码体检、架构收口与发布门禁完成

### 本次追加做了什么
- 对 V4.1 已提交分支重新执行最终质量门禁，确认代码体检、历史报告归档、前端 hook 清理、架构文档、脚本审计和发布安全检查仍然成立。
- 用隔离 `.pytest_tmp` SQLite 数据库重新运行 Alembic `upgrade head` 和 `current`，不接触用户真实数据库。
- 记录本机环境边界：默认 Anaconda Python 缺少 FastAPI，项目兼容的 bundled Python 可完整通过后端测试；全局 npm 不在 PATH，前端使用 bundled Node 调用项目本地 TypeScript/Next.js CLI 通过。

### 最终复验结果
- `python -m compileall backend/app scripts`：通过。
- bundled Python `-m pytest`：61 passed，9 warnings。
- frontend typecheck：通过。
- frontend production build：通过，28 个 App Router routes。
- Alembic isolated SQLite upgrade/current：通过，`0006_v3_6_unified_media_tasks (head)`。
- `python scripts/check_encoding.py`：通过，284 个 UTF-8 文本文件，96 条不可逆 legacy 日志行保留 append-only。
- `python scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `python scripts/check_frontend_smoke.py`：通过，required_routes=27，nav_targets=24，warnings=0。
- `python scripts/evaluate_rag.py --demo`：通过。
- `python scripts/check_secrets.py`：通过，scanned=282，findings=0。
- `python scripts/check_repo_clean.py`：通过，forbidden tracked files=0。
- `python scripts/release.py --dry-run`：通过，release_dry_run_version=V3.8，included_files=293，未发现 secrets/database/uploads/cache。

### 面试表达
V4.1 体现的是长期项目治理能力：我不是继续堆新功能，而是先建立资产清单和僵尸代码判断标准，再做低风险清理、历史归档、模块边界文档和质量门禁复验。这个过程保留真实功能和历史学习档案，不伪造 provider 能力，也不把测试失败当作删除测试的理由。

<!-- learning:v4-2-full-regression-demo-release-readiness-20260703 -->
## V4.2：全链路回归、Demo 稳定与发布前准备

### 本次做了什么
- 将可见版本统一到 `V4.2 / 4.2.0`，同步后端配置、前端 package、README、CI release artifact 和版本检查脚本。
- 强化 synthetic demo seed：加入 document、image、audio、video、code_repository、grounded QA、insufficient_context refusal、任务中心三种状态和学习资产。
- 增强 `scripts/evaluate_rag.py`，验证 citation id、used citation、CitationLocator、音视频时间戳、代码文件行号 locator、多模态 locator JSON 和资料不足拒答。
- 新增 `scripts/check_full_regression.py`，把后端路由、前端页面、Demo 数据、任务状态、学习资产、RAG/locator 和 release-support 文档脚本纳入一条回归检查。
- 更新 README、Demo、RAG evaluation、release process、roadmap 和 scripts reference，让 V4.2 的能力和限制保持一致。

### 我应该重点理解什么
V4.2 的核心是“清理之后真的没坏”。V4.1 让项目结构更干净，V4.2 则用可运行脚本证明核心链路仍可演示、可测试、可发布。Demo 数据不是假功能，而是明确标注的合成证据；真实 provider 缺失时仍必须明确拒绝。

### 面试表达
在 V4.2 中，我把多模态 RAG 项目的发布准备做成了可执行质量门禁：一键 seed 合成 Demo 数据，检查文档/图片/音频/视频/代码仓库证据，验证 RAG 引用、拒答、任务中心状态、学习资产和前端关键页面，并将这些检查接入 CI 和 release dry-run。这个阶段体现的是工程回归、Demo 可信度和长期维护能力。

### 当前验证结果
- targeted regression tests：9 passed。
- Demo readiness：通过，包含 4 类 source、9 个 multimodal chunks、9 个 citation locators、2 条 QA。
- RAG demo evaluation：通过，包含 1 条 grounded answer、1 条 refusal、1 条 timestamp citation、2 个 code locators。
- Full regression：通过，67 checks。
- Full pytest：63 passed，13 warnings。
- Frontend typecheck/build：通过，28 个 App Router routes。
- Release dry-run：V4.2，302 files，无 secrets/database/uploads/cache。
- Release archive check：通过，files=302，forbidden=0，missing=0。
<!-- learning:v4-3-real-demo-ux-hardening-release-usability-20260704 -->
## V4.3: Repository governance, real demo UX hardening and release usability

### What changed
- Confirmed repository source state in V4.2.1: latest complete code was on `feature/v4.2-full-regression-demo-release-readiness`, `main` lagged by 15 commits, no `v4.2.0` tag existed, and PR-to-main remained the safest merge path.
- Added V4.2.1 governance docs for source audit, mainline diff, merge plan, release preparation and branch governance.
- Promoted current product version to `V4.3 / 4.3.0` across backend config, health/status responses, frontend package metadata, README and CI release artifact naming.
- Added `scripts/check_docs_links.py` for README/docs local links and Mermaid fence validation.
- Added `scripts/check_readme_assets.py` for README images, screenshot inventory and missing demo GIF safety.
- Added `scripts/check_all.py` with `--quick`, `--demo`, `--release` and `--full` modes.
- Added provider-boundary tests covering missing LLM, embedding, OCR, vision description, transcription and disabled rerank behavior.
- Added V4.3 API regression tests for health/status/list routes, Chat missing-provider refusal, source-based learning action and portfolio summary.
- Updated README, architecture, quickstart, release process, scripts reference, roadmap, demo showcase and release checklist for V4.3.
- Generated V4.3 reports and learning package draft from real Git diff, route scan, dependency changes and validation results.

### What to understand
V4.3 is not a new AI capability layer. It is the release usability layer: make the repository source of truth clear, make the README safe to trust, make demo data repeatable, make provider boundaries testable, and make the quality gates easy to rerun. A portfolio project is not credible just because features exist; it becomes credible when a stranger can open it, follow the docs, see what is real, run checks, and understand the release path.

### Interview expression
In V4.3, I turned AI Knowledge OS Pro from a feature-rich branch into a more release-ready GitHub portfolio artifact. I audited branch/source truth before changing code, added local docs and README asset gates, grouped verification into `check_all.py`, and locked real-mode provider boundaries with regression tests so missing keys refuse clearly instead of producing fake OCR, transcripts or answers.

### Verification so far
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: 70 passed, 9 warnings.
- Frontend typecheck/build: passed, 28 App Router routes.
- `check_docs_links`: passed, 88 files, 45 local links, 7 local images, 11 Mermaid blocks.
- `check_readme_assets`: passed, 7 local images, 6 external badge images, 7 screenshots found.
- Demo readiness/RAG/full regression on `.pytest_tmp/v4_3_demo_showcase.db`: passed.
- Alembic isolated SQLite upgrade/current: `0006_v3_6_unified_media_tasks (head)`.
- `check_secrets`: passed, scanned=296, findings=0.
- `check_repo_clean`: passed, forbidden tracked files=0.
- `release.py --version V4.3 --dry-run`: passed, 307 files, no secrets/databases/uploads/cache.

### Next review focus
Review Git PR/tag/release flow, README link hygiene, provider-boundary error codes, check orchestration, and the difference between static smoke tests and future live browser E2E.
<!-- learning:v4-3-final-release-archive-20260704 -->
### V4.3 final release archive addendum
- `python scripts/check_all.py --full`: passed.
- Final staged release dry-run: `included_files=321`, no secrets/databases/uploads/cache.
- `python scripts/release.py --version V4.3`: generated `releases/AI-Knowledge-OS-Pro-V4.3-20260704.zip`.
- `python scripts/check_release.py --version V4.3`: passed, `files=321`, `forbidden=0`, `missing=0`.
- Final SHA256: recorded in the local `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.

<!-- learning:v4-3-post-release-hardening-20260704 -->
### V4.3 post-release hardening addendum
- Closed the remaining V4.3 evidence gaps by adding dedicated README asset, UX error-state and V4.4 planning reports.
- Hardened `scripts/check_all.py` so each gate prints name, status, duration, next-step guidance and report path; added `--skip-frontend` as a backend/demo/release diagnostic mode.
- Added shared frontend UX primitives for demo mode, capability warnings, provider-missing errors, loading state, task status, task logs, source locator actions and learning action bars.
- Standardized required task/runtime labels: queued, running, completed, failed, cancelled, retrying, not_configured, demo and real now map to readable Chinese labels.
- Revalidated full quality gates after the hardening pass: compileall passed, pytest `70 passed, 10 warnings`, frontend typecheck/build passed, docs/assets checks passed, demo/RAG/full regression passed, release dry-run included 324 files.
- Regenerated the V4.3 release zip and verified `files=324`, `forbidden=0`, `missing=0`; SHA remains in the `.sha256` sidecar rather than inside tracked docs.

<!-- learning:v4-4-demo-e2e-observability-20260705 -->
## V4.4: Browser demo E2E contracts, citation jumps and runtime observability

### What changed
- Promoted the current visible version to `V4.4 / 4.4.0` across backend config, health/status tests, frontend package metadata, README, CI release artifact names and version checks.
- Added lightweight request observability: API request ids, an in-process recent request buffer, error-code headers, and system observability endpoints for recent requests, tasks, retrievals, providers and error categories.
- Replaced the static `/system/observability` page with a data-driven runtime page that avoids keys, raw private data and fake provider claims.
- Strengthened citation deep-link behavior for document, media and code locators through `CitationPanel`, `/code` query handling and backend contract tests.
- Added optional Playwright scaffolding for demo smoke, citation-jump and observability routes, plus `scripts/run_demo_e2e.py` for seeded local browser validation when Playwright is installed.
- Added `scripts/evaluate_providers.py` with dry-run, demo and real-if-configured modes for LLM, embedding, OCR, vision, transcription and rerank readiness.
- Extended `scripts/check_all.py` with `--observability`, `--provider-eval`, `--e2e` and V4.4 full-gate coverage.
- Updated README, architecture, quickstart, demo mode, demo showcase, citation locator, observability, RAG evaluation, release process, roadmap, planning, versioning and script docs.
- Generated V4.4 reports and a learning package draft from real working-tree changes.

### What to understand
V4.4 is an evidence layer, not a new fake AI layer. It proves more of the product surface through contracts and optional browser automation while keeping default CI free of API keys and browser assumptions. Missing providers still return explicit NOT_CONFIGURED-style results, and missing Playwright is reported as `PLAYWRIGHT_NOT_INSTALLED` rather than being presented as a browser pass.

### Interview expression
In V4.4, I added runtime observability and browser-demo validation infrastructure to a multimodal RAG portfolio project. I connected request ids, task state, retrieval traces, provider readiness and citation jump contracts into testable APIs and UI, while keeping CI honest: no paid keys required, no fake OCR/transcripts/answers, and optional browser E2E skips with a clear reason when the runtime is missing.

### Verification so far
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: 73 passed, 15 warnings before adding the compatibility `test_observability.py` wrapper.
- Alembic isolated SQLite upgrade/current: passed at `0006_v3_6_unified_media_tasks (head)`.
- Frontend typecheck: passed.
- Frontend production build: passed, 28 routes generated after adding a Suspense boundary for `/code`.
- Demo seed/readiness/RAG/full regression on `.pytest_tmp/v4_4_demo_showcase.db`: passed.
- `check_all --quick`: passed.
- `check_all --observability`: passed.
- `check_all --provider-eval`: passed.
- `check_all --e2e`: passed with optional browser execution skipped as `PLAYWRIGHT_NOT_INSTALLED`.
- `check_secrets`: passed, scanned=313, findings=0.
- `check_repo_clean`: passed, forbidden tracked files=0.
- `release.py --version V4.4 --dry-run`: passed, included_files=324, no secrets/databases/uploads/cache.

### Next review focus
Review how request ids flow through response envelopes, how retrieval traces are derived from persisted QA logs, how provider dry-run avoids external calls, how Playwright output is kept untracked, and how citation locators map to document, media and code routes.

<!-- learning:v4-4-final-full-gate-20260705 -->
### V4.4 final full-gate addendum
- Final `python scripts/check_all.py --full`: passed.
- Full pytest inside the final gate: `74 passed, 23 warnings`.
- V4.4 observability/citation contract gate: passed.
- Frontend typecheck/build: passed, 28 routes generated.
- Encoding/docs links/README assets/frontend smoke: passed.
- Provider dry-run: passed with explicit NOT_CONFIGURED-style states and no external calls.
- Optional demo browser E2E: skipped honestly with `PLAYWRIGHT_NOT_INSTALLED`.
- Demo seed/readiness/RAG/full regression: passed on `.pytest_tmp/v4_4_demo_showcase.db`.
- Secret scan, repo-clean and release dry-run: passed; release dry-run included 324 files with no secrets/databases/uploads/cache.

<!-- learning:v4-4-final-release-archive-20260705 -->
### V4.4 final release archive addendum
- After staging the new V4.4 files, `python scripts/check_secrets.py` passed with `scanned=335`, `findings=0`.
- `python scripts/check_repo_clean.py` passed with forbidden tracked files `0`.
- `python scripts/release.py --version V4.4 --dry-run` passed with `included_files=347` and no secrets/databases/uploads/cache.
- `python scripts/release.py --version V4.4` generated `releases/AI-Knowledge-OS-Pro-V4.4-20260705.zip`.
- `python scripts/check_release.py --version V4.4` passed with `files=347`, `forbidden=0`, `missing=0`.
- SHA256 is recorded in the local `.sha256` sidecar file, not embedded in this tracked log.

<!-- learning:v4-4-ci-provider-dry-run-hardening-20260705 -->
### V4.4 CI provider dry-run hardening addendum
- GitHub push CI showed the quality job ran `scripts/evaluate_providers.py --dry-run` before backend dependencies were installed.
- Fixed `evaluate_providers.py` so dry-run mode reads environment/default configuration without importing backend provider adapters or Pydantic.
- Verified default `python scripts/evaluate_providers.py --dry-run` passes without backend dependency installation.
- Reverified `.venv` modes: `--dry-run`, `--demo` and `--real-if-configured` all pass; missing keys still produce explicit NOT_CONFIGURED-style states without fake outputs.
- Re-ran `python scripts/check_all.py --full` after the CI hardening fix: passed, including backend pytest `74 passed, 22 warnings`, frontend build, demo/RAG/full regression and release dry-run.

<!-- learning:v4-4-pr-ci-source-branch-hardening-20260705 -->
### V4.4 PR CI source branch hardening addendum
- GitHub pull request CI for commit `530183a` failed only in the backend job because `PortfolioMarkdownResponse.source_branch` was empty under the PR detached checkout.
- Fixed `PortfolioService._git_branch()` to prefer `GITHUB_HEAD_REF` and `GITHUB_REF_NAME`, then fall back to local git branch detection and an explicit `detached-head` marker.
- Added a regression test for the GitHub Actions head-ref path so portfolio generation keeps source metadata in PR validation.
- Re-ran targeted portfolio tests: `6 passed`.
- Re-ran `python scripts/check_all.py --full`: passed, including backend pytest `75 passed, 22 warnings`, frontend typecheck/build, encoding, version, docs links, README assets, provider dry-run, demo readiness, RAG evaluation, full regression, secret scan, repo-clean and release dry-run.
- Optional browser E2E remains honestly skipped as `PLAYWRIGHT_NOT_INSTALLED`; no browser pass is claimed without the Playwright runtime.

<!-- learning:v4-5-live-demo-e2e-hardening-20260705 -->
## V4.5: Strict live demo E2E hardening

### What changed
- Promoted the visible version to `V4.5 / 4.5.0` across backend config, health/status tests, frontend package metadata, README, CI release artifact names and version checks.
- Added `@playwright/test`, `npm run test:e2e:strict`, strict runner behavior and a GitHub Actions `live-e2e` job that installs Chromium and uploads Playwright artifacts.
- Strengthened Playwright specs for demo smoke, document/image/audio/video/code citation jumps, seeded chat citations and runtime observability.
- Added stable frontend test locators and split the media transcript timeline into `TranscriptTimeline` for safer timestamp highlighting checks.
- Fixed `scripts/run_demo_e2e.py` CORS serialization for Pydantic list settings and pinned the temporary demo backend embedding/index values.
- Aligned showcase seed fingerprints with the real `DEMO_MODE=true` local embedding fingerprint.
- Added a demo-mode-only keyword fallback when Qdrant is unavailable, while real mode still raises the dependency error instead of fabricating retrieval.
- Updated architecture, citation locator, observability, RAG evaluation, release checklist, roadmap and V4.5 reports.

### What to understand
V4.5 turns the browser demo from a nice-to-have scaffold into executable evidence. The app seeds a labelled synthetic database, starts real FastAPI and Next.js processes, then drives Chromium through the portfolio pages, media timestamp citations, code locators, chat citations and observability panels. It still does not fake real provider output: demo answers are labelled demo mode, provider dry-run makes no external calls, and real mode keeps explicit NOT_CONFIGURED or dependency errors.

### Interview expression
In V4.5, I promoted a multimodal RAG portfolio demo into a strict live E2E quality gate. I wired seeded synthetic evidence, local demo providers, citation deep links, browser automation and GitHub Actions artifacts into one reproducible validation path, while preserving real-mode provider boundaries and release safety.

### Verification so far
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: `75 passed`, `22 warnings`.
- Alembic isolated SQLite upgrade/current: passed at `0006_v3_6_unified_media_tasks (head)`.
- Frontend typecheck: passed.
- Frontend production build: passed, 28 app routes generated.
- `python scripts/check_all.py --quick`: passed.
- `python scripts/check_all.py --demo`: passed on `.pytest_tmp/v4_5_demo_showcase.db`.
- `python scripts/check_all.py --provider-eval`: passed with dry-run NOT_CONFIGURED-style states and no external calls.
- `python scripts/check_all.py --observability`: passed, `3 passed`.
- `python scripts/run_demo_e2e.py --strict`: passed, `22 passed`.
- `python scripts/check_all.py --e2e`: passed, browser E2E `22 passed`.

### Next review focus
Review strict-vs-optional E2E semantics, why demo-mode keyword fallback is allowed only for synthetic demos, how citation locators map to route query parameters, and how CI artifacts make browser failures inspectable.

<!-- learning:v4-5-learning-package-draft-20260705 -->
### V4.5 learning package draft addendum
- Committed the implementation/docs evidence in `5b6e205` before generating the learning package.
- Generated `docs/v4_5_learning_package_draft.md` from the real `main..HEAD` diff, route scan, dependency changes and V4.5 verification reports.
- Added the learning package draft to README documentation navigation and V4.5 release archive required entries.
- The draft intentionally records no migration changes for V4.5; the release is an E2E/CI/observability hardening pass over the existing V3.6 schema.

<!-- learning:v4-5-final-release-archive-20260705 -->
### V4.5 final release archive addendum
- Final `python scripts/check_all.py --full`: passed, including backend pytest `75 passed`, frontend build, browser E2E `22 passed`, demo/RAG/full regression, secret scan, repo-clean and release dry-run.
- `python scripts/release.py --version V4.5` generated `releases/AI-Knowledge-OS-Pro-V4.5-20260705.zip`.
- `python scripts/check_release.py --version V4.5` passed with `files=355`, `forbidden=0`, `missing=0`.
- SHA256 is recorded in the local `.sha256` sidecar file, not embedded in this tracked log.

<!-- learning:v4-5-release-doc-hygiene-20260705 -->
### V4.5 release documentation hygiene addendum
- Added `codex/**` to GitHub Actions push branch filters so future Codex work branches run CI without needing a PR event first.
- Updated the local `docs/release_checklist.md` from stale V3.6 wording to the current `V4.5 / 4.5.0` release gate.
- Expanded `scripts/check_version.py` so current README, release process, versioning, local release checklist, GitHub release checklist and CI surfaces are checked together.
- Added `docs/v4_5_release_doc_hygiene_report.md` and required it in the V4.5 release archive check.
- Verification: `check_version` passed; `check_all --quick` passed; `compileall` passed; `pytest` passed with `75 passed, 23 warnings`; `check_all --release` passed.
- Staged release dry-run included `356` files and reported no secrets, databases, uploads or caches.
- No provider-backed capability was changed, and no fake OCR, fake transcription, fake LLM answer or fake provider result was added.

<!-- learning:v4-5-release-doc-hygiene-archive-20260705 -->
### V4.5 release documentation hygiene archive addendum
- `python scripts/release.py --version V4.5` generated `releases/AI-Knowledge-OS-Pro-V4.5-20260705.zip` after the release documentation hygiene append.
- `python scripts/check_release.py --version V4.5` passed with `files=356`, `forbidden=0`, `missing=0`.
- SHA256 is recorded in the local `.sha256` sidecar file and in the final delivery message, not embedded as a self-referential tracked value.

<!-- learning:v4-6-rag-eval-evidence-report-20260705 -->
## V4.6 preparation: RAG evaluation evidence report

### What changed
- Extended `scripts/evaluate_rag.py --demo` with `--output <path>` so demo RAG evaluation can write a JSON evidence report.
- The report records aggregate counts, citation source coverage, multimodal source coverage, locator-shape coverage and per-question traces for grounded and insufficient-context QA logs.
- Wired `scripts/check_all.py --demo` to write `.pytest_tmp/v4_5_rag_eval_report.json`.
- Updated RAG evaluation docs, scripts reference, roadmap and `docs/v4_6_rag_eval_report.md`.
- Added regression coverage in `backend/tests/test_v3_9_rag_evaluation.py`.

### What to understand
This does not turn demo data into a real model benchmark. It makes the demo release gate more explainable: a reviewer can see which seeded QA rows were grounded or refused, which evidence modalities were covered, and which locator shapes support citation jumps.

### Verification
- `python -m pytest backend/tests/test_v3_9_rag_evaluation.py`: `2 passed`.
- `python scripts/check_all.py --demo`: passed and wrote `.pytest_tmp/v4_5_rag_eval_report.json`.
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: `75 passed`, `23 warnings`.
- `python scripts/check_all.py --quick`: passed.
- `python scripts/check_all.py --release`: passed with staged release dry-run `included_files=357` and no secrets/databases/uploads/cache.

### Interview expression
In the V4.6 preparation step, I turned the demo RAG check from a pass/fail script into a small evidence report. It still avoids fake provider claims, but it gives reviewers a concrete trace of seeded questions, citation coverage, timestamp locators and refusal behavior.

<!-- learning:v4-6-rag-eval-full-gate-20260705 -->
### V4.6 RAG evaluation evidence full-gate addendum
- Final `python scripts/check_all.py --full`: passed.
- Backend pytest: `75 passed`, `22 warnings`.
- Frontend typecheck/build: passed; production build generated 28 routes.
- Browser demo E2E ran locally and passed with `22 passed`.
- Demo RAG evaluation wrote `.pytest_tmp/v4_5_rag_eval_report.json` and passed with locator shapes `code_file_line=2`, `image_region=1`, `media_timestamp=6`.
- Release dry-run passed with `included_files=357` and no secrets/databases/uploads/cache.

<!-- learning:v4-6-project-structure-learning-page-20260705 -->
### V4.6 project structure learning page

### What changed
- Added `/learning/project-structure` as an in-app explanation page for the product model, backend structure, frontend structure, RAG evidence flow, multimodal processing flow, quality gates and study path.
- Linked the page from the `学习成长` navigation group as `项目构造`.
- Added frontend smoke coverage for the new route and required text: `项目构造讲解`, `RAG 证据流`, `多模态处理流` and `release dry-run`.
- Added `docs/v4_6_project_structure_learning_page.md` and updated the V4.6 roadmap entry.

### What to understand
This is a learning and explanation layer, not a new provider-backed capability. It does not call LLM/OCR/transcription providers, does not invent runtime metrics, and does not alter database schema or existing RAG/media behavior.

### Review focus
Use this page as the first map when studying the project: understand how sources become chunks, how chunks become retrievable citations, how media processing enters the task center, and how release checks protect GitHub portfolio claims.

<!-- learning:v4-6-project-structure-learning-page-verification-20260705 -->
### V4.6 project structure learning page verification

- Frontend smoke passed with `required_routes=28`.
- Targeted frontend smoke pytest passed with `1 passed`.
- `python -m compileall backend/app scripts` passed.
- `python scripts/check_all.py --quick` passed.
- Frontend typecheck passed via local `tsc --noEmit`.
- Frontend production build passed and generated `/learning/project-structure`.
- Full backend pytest passed with `75 passed`, `16 warnings`.
- Release gate passed through `python scripts/check_all.py --release`.
- Existing V4.5 local release archive safety check passed with `files=357`, `forbidden=0`, `missing=0`.

<!-- learning:v4-6-quality-gate-json-report-20260705 -->
### V4.6 quality gate JSON report

### What changed
- Added `--json-report <path>` to `scripts/check_all.py`.
- The JSON report records mode, overall status, report path, gate count and each gate's status, duration, failure reason and next step.
- The report is written from the quality-gate `finally` path, so partial self-check evidence is preserved even when a gate fails.
- GitHub Actions now writes `.pytest_tmp/check_all_quick.json` during the quality job and uploads `.pytest_tmp/check_all_*.json` as `quality-gate-json`.
- Added `docs/v4_6_quality_gate_json_report.md` and updated `docs/scripts_reference.md`.

### Verification
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick.json`: passed and wrote `gate_count=6`.
- `python -m pytest backend/tests/test_v4_3_api_regression.py::test_v4_3_static_quality_gate_scripts_pass`: `1 passed`, `2 warnings`.

### What to understand
This turns quality gates from terminal-only evidence into reusable structured data. Future learning-package generation, CI artifacts and in-app self-check pages can read the same gate result shape without scraping logs.

<!-- learning:v4-6-quality-gate-markdown-summary-20260705 -->
### V4.6 quality gate Markdown summary

### What changed
- Added `scripts/summarize_quality_report.py` to convert `check_all.py --json-report` output into a Markdown self-check summary.
- The summary records source report, mode, status, gate counts, per-gate result rows and an optimization focus section.
- CI now writes `.pytest_tmp/check_all_quick_summary.md` after the quick JSON report and uploads it with the quality gate artifact.
- Added regression coverage in `backend/tests/test_v4_6_quality_report_summary.py`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_quality_report_summary.py`: `2 passed`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick.json`: passed.
- `python scripts/summarize_quality_report.py --input .pytest_tmp/check_all_quick.json --output .pytest_tmp/check_all_quick_summary.md`: passed.

### What to understand
This completes the first self-check evidence loop: command output becomes JSON, JSON becomes a readable summary, and both can be stored as CI artifacts for later learning-package or dashboard use.

<!-- learning:v4-6-quality-artifact-validation-20260705 -->
### V4.6 quality artifact validation

### What changed
- Added `scripts/check_quality_artifacts.py` to validate `check_all.py --json-report` output and its Markdown summary.
- The validator checks JSON mode/status, gate count, gate fields, durations, failed-gate policy and required Markdown summary sections.
- CI now validates `.pytest_tmp/check_all_quick.json` and `.pytest_tmp/check_all_quick_summary.md` before uploading them as artifacts.
- Added `backend/tests/test_v4_6_quality_artifacts.py` for passed, failed and malformed-count paths.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_quality_artifacts.py backend/tests/test_v4_6_quality_report_summary.py`: `5 passed`.
- Real quick self-check chain passed: `check_all --quick --json-report`, `summarize_quality_report.py`, then `check_quality_artifacts.py --require-passed`.

### What to understand
The self-check loop now verifies its own evidence artifacts. This prevents CI from uploading malformed quality reports and gives future automation a trustworthy input format.

<!-- learning:v4-6-run-self-check-entrypoint-20260705 -->
### V4.6 one-command self-check entrypoint

### What changed
- Added `scripts/run_self_check.py` as the preferred wrapper for the self-check evidence loop.
- The script runs `check_all.py --<mode> --json-report`, generates a Markdown summary and validates both artifacts with `check_quality_artifacts.py`.
- Supported modes are `quick` and `release`, keeping the entrypoint provider-free and safe for CI.
- GitHub Actions now calls `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp`.
- Added `backend/tests/test_v4_6_run_self_check.py`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_artifacts.py backend/tests/test_v4_6_quality_report_summary.py`: `7 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check`: passed.

### What to understand
This turns the self-check pipeline into a single command that a learner, maintainer or CI job can rerun without remembering the three underlying artifact commands.

<!-- learning:v4-6-quality-report-comparison-20260705 -->
### V4.6 quality report comparison

### What changed
- Added `scripts/compare_quality_reports.py` to compare two `check_all.py --json-report` files.
- The comparison detects status changes, missing gates, new gates and slower gates above a configurable threshold.
- Added optional `run_self_check.py --compare-to <baseline>` and `--fail-on-regression` support.
- Expanded CI artifact matching so future comparison Markdown files are uploaded with self-check artifacts.
- Added `backend/tests/test_v4_6_quality_report_comparison.py`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_quality_report_comparison.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_artifacts.py backend/tests/test_v4_6_quality_report_summary.py`: `10 passed`.
- Generated a quick baseline report, reran quick self-check with `--compare-to`, and comparison passed with `regression_count=0`.

### What to understand
The self-check system now has a continuous-improvement primitive: it can compare current evidence to a baseline and identify regressions before a release claim is made.

<!-- learning:v4-6-self-check-history-index-20260705 -->
### V4.6 self-check history index

### What changed
- Added `scripts/index_self_checks.py` to scan self-check artifact directories and generate JSON plus Markdown history indexes.
- The index records run count, passed/failed run counts, regression run count, latest run metadata and a run table.
- Added filtering for pytest `test_*` temporary folders so fixture reports do not pollute real self-check history.
- Added `backend/tests/test_v4_6_self_check_index.py`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_self_check_index.py`: `3 passed`.
- `python scripts/index_self_checks.py --input-dir .pytest_tmp --output .pytest_tmp/self_check_index.json --markdown-output .pytest_tmp/self_check_index.md`: passed and indexed the real quick self-check run.

### What to understand
The self-check evidence loop now has a history primitive. Instead of looking only at a single run, future automation can inspect a directory of self-check artifacts and understand whether recent runs passed, failed or regressed.

<!-- learning:v4-6-self-check-write-index-20260705 -->
### V4.6 self-check auto index refresh

### What changed
- Added `run_self_check.py --write-index`.
- The one-command self-check can now run the quality gate, summarize it, validate artifacts and refresh `self_check_index.json` plus `self_check_index.md`.
- CI now runs `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index`.
- CI artifact upload includes the generated self-check index files.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_index.py`: `8 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --write-index`: passed and wrote the history index.

### What to understand
This makes self-check history maintenance automatic. A maintainer no longer has to remember a separate indexing command after running the evidence loop.

<!-- learning:v4-6-self-check-improvement-plan-20260705 -->
### V4.6 self-check improvement plan

### What changed
- Added `scripts/plan_self_check_improvements.py`.
- The script reads `self_check_index.json` and optional comparison JSON to generate Markdown/JSON improvement actions.
- Added `run_self_check.py --write-plan`, which refreshes the improvement plan after the self-check artifacts and history index are generated.
- CI now runs `run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan` and uploads the generated improvement plan artifacts.
- Added `backend/tests/test_v4_6_self_check_improvement_plan.py`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_self_check_improvement_plan.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_index.py`: `12 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --write-index --write-plan`: passed and generated a self-check improvement plan.

### What to understand
The self-check loop now produces an action-oriented artifact. It can say whether to fix failed runs, review regressions, add a comparison baseline or broaden validation scope, based only on recorded evidence.

<!-- learning:v4-6-self-check-git-provenance-20260705 -->
### V4.6 self-check Git provenance

### What changed
- Added Git provenance to `scripts/check_all.py --json-report`: branch, full commit, short commit and dirty working-tree state.
- Updated `scripts/summarize_quality_report.py` so Markdown summaries show which branch and commit produced the quality evidence.
- Updated `scripts/index_self_checks.py` so self-check history tables can trace each run to `branch@commit`.
- Strengthened `scripts/check_quality_artifacts.py` so CI rejects malformed quality reports that are missing Git provenance.
- Updated tests and docs for the new report contract.

### Verification
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest backend/tests/test_v3_9_frontend_smoke.py backend/tests/test_v4_6_quality_report_summary.py backend/tests/test_v4_6_quality_artifacts.py backend/tests/test_v4_6_self_check_index.py backend/tests/test_v4_3_api_regression.py::test_v4_3_static_quality_gate_scripts_pass`: `11 passed, 2 warnings`.
- Bundled Node TypeScript check: passed.
- Bundled Node Next production build: passed and generated `/learning/project-structure`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --write-index --write-plan`: passed, with Git provenance rendered in the summary and history index.

### What to understand
This makes self-check artifacts easier to trust and explain. A quality report is no longer only a set of pass/fail rows; it now says exactly which branch and commit produced that evidence, while honestly showing whether the working tree still had uncommitted changes.

<!-- learning:v4-6-self-check-auto-compare-latest-20260705 -->
### V4.6 self-check automatic latest comparison

### What changed
- Added `scripts/run_self_check.py --compare-latest`.
- When a previous `check_all_<mode>.json` exists in the selected output directory, the wrapper copies it to `baseline_check_all_<mode>.json` before the new run overwrites the current report.
- The new report is then compared against that saved baseline using the existing quality-report comparison layer.
- If no previous report exists, the wrapper prints `auto_compare=skipped reason=no_previous_report` and continues without creating fake comparison evidence.
- `--write-plan` now receives the generated comparison JSON when auto comparison is available, so the improvement plan can distinguish compared runs from first runs.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_report_comparison.py backend/tests/test_v4_6_self_check_improvement_plan.py`: `15 passed`.

### What to understand
This closes the loop from "please compare against a baseline" to "the self-check command can reuse the previous local report automatically." It still preserves evidence honesty: the command compares only a real saved report, and it says when no baseline exists.

### Verification addendum
- First real `--compare-latest` run in `.pytest_tmp/self_check`: passed and printed `auto_compare=skipped reason=no_previous_report`, because no previous quick report was available before that run.
- Second real `--compare-latest` run in the same directory: passed, saved `baseline_check_all_quick.json`, generated comparison artifacts with `regression_count=0`, and changed the improvement plan recommendation to `Broaden validation scope`.

<!-- learning:v4-6-self-check-command-suggestions-20260705 -->
### V4.6 self-check command suggestions

### What changed
- Added a `command` field to each self-check improvement plan item.
- Markdown improvement plans now include a `Command` column.
- Empty-history plans suggest the one-command quick self-check with index and plan generation.
- Uncompared healthy runs suggest `--compare-latest`.
- Healthy compared runs suggest a release-mode self-check command.
- Human-inspection items keep the command blank instead of pretending remediation can be fully automated.
- Quality summaries now refer to the current report mode, so release reports say `release baseline` instead of reusing quick-mode wording.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_self_check_improvement_plan.py backend/tests/test_v4_6_run_self_check.py`: `14 passed`.
- `python -m pytest backend/tests/test_v4_6_quality_report_summary.py backend/tests/test_v4_6_self_check_improvement_plan.py backend/tests/test_v4_6_run_self_check.py`: `18 passed`.
- `python -m pytest backend/tests/test_v4_6_quality_report_summary.py backend/tests/test_v4_6_self_check_improvement_plan.py backend/tests/test_v4_6_run_self_check.py`: `19 passed` after making release-mode broaden-scope wording mode-aware.
- Real release-mode self-check with `--compare-latest --write-index --write-plan --fail-on-regression`: passed; the repeated run produced `regression_count=0` and suggested the full gate command.

### What to understand
This turns the improvement plan from a readable checklist into a more automation-friendly artifact. It still does not execute commands by itself; it records the next safe command when the next step is deterministic.

<!-- learning:v4-6-self-check-command-allowlist-20260705 -->
### V4.6 self-check command allowlist

### What changed
- Added `scripts/check_improvement_plan_commands.py`.
- The validator checks `self_check_improvement_plan.json` command suggestions against a narrow allowlist.
- Allowed commands are limited to deterministic quality workflows: `run_self_check.py` quick/release loops and `check_all.py --full --json-report`.
- Suggested artifact paths must stay under `.pytest_tmp`.
- Manual remediation items may keep an empty command.
- `run_self_check.py --write-plan` now runs this validator automatically after generating the JSON improvement plan.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_improvement_plan_commands.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_improvement_plan.py`: `20 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression`: passed and automatically ran `check_improvement_plan_commands.py`.

### What to understand
This protects the automation boundary. The project can now generate executable next-step hints without quietly expanding into arbitrary shell execution or non-quality commands.

<!-- learning:v4-6-self-check-next-command-summary-20260705 -->
### V4.6 self-check next command summary

### What changed
- Added `next_command_from_plan()` to `scripts/run_self_check.py`.
- When `--write-plan` produces a validated command suggestion, the final self-check summary now prints `next_command_priority`, `next_command_title` and `next_command`.
- Dry runs print `next_command=unavailable reason=dry_run` because no real plan JSON is generated.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `15 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression`: passed and printed `next_command_priority=P2`, `next_command_title=Add a comparison baseline` and the allowlisted `next_command`.

### What to understand
This makes the self-check loop easier to automate. A script or learner can read the final summary line instead of parsing Markdown tables to know the next safe quality command.

<!-- learning:v4-6-self-check-next-command-artifacts-20260705 -->
### V4.6 self-check next command artifacts

### What changed
- Added `self_check_next_command.json` and `self_check_next_command.md` outputs to `run_self_check.py --write-plan`.
- The JSON artifact records `status`, `source_plan`, `priority`, `title` and `command`.
- If no validated command exists, the artifact is still written with `status=none`.
- GitHub Actions now uploads the next-command artifacts with the self-check JSON/Markdown reports.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `17 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression`: passed and wrote `self_check_next_command.json` plus `self_check_next_command.md` with `status=available`.

### What to understand
This turns the next-command hint into durable evidence. Terminal output is convenient, but JSON/Markdown artifacts are easier for CI, future pages and learning packages to consume.

<!-- learning:v4-6-self-check-manifest-artifacts-20260705 -->
### V4.6 self-check manifest artifacts

### What changed
- Added `self_check_manifest.json` and `self_check_manifest.md` outputs to `run_self_check.py`.
- The manifest records mode, comparison state, artifact paths, artifact existence and next-command summary.
- GitHub Actions now uploads the manifest with the rest of the self-check evidence artifacts.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `18 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression`: passed and wrote `self_check_manifest.json` plus `self_check_manifest.md`.

### What to understand
This creates a small index of the self-check bundle itself. Instead of discovering artifact files by convention, future automation can read the manifest and know which evidence files exist.

<!-- learning:v4-6-self-check-manifest-validator-20260705 -->
### V4.6 self-check manifest validator

### What changed
- Added `scripts/check_self_check_manifest.py` as the self-check manifest validator.
- The validator checks artifact paths, artifact `exists` flags, required quality JSON/Markdown artifacts and `next_command.command` safety.
- `run_self_check.py` now validates `self_check_manifest.json` immediately after writing it.
- Added regression tests for valid manifests, unsafe artifact paths, existence mismatches and unsafe next commands.

### Verification
- `python -m compileall scripts`: pending in this local step.
- `python -m pytest backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: pending in this local step.
- Real quick self-check will be rerun after the validator tests pass.

### What to understand
The manifest is now evidence with its own guardrail. Future automation can rely on `self_check_manifest.json` only after the wrapper proves that the listed files are safe, real and internally consistent.

<!-- learning:v4-6-self-check-manifest-validator-verification-20260705 -->
### V4.6 self-check manifest validator verification

### What changed
- Confirmed the validator works both as a standalone script and inside `run_self_check.py`.
- Confirmed frontend typecheck and production build still pass after the V4.6 project-structure learning route and self-check docs updates.
- Confirmed the release gate and release package safety checks still pass under the existing V4.5 package naming strategy.

### Verification
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `22 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression`: passed and ran `check_self_check_manifest.py`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_manifest_validator_final.json`: passed.
- Frontend typecheck via bundled Node and `node_modules/typescript/bin/tsc --noEmit`: passed.
- Frontend production build via bundled Node and `node_modules/next/dist/bin/next build`: passed.
- `python scripts/check_all.py --release`: passed.
- `python scripts/check_release.py --version V4.5`: passed before the final documentation append; the release package is regenerated after this entry.

### What to understand
The self-check loop now produces a bundle, validates the bundle, summarizes the next safe command and preserves enough evidence for local learning or CI artifact review without touching user data or provider-backed flows.

<!-- learning:v4-6-next-self-check-runner-20260705 -->
### V4.6 next self-check runner

### What changed
- Added `scripts/run_next_self_check.py`.
- The runner reads `self_check_next_command.json`, validates the embedded command with the existing self-check allowlist, and prints whether the next command is ready.
- The runner does not execute by default. Execution requires explicit `--execute`.
- Execution uses tokenized subprocess calls and replaces the `python` token with the current interpreter instead of invoking a shell string.
- GitHub Actions now validates the generated next-command artifact after `run_self_check.py --write-plan`.

### Verification
- Targeted tests and quality gates are pending in this local step.

### What to understand
This is the handoff from self-check evidence to controlled automation. The project can now say, "Here is the next safe quality command, and here is a script that proves it is still safe before anyone runs it."

<!-- learning:v4-6-next-self-check-runner-verification-20260705 -->
### V4.6 next self-check runner verification

### What changed
- Verified the runner in validate-only mode and explicit execute mode.
- Used the root quick self-check artifact to execute a compare-latest quick self-check.
- Used the release self-check artifact to execute a compare-latest release self-check.
- Followed the generated full-gate recommendation through the runner and completed the full quality gate.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `26 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan`: passed and generated `self_check_next_command.json`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json`: passed with `result=ready`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --execute`: passed and produced quick comparison evidence with `regression_count=0`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --execute`: passed and produced release comparison evidence with `regression_count=0`.
- Full gate execution through the runner passed: backend compileall, `119 passed` backend tests, frontend typecheck/build, encoding/version/docs checks, provider dry-run, demo browser E2E `22 passed`, demo readiness, demo RAG evaluation, full regression and release dry-run.

### What to understand
The self-check loop can now move from quick evidence to comparison, then to release evidence, then to full validation through validated artifacts. It is still controlled automation: each command is allowlisted and explicit execution is required.

<!-- learning:v4-6-next-self-check-json-report-20260705 -->
### V4.6 next self-check JSON report

### What changed
- Added `--json-output` to `scripts/run_next_self_check.py`.
- The runner now writes a machine-readable readiness report with schema version, status, result, priority, title, command, source artifact path and failure text.
- JSON output paths are restricted to `.pytest_tmp` so the runner cannot become a broad file-writing tool.
- GitHub Actions now uploads `.pytest_tmp/next_self_check.json` with the self-check evidence bundle.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `25 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan`: passed.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json`: passed with `result=ready`.

### What to understand
The next-command handoff is no longer terminal-only. CI, future dashboards and learning views can consume a small JSON contract that says whether the next self-check command is safe and ready.

<!-- learning:v4-6-bounded-self-check-loop-20260705 -->
### V4.6 bounded self-check loop

### What changed
- Added `scripts/run_self_check_loop.py`.
- The loop starts with `run_self_check.py`, reads generated next-command artifacts, and validates each next step through `run_next_self_check.py`.
- The loop has an explicit `--max-steps` bound.
- By default it validates readiness only; next commands execute only with `--execute-next`.
- CI runs the loop in dry-run mode and uploads `.pytest_tmp/self_check_loop.json`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check_loop.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_run_self_check.py`: `27 passed`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --json-output .pytest_tmp/self_check_loop.json`: passed and reported one ready next step.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_ci --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop_dry_run.json`: passed and wrote a planned loop report.

### What to understand
The automation chain now has a bounded controller. It can connect self-check output to the next recommended command while keeping execution opt-in, step-limited and restricted to the existing self-check allowlist.

<!-- learning:v4-6-self-check-loop-report-validator-20260705 -->
### V4.6 self-check loop report validator

### What changed
- Added `scripts/check_self_check_loop_report.py`.
- The validator checks loop report schema, mode, status, `.pytest_tmp` paths, step counts, readiness artifact existence and allowlisted commands.
- `run_self_check_loop.py` now validates the loop report after writing it.
- GitHub Actions also runs the loop report validator on `.pytest_tmp/self_check_loop.json`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_self_check_loop_report.py backend/tests/test_v4_6_run_self_check_loop.py`: `12 passed`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_ci --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop.json`: passed and reported `self_check_loop_report=checked`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --json-output .pytest_tmp/self_check_loop_real.json`: passed and validated a report with one ready next step.

### What to understand
The bounded loop now has its own evidence guardrail. The project can generate a self-check loop report and immediately prove that its paths, commands and step accounting are internally consistent.

<!-- learning:v4-6-self-check-loop-markdown-report-20260705 -->
### V4.6 self-check loop Markdown report

### What changed
- Added `--markdown-output` to `scripts/run_self_check_loop.py`.
- The loop now writes a human-readable Markdown report beside the JSON loop report.
- The Markdown report includes status, mode, output directory, max steps, execution flags, initial command and inspected next-command steps.
- The loop report validator now checks optional `markdown_output` paths and confirms the Markdown artifact exists.
- GitHub Actions uploads `.pytest_tmp/self_check_loop.md` with the self-check evidence bundle.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_self_check_loop_report.py backend/tests/test_v4_6_run_self_check_loop.py`: `13 passed`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop.json --markdown-output .pytest_tmp/self_check_loop.md`: passed and reported `self_check_loop_report=checked`.

### What to understand
The loop evidence is now useful to both machines and learners. JSON keeps CI automation stable; Markdown gives a quick explanation of the planned or executed self-check chain.

<!-- learning:v4-6-next-self-check-markdown-report-20260705 -->
### V4.6 next self-check Markdown report

### What changed
- Added `--markdown-output` to `scripts/run_next_self_check.py`.
- The next-command readiness check now writes a human-readable Markdown report beside the JSON report.
- The Markdown report includes status, result, priority, title, source artifact and the validated command.
- GitHub Actions uploads `.pytest_tmp/next_self_check.md` with the self-check evidence bundle.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_run_self_check_loop.py`: `16 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan`: passed.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json --markdown-output .pytest_tmp/next_self_check.md`: passed and wrote a Markdown readiness report with `result=ready`.

### What to understand
The next self-check handoff is now readable without opening JSON. This is useful for CI artifacts, learning review and quick release triage while preserving the explicit `--execute` boundary.

<!-- learning:v4-6-next-self-check-report-validator-20260705 -->
### V4.6 next self-check report validator

### What changed
- Added `scripts/check_next_self_check_report.py`.
- The validator checks next-command readiness report schema, status/result consistency, `.pytest_tmp` paths, optional Markdown artifact existence and allowlisted commands.
- `run_next_self_check.py` now validates `next_self_check.json` immediately after writing it.
- GitHub Actions also validates `.pytest_tmp/next_self_check.json`.

### Verification
- `python -m compileall scripts`: passed.
- `python -m pytest backend/tests/test_v4_6_next_self_check_report.py backend/tests/test_v4_6_run_next_self_check.py`: `15 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan`: passed.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json --markdown-output .pytest_tmp/next_self_check.md`: passed and reported `next_self_check_report=checked`.

### What to understand
The next-command readiness artifact now has its own guardrail. The project does not merely generate a "next command"; it proves the report is internally consistent before CI or a learner trusts it.

<!-- learning:v4-6-self-check-loop-step-markdown-20260705 -->
### V4.6 self-check loop step Markdown evidence

### What changed
- `scripts/run_self_check_loop.py` now passes `--markdown-output` to every `run_next_self_check.py` step.
- Each real loop step writes `next_self_check_step_N.json` and `next_self_check_step_N.md`.
- Loop JSON records `readiness_markdown` beside `readiness_json`.
- Loop Markdown summaries include the per-step readiness Markdown path.
- `scripts/check_self_check_loop_report.py` validates per-step readiness Markdown paths when present.

### Verification
- `python -m pytest backend/tests/test_v4_6_run_self_check_loop.py backend/tests/test_v4_6_self_check_loop_report.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_next_self_check_report.py`: `29 passed`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_step_markdown --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop_step_markdown.json --markdown-output .pytest_tmp/self_check_loop_step_markdown.md`: passed.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_step_markdown_real --max-steps 1 --json-output .pytest_tmp/self_check_loop_step_markdown_real.json --markdown-output .pytest_tmp/self_check_loop_step_markdown_real.md`: passed and generated `next_self_check_step_1.md`.

### What to understand
The bounded loop now keeps machine evidence and learner-readable evidence paired at every handoff. A future CI artifact or learning page can open the loop report, then jump from each step to the exact readiness explanation without parsing raw JSON.

<!-- learning:v4-6-ci-artifact-contract-check-20260705 -->
### V4.6 CI artifact contract check

### What changed
- Added `scripts/check_ci_artifacts.py`.
- The script validates that GitHub Actions runs the self-check, next-command readiness and loop report validators.
- It also validates that the `quality-gate-json` artifact uploads JSON, Markdown, manifest, next-command and loop step readiness files.
- `check_all.py --quick` now includes a `CI artifacts` gate, so quick JSON evidence now has seven gates.
- CI runs `python scripts/check_ci_artifacts.py` before publishing quality artifacts.

### Verification
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=5`, `required_artifact_paths=16`, `failures=0`.
- Release-mode self-check comparison passed with `regression_count=0` before this implementation pass.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_3_api_regression.py::test_v4_3_static_quality_gate_scripts_pass backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_artifacts.py`: `22 passed`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_ci_artifacts.json`: passed with the new `CI artifacts` gate.
- `python scripts/check_all.py --release`: passed with release dry-run including `386` files.
- `python scripts/check_release.py --version V4.5`: passed with `files=386`, `forbidden=0`, `missing=0`, SHA256 `2bb83ae843f4663a95aec443086620f452e9171bd9b013fada086ccc30e71e4b`.

### What to understand
This closes another evidence gap: the project now checks not only that self-check files can be produced, but that CI is configured to preserve them for review. Automation that disappears after a CI run is much less useful than automation with durable artifacts.

<!-- learning:v4-6-full-self-check-mode-20260705 -->
### V4.6 full self-check mode

### What changed
- `scripts/run_self_check.py` now supports `--mode full`.
- Full quality gates can now produce the same artifact bundle as quick/release: JSON report, Markdown summary, artifact validation, optional comparison, history index, improvement plan, next-command artifacts and manifest.
- `plan_self_check_improvements.py` now recommends `run_self_check.py --mode full` after a healthy release baseline instead of a bare `check_all.py --full --json-report`.
- `check_improvement_plan_commands.py`, `run_self_check_loop.py` and `check_self_check_loop_report.py` now accept full self-check mode.

### Verification
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_improvement_plan.py backend/tests/test_v4_6_improvement_plan_commands.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_next_self_check_report.py backend/tests/test_v4_6_run_self_check_loop.py backend/tests/test_v4_6_self_check_loop_report.py`: `55 passed`.
- `python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan --dry-run`: passed and planned the full artifact bundle.
- Release self-check comparison passed with `regression_count=0` and recommended `python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --json-output .pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output .pytest_tmp/self_check_release/next_self_check_full_ready.md`: passed with `result=ready`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_full_self_check_mode.json`: passed.
- `python scripts/check_all.py --release`: passed.
- `python scripts/check_release.py --version V4.5`: passed with `files=386`, `forbidden=0`, `missing=0`, SHA256 `f4c329ba189677ec06107e1d8979472697c92b0ea0563d9a1aaeccfae7238378`.

### What to understand
Full validation is no longer a side path. It can now travel through the same self-check evidence machinery as quick and release validation, which makes heavy final checks easier to archive, compare and explain.

<!-- learning:v4-6-ci-release-full-handoff-evidence-20260705 -->
### V4.6 CI release-to-full handoff evidence

### What changed
- GitHub Actions now runs a release self-check baseline, then a release `--compare-latest` self-check with regression failure enabled.
- CI writes `next_self_check_full_ready.json` and `next_self_check_full_ready.md` from the release self-check next-command artifact.
- `scripts/check_ci_artifacts.py` now requires the release-to-full handoff commands and upload paths.
- CI artifact coverage now includes release self-check JSON, Markdown, index, improvement plan, next-command, manifest and full-ready handoff files.

### Verification
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_next_self_check_report.py`: `20 passed`.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=9`, `required_artifact_paths=28`, `failures=0`.
- `python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --write-index --write-plan`: passed.
- `python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --compare-latest --write-index --write-plan --fail-on-regression`: passed with `regression_count=0`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --json-output .pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output .pytest_tmp/self_check_release/next_self_check_full_ready.md`: passed with `result=ready`.
- `python scripts/check_next_self_check_report.py --report-json .pytest_tmp/self_check_release/next_self_check_full_ready.json`: passed.

### What to understand
The CI evidence chain now proves that a healthy release baseline can hand off to the full self-check command. It still does not execute heavy full validation automatically on every push; it preserves a readable, validated next step for release review.

<!-- learning:v4-6-github-actions-status-diagnostic-20260705 -->
### V4.6 GitHub Actions status diagnostic

### What changed
- Added `scripts/check_github_actions.py`.
- The script can query GitHub Actions for the current branch and commit, or evaluate a saved Actions API JSON response offline.
- It writes optional JSON and Markdown reports under `.pytest_tmp`.
- It supports `--require-success` for explicit release checks, while the default mode reports `unavailable` without failing when remote access or permission is missing.
- It reads `GH_TOKEN` or `GITHUB_TOKEN` when present and never prints token values.

### Verification
- `python -m pytest backend/tests/test_v4_6_github_actions_status.py`: `7 passed`.
- `python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status.json --markdown-output .pytest_tmp/github_actions_status.md`: completed with `result=unavailable`, `failure=github_api_http_404`.

### What to understand
Remote CI status is a different evidence layer from local quality gates. This diagnostic makes that layer visible and auditable without making local development depend on network access or GitHub authentication.

<!-- learning:v4-6-ci-github-actions-status-artifact-20260705 -->
### V4.6 CI GitHub Actions status artifact

### What changed
- GitHub Actions now grants `actions: read` alongside `contents: read`.
- The quality-and-release job runs `scripts/check_github_actions.py` with `GITHUB_TOKEN: ${{ github.token }}`.
- CI uploads `.pytest_tmp/github_actions_status.json` and `.pytest_tmp/github_actions_status.md` with the `quality-gate-json` artifact.
- `scripts/check_ci_artifacts.py` now verifies the diagnostic command, upload paths, Actions read permission and token environment binding.

### Verification
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=10`, `required_artifact_paths=30`, `required_workflow_snippets=2`.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_6_github_actions_status.py`: `15 passed`.

### What to understand
Remote CI status is now preserved as part of the CI evidence bundle. The diagnostic still does not use `--require-success` in the default workflow, so network or permission issues become readable evidence instead of silently blocking local-quality automation.

<!-- learning:v4-6-github-actions-report-validator-20260705 -->
### V4.6 GitHub Actions report validator

### What changed
- Added `scripts/check_github_actions_report.py`.
- The validator checks GitHub Actions status JSON schema, result/status/conclusion consistency, owner/repo shape, Actions run URL shape, branch/head branch agreement, unavailable failure text and optional Markdown content.
- `scripts/check_github_actions.py` now automatically validates reports after writing JSON/Markdown output.
- CI explicitly runs the validator after generating `.pytest_tmp/github_actions_status.json` and `.pytest_tmp/github_actions_status.md`.
- `scripts/check_ci_artifacts.py` now requires the explicit validator step.

### Verification
- `python -m pytest backend/tests/test_v4_6_github_actions_report.py backend/tests/test_v4_6_github_actions_status.py backend/tests/test_v4_6_ci_artifacts.py`: `22 passed`.
- `python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status_validator.json --markdown-output .pytest_tmp/github_actions_status_validator.md`: completed with `result=unavailable` and `github_actions_report=checked`.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=11`, `required_artifact_paths=30`, `required_workflow_snippets=2`.

### What to understand
Generating evidence is not enough; the project now validates the remote CI status evidence before CI uploads it. This keeps unavailable/failed/pending/passed remote states machine-readable without pretending a malformed report is trustworthy.

<!-- learning:v4-6-ci-artifact-ordering-20260705 -->
### V4.6 CI artifact ordering checks

### What changed
- `scripts/check_ci_artifacts.py` now validates required command ordering, not only command/path presence.
- It checks quick self-check generation before next-command validation, loop generation before loop report validation, release comparison before full-ready handoff, GitHub Actions status generation before status report validation, and status report validation before the `quality-gate-json` upload.
- Added regression tests for reversed GitHub Actions status generation/validation, reversed release-to-full handoff order, and uploading quality artifacts before status report validation.

### Verification
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py`: `12 passed`.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=11`, `required_artifact_paths=30`, `required_workflow_snippets=2`, `required_ordered_groups=5`.

### What to understand
A CI command merely existing in YAML is weaker than a verified evidence sequence. The workflow now proves that evidence is produced before it is validated and validated before it is uploaded.

<!-- learning:v4-6-ci-artifact-contract-report-20260705 -->
### V4.6 CI artifact contract report

### What changed
- `scripts/check_ci_artifacts.py` now supports `--json-output` and `--markdown-output`.
- The report records schema version, pass/fail result, workflow path, required command count, artifact path count, workflow snippet count, ordered group count and failure details.
- GitHub Actions writes `.pytest_tmp/ci_artifacts_contract.json` and `.pytest_tmp/ci_artifacts_contract.md`.
- The `quality-gate-json` upload now includes the CI artifact contract report itself.

### Verification
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py`: `16 passed`.
- `python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract_local.json --markdown-output .pytest_tmp/ci_artifacts_contract_local.md`: passed with `required_commands=12`, `required_artifact_paths=32`, `required_workflow_snippets=2`, `required_ordered_groups=6`.

### What to understand
The CI artifact bundle now includes the evidence that checked the bundle contract. That makes the CI artifact policy auditable after a run instead of only visible in terminal output.

<!-- learning:v4-6-ci-artifact-contract-report-validator-20260705 -->
### V4.6 CI artifact contract report validator

### What changed
- Added `scripts/check_ci_artifacts_report.py`.
- The validator checks CI artifact contract JSON schema, pass/fail consistency, safe workflow path shape, required count fields, failure count alignment and optional Markdown content.
- `scripts/check_ci_artifacts.py` now validates its own JSON/Markdown outputs immediately after writing them.
- GitHub Actions now runs the report validator explicitly before uploading `quality-gate-json`.
- CI artifact contract tests now cover the validator command and upload ordering.

### Verification
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_6_ci_artifacts_report.py`: `25 passed`.
- `python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract_local_validator.json --markdown-output .pytest_tmp/ci_artifacts_contract_local_validator.md`: passed with `required_commands=13`, `required_artifact_paths=32`, `required_workflow_snippets=2`, `required_ordered_groups=6` and `ci_artifacts_report=checked`.

### What to understand
The workflow contract now has a second guardrail: the project validates the report that validates the artifact bundle. This is useful when you learn CI/CD because it separates three ideas: producing evidence, checking evidence structure, and uploading evidence for later review.

<!-- learning:v4-6-full-self-check-manifest-validator-20260705 -->
### V4.6 full self-check manifest validator alignment

### What changed
- `scripts/run_self_check.py` already supported `quick`, `release` and `full` modes, but `scripts/check_self_check_manifest.py` still only accepted `quick` and `release`.
- Updated the manifest validator to accept `full` mode.
- Added a regression test that validates a full self-check manifest with a safe full comparison next command.
- Updated the script reference and quality-gate documentation so the supported modes match the code.

### Verification
- `python -m pytest backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `25 passed`.
- `python scripts/check_self_check_manifest.py --manifest-json .pytest_tmp/self_check_full/self_check_manifest.json`: passed.

### What to understand
This is a small but important consistency fix. When one module adds a new mode, every validator and report reader that interprets that mode must be updated too; otherwise the main work can pass while the evidence pipeline fails at the end.

<!-- learning:v4-6-self-check-baseline-resilience-20260705 -->
### V4.6 self-check baseline resilience

### What changed
- Full self-check comparison exposed that the auto baseline file could disappear before `compare_quality_reports.py` ran.
- `scripts/run_self_check.py` now stores `--compare-latest` baselines in an isolated system temporary directory keyed by the output path instead of inside the active self-check output directory.
- Added a regression test proving the baseline survives even if the self-check output directory is removed during a run.

### Verification
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_improvement_plan_commands.py`: `36 passed`.
- `python -m compileall scripts/run_self_check.py`: passed.

### What to understand
Comparison baselines are inputs, not normal run outputs. Keeping them outside the directory being regenerated makes the evidence loop less brittle, especially for full gates that exercise demo servers, browsers and temporary databases.

<!-- learning:v4-6-quality-comparison-duplicate-gates-20260705 -->
### V4.6 quality comparison duplicate gate preservation

### What changed
- Full quality reports run `E2E scaffolding` twice: once in quick checks and once before optional demo browser E2E.
- `scripts/compare_quality_reports.py` previously keyed gates only by name, so duplicate names were collapsed in comparison evidence.
- The comparison layer now preserves repeated gate occurrences with stable labels such as `E2E scaffolding #2`.
- Added regression tests for missing and failed duplicate gate occurrences.

### Verification
- `python -m pytest backend/tests/test_v4_6_quality_report_comparison.py backend/tests/test_v4_6_run_self_check.py`: `21 passed`.
- `python scripts/compare_quality_reports.py --base <full-baseline> --current <same-full-baseline> --json-output .pytest_tmp/check_all_full_duplicate_gate_comparison.json --output .pytest_tmp/check_all_full_duplicate_gate_comparison.md --fail-on-regression`: passed with `Base gates: 22`, `Current gates: 22`, `Regression count: 0`.

### What to understand
Report comparisons should preserve the evidence shape of the source report. If a report intentionally contains repeated gate names, the comparison tool must distinguish occurrences instead of silently merging them.

<!-- learning:v4-7-interaction-visual-cleanup-20260705 -->
### V4.7 interaction performance and visual cleanup

### What changed
- Unified current version surfaces to `V4.7 / 4.7.0`.
- Reduced AppShell main navigation from 25 entries to 17 core workflow entries.
- Added `PendingButton`, `ActionToast`, `SkeletonCard`, `LoadingOverlay`, `AsyncActionBoundary`, `SectionTabs`, `ProgressivePanel` and API timeout handling.
- Redesigned Dashboard into a visual command center with capability bars, task distribution, next actions and recent evidence.
- Redesigned `/learning/project-structure` into a visual learning map with module relations, RAG evidence flow, multimodal flow, user-action-to-code mapping and interview mode.
- Added `scripts/check_frontend_interactions.py`, `scripts/check_ui_performance_budget.py` and `scripts/check_interaction_feedback.py`.
- Documented script/test sprawl instead of deleting active self-check evidence tooling blindly.

### Verification
- `python scripts/check_ui_performance_budget.py`: passed with `main_nav_targets=17`.
- `python scripts/check_frontend_interactions.py`: passed with `high_risk=0`.
- `python scripts/check_interaction_feedback.py`: passed with `high_risk=0`.
- `python -m pytest backend/tests/test_v3_9_frontend_smoke.py backend/tests/test_v4_7_ui_quality_gates.py`: `3 passed`.
- Frontend typecheck: passed.
- `python scripts/check_version.py`: passed for `V4.7 / 4.7.0`.

### What to understand
Performance is not only backend speed. A product feels faster when the next action is obvious, buttons respond immediately, repeated clicks are blocked during async work, and long requests fail with a clear message. V4.7 adds these guardrails without pretending to improve provider latency or fabricating runtime metrics.

<!-- learning:v4-7-final-validation-20260705 -->
### V4.7 final validation and release packaging evidence

### What changed
- Re-ran the V4.7 interaction inventory after final edits; it reported `buttons=79` and `high_risk=0`.
- Tightened `scripts/check_version.py` so AppShell brand and the GitHub bug template are included in version consistency checks.
- Updated the GitHub bug report template placeholder from `V3.8 / 3.8.0` to `V4.7 / 4.7.0`.
- Replaced the short V4.7 learning-package draft with 18 beginner-friendly knowledge points covering interaction feedback, duplicate-click protection, API timeouts, skeleton states, Dashboard redesign, visual project-structure learning, RAG evidence flow, multimodal flow, navigation governance, quality budgets, script/test sprawl governance, version consistency, release safety and real-mode boundaries.
- Replaced placeholder final-report text with real local gate evidence.

### Verification
- `python scripts/check_version.py`: passed for `V4.7 / 4.7.0`.
- `python scripts/check_frontend_interactions.py`: passed with `buttons=79` and `high_risk=0`.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_7.json`: passed.
- Full gate evidence included backend pytest `190 passed, 15 warnings`, frontend production build, browser demo E2E `22 passed`, provider dry-run, demo RAG evaluation, full regression, secret scan, repo clean and release dry-run with `included_files=413`.

### What to understand
The final V4.7 pass shows why release evidence must be generated after feature and documentation changes are in the Git index. The release dry-run uses tracked files, so staging the new docs, scripts and tests before the full gate makes packaging evidence match the intended release surface.

<!-- learning:v4-8-runtime-performance-release-polish-20260705 -->
### V4.8 runtime performance and release polish

### What changed
- Unified current version surfaces to `V4.8 / 4.8.0`.
- Added backend runtime performance observability with `/api/system/performance`, `/recent`, `/slow` and `/summary`.
- Added frontend GET request TTL cache, in-flight request dedupe, force refresh support and mutation cache clearing.
- Added `/system/performance` with backend request summaries, browser cache metrics, slow-path distribution and recent button action timing.
- Added `scripts/check_request_cache.py` and V4.8 regression tests for performance routes, request-cache wiring and no-Git release safety.
- Updated release safety scripts so extracted source trees without `.git` use filesystem mode instead of crashing.
- Moved low-frequency self-check and CI diagnostic implementations to `scripts/maintenance/` while keeping root-level compatibility wrappers.

### Verification
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: `194 passed, 17 warnings`.
- Frontend typecheck with bundled Node: passed.
- Frontend production build with bundled Node: passed and included `/system/performance`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_v4_8.json`: passed with 10 quick gates.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_8.json`: passed with 25 gates.
- Browser demo E2E inside the full gate: `22 passed`.
- `python scripts/release.py --version V4.8 --dry-run`: passed with secrets, databases, uploads and caches all reported as absent.

### What to understand
V4.8 is about making performance and release quality observable instead of guessed. The important design idea is that frontend perceived speed, backend request timing, cache behavior and release packaging are all product surfaces. They should have visible UI, tests and honest boundaries, not only terminal scripts.

<!-- learning:v4-8-final-release-20260705 -->
### V4.8 final release packaging evidence

### What changed
- Generated the final V4.8 source release archive after staging V4.8 code, tests and docs.
- Verified the archive includes required V4.8 performance/request-cache files and excludes forbidden runtime artifacts.

### Verification
- `python scripts/release.py --version V4.8`: generated `releases/AI-Knowledge-OS-Pro-V4.8-20260705.zip`.
- `python scripts/check_release.py --version V4.8`: passed with `files=449`, `forbidden=0`, `missing=0`.
- SHA256: `81cdccb28ff0574fe5e21c511dc4761ea3280b43eadbf99c829d006802c43ddb`.

### What to understand
For this project, a release zip is not just a convenience file. It is a tested artifact with exclusion rules for secrets, databases, uploads, logs, build output and caches. The `.sha256` file is the compact proof that the exact archive can be verified later.

<!-- learning:v4-8-release-digest-correction-20260705 -->
### V4.8 release digest correction

The previous V4.8 release packaging entry recorded the digest for the archive generated before this append-only note was added. Because embedding a digest inside files that are themselves packaged changes the archive content, the final authoritative digest is the `.sha256` file next to the regenerated archive, not an inline value inside versioned docs.

<!-- learning:v4-8-final-audit-no-git-validation-20260705 -->
### V4.8 final audit and no-Git validation

### What changed
- Added V4.8 predevelopment, interaction-runtime and medium-risk interaction cleanup reports.
- Regenerated `docs/v4_8_button_latency_map.md` with `buttons=79` and `high_risk=0`.
- Expanded `docs/v4_8_learning_package_draft.md` from 5 topics to 15 teachable knowledge points covering runtime observability, slow-request analysis, request dedupe, lightweight cache, cache invalidation, button timing, slow-action notices, no-Git release mode and technical-debt governance.
- Updated `docs/quickstart.md` and `docs/local_development.md` to describe V4.8 routes, request-cache checks, `.pytest_tmp/v4_8_demo_showcase.db`, `/system/performance`, V4.8 release dry-run and extracted no-Git validation.
- Updated `scripts/check_release.py` so the V4.8 release archive must include the new audit and interaction reports.

### Verification
- `python scripts/check_frontend_interactions.py`: passed with `buttons=79`, `high_risk=0`.
- `python scripts/check_interaction_feedback.py`: passed with `high_risk=0`.
- `python scripts/check_request_cache.py`: passed with `ttl_methods=6`.
- `python scripts/check_encoding.py`: passed for UTF-8 text files.
- `python scripts/check_docs_links.py`: passed.
- `python scripts/check_version.py`: passed for `V4.8 / 4.8.0`.
- `python scripts/check_ui_performance_budget.py`: passed with `main_nav_targets=18`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_v4_8_final.json`: passed.
- Extracted no-Git release tree checks passed:
  - `python scripts/check_version.py`
  - `python scripts/check_secrets.py` with `mode=filesystem reason=no_git_metadata`
  - `python scripts/check_repo_clean.py` with `mode=filesystem reason=no_git_metadata`
  - `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_no_git_v4_8.json`

### What to understand
The final V4.8 pass separates three kinds of evidence: runtime evidence inside the product, static quality gates in the repository and release-user evidence from an extracted zip without Git metadata. The `.sha256` file next to the regenerated archive is the authoritative digest because putting a digest inside packaged docs would make it stale as soon as the docs change.

<!-- learning:v4-8-final-local-revalidation-20260705 -->
### V4.8 final local revalidation

### What changed
- Re-ran backend compile, the full pytest suite, frontend typecheck, frontend production build and Alembic migration checks after the final documentation and release-check updates.
- Diagnosed a transient Windows file-lock issue from stale local demo child processes holding `.pytest_tmp/local_demo_logs` open.
- Stopped the stale local demo backend/frontend child processes, confirmed the generated log directory was gone, and reran the full backend suite.

### Verification
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: passed with `194 passed, 23 warnings` after clearing the stale demo log lock.
- Frontend typecheck with local `tsc.cmd --noEmit` and the bundled Node path: passed.
- Frontend production build with local `next.cmd build` and the bundled Node path: passed; `/system/performance` is included in the route list.
- Isolated Alembic check using `.pytest_tmp/v4_8_alembic_check.db`: `upgrade head` and `current` passed with `0006_v3_6_unified_media_tasks (head)`.

### What to understand
The first pytest failure was not a regression in app behavior. It was a Windows file-handle problem caused by a still-running local demo process. The useful lesson is to distinguish environment locks from code failures, fix the environment honestly, and rerun the same gate instead of treating a partial pass as success.

<!-- learning:v4-8-page-load-metrics-20260705 -->
### V4.8 page-load and route-switch metrics

### What changed
- Added `frontend/services/page-metrics.ts` to record browser-side page timing.
- AppShell now records the initial browser navigation timing and main-navigation route-switch duration.
- `/system/performance` now includes a “页面加载与切换” panel beside backend request timing, request-cache metrics and button timing.
- `scripts/check_release.py` now requires `frontend/services/page-metrics.ts` in V4.8 release archives.

### Verification
- Frontend typecheck and production build were rerun after this change.
- `python scripts/check_release.py --version V4.8` was rerun after regenerating the release archive.

### What to understand
Backend request timing alone cannot prove that a page feels fast. V4.8 now separates API latency, browser cache behavior, button action duration and page navigation timing, so future optimization can identify whether slowness comes from the backend, repeated reads, UI interaction or page transition work.

<!-- learning:v4-8-page-metrics-release-recheck-20260705 -->
### V4.8 page metrics release recheck

### What changed
- Regenerated the V4.8 release archive after staging `frontend/services/page-metrics.ts`.
- Verified that the release package now includes 454 source files and still excludes forbidden runtime artifacts.
- Re-ran extracted no-Git quick validation after the page metrics addition.

### Verification
- `python scripts/check_release.py --version V4.8`: passed with `files=454`, `forbidden=0`, `missing=0`.
- Extracted no-Git checks passed: version, filesystem-mode secret scan, filesystem-mode repo clean and `check_all.py --quick`.

### What to understand
When release packaging uses tracked files, new source files must be staged before generating the archive. Otherwise a local build can pass while the release zip silently misses the new capability.

<!-- learning:v4-8-interface-system-refinement-20260806 -->
### V4.8 interface system refinement

### What changed
- Studied Hallmark as an MIT-licensed design reference and translated its useful principles into the existing product shell rather than copying its site or assets.
- Added `frontend/DESIGN.md` to lock the project interface language: calm knowledge-workspace hierarchy, semantic color roles, restrained surfaces, responsive behavior, and honest runtime states.
- Refined AppShell navigation with explicit group expansion state, accessible mobile open/close controls, and clearer breadcrumbs.
- Rebalanced Dashboard hierarchy around the next action, core counts, system readiness, task state, and evidence. Primary, informational, warning, and review signals now have distinct semantic color roles.

### Verification
- Frontend TypeScript typecheck passed after the interface changes.
- Production build passed and generated all 30 application routes.
- Desktop Dashboard loaded showcase data correctly during visual review.
- A 375px layout check found no horizontal overflow. The mobile drawer overlap found during review was corrected by removing the open control while the drawer is active.

### What to understand
Visual polish in an operational product is not a marketing reskin. It should make the next decision easier to spot, preserve trustworthy system states, and reduce cognitive noise without changing the underlying RAG, media, or provider behavior.

<!-- learning:v4-8-local-preview-api-proxy-20260806 -->
### V4.8 local preview API proxy

### What changed
- Added an optional Next.js rewrite from `/api-proxy/*` to a server-only `API_PROXY_TARGET`.
- Documented the paired local-preview configuration: `NEXT_PUBLIC_API_BASE_URL=/api-proxy` and `API_PROXY_TARGET=http://127.0.0.1:8000`.

### What to understand
Browser-visible environment variables are compiled into frontend code. A same-origin proxy keeps the API target server-side and can accommodate preview environments that block direct access to a separate local port. It is a transport adjustment only: it does not fabricate provider output or change any backend behavior.

<!-- learning:v4-8-ingestion-readiness-guidance-20260806 -->
### V4.8 ingestion readiness and duplicate guidance

### What changed
- Fixed the showcase seed so every document marked `ready/indexed` has persisted `chunks` rows; the seeded document count is now verified against the real database rows.
- RAG now considers a document retrievable only when the document has persisted chunks, preventing stale metadata from being presented as usable knowledge.
- Duplicate upload errors now retain the existing document id, processing state, latest task id and an explicit next action. The upload UI uses that information to open the original document or reprocess it.
- When Redis/RQ cannot accept a task, the file remains visible as a failed document with an actionable task error instead of appearing to vanish before the next duplicate upload attempt.

### What to understand
An uploaded file and a searchable source are different lifecycle states. A reliable RAG product must expose the transition from saved file, to queued task, to chunks, to index, rather than treating a successful byte upload as evidence that an answer can be grounded in that file.

<!-- learning:v5-evidence-agent-20260815 -->
### V5 Evidence Agent: from answer generation to evidence work

### What changed
- Reframed 溯知 around a canonical EvidenceIndex and a durable Evidence Agent instead of treating RAG as one search-then-answer function.
- Unified document, media and code evidence under immutable source/revision/index/chunk identity with manifest-first vector writes, atomic activation and reconciliation.
- Added persisted runs, plans, requirements, tool/model journals, Evidence Ledger, budgets, clarification/approval gates, cancellation fences and claim-level Artifacts.
- Rebuilt the primary product flow as Workbench, Library, Agent Runs and Artifacts, with source locators and bidirectional provenance.
- Added a fixed 60-case deterministic pipeline evaluation and a machine gate that validates dataset/report provenance, safety, recovery and honest Provider labels.

### Verification
- The pre-final full backend regression passed with `302 passed, 13 warnings`; post-review Agent runtime suites passed with `63 passed` and adjacent API/security/recovery suites with `10 passed`.
- Migration/CLI verification passed with `9 passed`; direct `0008→0006→0008` round-trip preserved the V4.9 semantic digest and failed closed for an invalid downgrade journal.
- Frontend lint, typecheck, 35-test unit checkpoint, 34-route build, V5 Playwright `4/4`, selected citation `2/2`, production Artifact locator `1/1` and production dependency audit with 0 vulnerabilities were observed before the final full rerun.
- Deterministic evaluation passed 60/60 cases, reported fusion Recall@10 `1.0`, citation/immutable identity `1.0`, unauthorized action rate `0.0`, recovery `6/6`, and multi-hop Agent `100%` versus a labeled V4.9-style proxy `41.67%`.

### What to understand
The central engineering upgrade is not that an LLM loops more times. A credible evidence agent needs a durable evidence identity, a recoverable external-side-effect protocol, an explicit state machine, controlled tools, hard budgets, human checkpoints and an Artifact whose factual claims can be replayed against immutable evidence. Evaluation provenance is part of the product: deterministic synthetic scores are useful regression evidence, but they are not a real-model benchmark or a historical-release rerun.

### Honest boundaries
- Production reranking is not configured; the rerank evaluation arm is a labeled recording adapter.
- The Runner does not yet execute the registered neighbor/open-evidence tools, and backend SSE reset/heartbeat remains incomplete.
- Historical Alembic metadata drift from 0001–0006 and live legacy Qdrant payload remediation are separate operational debt.
- Public GitHub visibility, default branch, push/merge and release publication are repository-owner actions and are not claimed by the local branch.

<!-- learning:v5-final-regression-and-sse-20260815 -->
### V5 final regression, SSE recovery and release-source boundary

### What changed
- Completed server-side no-cursor/stale/future cursor reset, cursor-neutral heartbeat and refresh-time reconstruction of public Ledger/interaction state.
- Added the real optional HTTP rerank adapter while keeping default and deterministic-report reranking explicitly unconfigured.
- Removed shared-counter recording ids in favor of concurrency-safe UUIDs.
- Exercised the canonical sparse fallback during a real Qdrant `502`; the degraded live flow retained an immutable citation.

### Verification
- Backend full suite: `328 passed`.
- Backend SSE runtime/API selection: `20 passed`.
- Frontend lint and typecheck: passed.
- Frontend unit suite: `12 files / 49 tests passed`; focused runtime/SSE/controller selection: `3 files / 12 tests passed`.
- Next `15.5.23` production build: passed with 34 routes.
- Strict live E2E: `26/26 passed`.
- Production dependency audit: 0 vulnerabilities.
- Migration round-trip/single head, quick gate, 60/60 evaluator and acceptance gate: passed.

### What to understand
An SSE heartbeat is transport liveness, not a domain fact: persisting it would consume cursors and pollute replay. A safe stream keeps heartbeats cursor-neutral, resets invalid cursors from a complete public projection and excludes private journal events. The live Qdrant failure also demonstrated why a degraded retrieval path must preserve the same evidence identity instead of fabricating dense-search success.

### Release note
The source-release check currently fails for the correct reason: packaging uses `git ls-files`, and the new V5 files are not committed yet. The safe next step is to commit the reviewed source set, rebuild the archive, and rerun the unchanged release checker—not to weaken the tracked-source rule.

<!-- learning:v5-agent-closure-20260821 -->
### V5 Agent closure: reading context is not the same as citing it

### What changed
- Added first-class immutable chunk and bounded neighbor queries to EvidenceIndex.
- Made AgentRunner execute search, exact open and same-revision neighbor reads as separate budgeted, checkpointed ToolCalls.
- Added `contextual` and `excluded` Ledger outcomes: adjacent context is visible but cannot support a claim until selected; unselected candidates keep an explicit reason.
- Added a title-only `modify` approval command. A content-bound proposal digest rotates after modification, so an old approval cannot authorize changed content.
- Fixed Recording Demo restoration to replay its durable journal and rebuild the visible plan/Ledger after navigation or refresh.

### Verification
- Focused backend closure suite: `93 passed`; final full backend regression: `444 passed, 1 skipped in 150.71s`, including the three-tool recovery matrix.
- Frontend lint/typecheck passed; `17 files / 76 tests` and the 34-route production build passed.
- Recording projection and production excluded-relation Playwright selection: `2/2 passed`.
- The strict all-browser rerun was not presented as passing because the process lacked `NEXT_PUBLIC_API_BASE_URL`; backend-dependent legacy scenarios failed or timed out while 21/31 cases passed.

### What to understand
Retrieval relevance, surrounding context and factual support are three different states. A trustworthy Agent must preserve those distinctions in durable data. Approval has the same requirement: if the proposed Artifact changes, approval authority must bind to the new exact content rather than to a vague user intention.

<!-- learning:v5-1-integration-20260826 -->
### V5.1 integration: merge product capability before release naming

### What changed
- Integrated the Agent intelligence, product-experience, and Runtime/E2E branches on one clean integration branch.
- Added continuation lineage, explicit tool-selection policy, conservative conflict handling, and confidence calibration.
- Reworked the core product surface into a warmer, Chinese-first research workflow while preserving immutable evidence details.
- Added a Docker-gated isolated runtime manifest for frontend/backend/Redis/Qdrant/worker resources and ownership-safe cleanup.
- Normalized evaluator and dataset text digests across LF/CRLF checkouts instead of treating platform line endings as tampering.

### Verification
- Backend full regression: `455 passed, 1 skipped`.
- Frontend: lint/typecheck passed, `18 files / 80 tests`, 34-route build.
- V5.1 product Playwright: `7/7 passed`; Runtime focused regression: `33 passed`.
- Deterministic 60-case evaluation and acceptance gate passed.

### What to understand
Integration and release are different stages. A feature can be correctly merged and fully regression-tested while a production-like external-service gate remains unavailable. The correct response is to preserve the boundary, not to relabel an inline demo as Redis/Qdrant production evidence or prematurely change the public version.

<!-- learning:v5-1-runtime-and-release-closure-20260826 -->
### V5.1 runtime and release closure: test the queue you actually ship

### What changed
- Ran the Agent through real Redis/RQ and Qdrant rather than treating an inline worker as equivalent.
- Replaced colon-delimited Agent job ids with RQ-safe hyphenated ids after the real broker rejected them.
- Pinned the Qdrant container to the client-compatible 1.18.0 release.
- Prewarmed 21 Next.js route groups and bounded the strict suite at four parallel browser workers, then
  added explicit URL assertions for code-evidence navigation.
- Unified public, backend, frontend, CI and release-tooling versions at `V5.1 / 5.1.0`.

### Verification
- Two isolated canonical runs passed `32/32` browser scenarios with different ports, databases,
  queues, collections, workers and containers; both cleaned all owned resources.
- A forced post-container startup failure cleaned both exact containers and left no run database.
- Code-viewer concurrency regression passed `24/24`.
- Final post-review backend regression passed `457 passed, 1 skipped in 168.33s`.
- Frontend lint/typecheck, `19 files / 81 tests`, 34-route build and production audit with 0 vulnerabilities passed.
- Migration `0008→0006→0008`, 60/60 deterministic Agent evaluation, acceptance gate, quick quality gate,
  secret scan and release dry-run passed.

### What to understand
An architecture can be correct in unit tests and still fail at the integration boundary: RQ's real job-id
rules were stricter than the in-memory broker. End-to-end evidence is strongest when every run owns its
infrastructure identities and proves cleanup on both success and failure. Browser parallelism is also a
test-system design decision: local development compilation must be separated from product behavior so
CPU contention does not masquerade as a navigation defect.

### Honest boundary
Model configuration was intentionally skipped. LLM, embedding, OCR, vision, transcription and rerank
dry-runs all reported not configured and made zero provider calls. The 60-case result is deterministic
architecture/regression evidence, not a real-model quality benchmark.

### Review closure
The two-axis review found no hard repository-standard violation. It did expose a strict-origin fallback,
an unstructured final runtime verdict, an ambiguous lockfile rule and three maintainability smells. The
origin fallback now fails closed, the final manifest carries the verdict, the spec distinguishes dependency
resolution from root version metadata, shared artifact labels/action lifecycles were extracted, and RunOrigin
persistence now uses one codec seam.

### Release evidence
The V5.1 source set was packaged as `AI-Knowledge-OS-Pro-V5.1-20260826.zip`; the release checker
reported 602 files, forbidden 0, missing 0, a verified manifest and current source freshness.

<!-- learning:v5-2-agent-control-20260827 -->
### V5.2 Agent control center: an intelligent system also needs a dashboard and an exam

### What changed
- Added a persisted Run Trace that reconstructs what an Agent already did from SQL facts without rerunning a
  model, tool, vector search, or external side effect.
- Added a durable Evaluation Studio: an idempotent SQL command creates an immutable snapshot request and
  transactional Outbox record; Redis/RQ runs the one fixed 60-case evaluator; validated results become history.
- Added compatible snapshot comparison, metric/gate/failure deltas, explicit policy-fingerprint disclosure,
  deterministic failure triage, status filtering, rerun, provenance display, and mobile/keyboard-safe pages.
- Closed adversarial privacy gaps by sanitizing the persisted Run goal, ignoring policy facts from private events,
  and replacing child-process credential denylisting with a minimal environment allowlist plus empty provider keys.
- Centralized Agent-control number, percentage, duration, timestamp, and exact metric formatting instead of
  guessing metric types from string fragments.

### How it works
`AgentControl.submit / inspect / execute / recover` is the small public Interface. SQL rows, leases, terminal-write
fences, report validation, trace projection, comparison, and triage stay behind it. The evaluator command, mode,
dataset, database, and output arguments are constructed internally; HTTP callers cannot supply a command or path.
Evaluation result contracts independently verify the report schema, evaluator/dataset SHA-256, 60 unique cases,
category totals, metrics, gates, failure ids, and zero provider calls before data can be shown as passed.

### Verification checkpoint
- Focused post-review backend privacy/executor/API regression: `57 passed`.
- Focused Agent-control frontend regression: `6 files / 17 tests`; lint and typecheck passed.
- Pre-review full gates: backend `531 passed, 1 skipped`; frontend `24 files / 96 tests`, 35-page production build,
  dependency audit with 0 vulnerabilities, fixed evaluation `60/60`, and two strict runtime runs `36/36` each.
- Final post-review full and double-runtime evidence is recorded separately after the unchanged gates complete.

### What to understand
RAG quality cannot be judged only by a plausible answer. A portfolio-grade Agent should preserve evidence identity,
show its decisions, prove that private inputs stay private, survive queue/worker failure, and compare fixed regression
snapshots. A policy fingerprint does not judge quality by itself; it explains whether two scores came from the same
decision rules or from an intentional policy change.

### Honest boundary
Model configuration remains intentionally unchanged. This stage proves deterministic architecture, safety,
persistence, recovery, traceability, and regression control. It does not claim real-LLM answer quality.

<!-- learning:v5-2-final-verification-20260827 -->
### V5.2 final verification: test semantics, not scheduler luck

The first post-review full suite exposed two release-scan failures from one secret-shaped test fixture and one
timing-sensitive Outbox heartbeat assertion. The release fixture was split without weakening either scanner. The
heartbeat test now waits for an observed SQL lease extension beyond its original expiry before attempting takeover,
instead of assuming a background thread receives CPU within 1.35 seconds. It passed eight times under concurrent
Next.js build pressure.

Metric metadata was also consolidated into one backend and one frontend catalog. The final backend suite passed
`533 passed, 1 skipped in 210.90s`; frontend passed `25 files / 98 tests`, lint, typecheck, 35-page build and an audit
with 0 vulnerabilities. Strict runtime tokens `16816-389b8657` and `22308-2d0704c5` each passed `36/36` and cleaned
their exact processes, Redis/Qdrant containers, database, WAL and SHM files.

<!-- learning:v5-2-nonfinite-final-20260827 -->
### V5.2 malformed-number closure: JSON-shaped does not always mean valid JSON data

The final Spec review demonstrated that Python accepts `NaN` and positive/negative infinity as numbers and emits
them by default even though they are not interoperable JSON values. Evaluation report canonicalization now uses
`allow_nan=False`, and the numeric validator independently requires finite floats. Three adversarial cases cover a
root metric, fusion retrieval metric, and case latency.

After the fix, backend regression passed `536 passed, 1 skipped in 236.78s`. The fixed 60-case evaluation and
acceptance checker passed. Strict runtime tokens `18664-deccddad` and `24528-b972f20c` each passed `36/36` and
cleaned every owned process, container and database side file.

<!-- learning:v5-2-release-archive-20260827 -->
### V5.2 release archive closure

The final tracked source set was packaged as `AI-Knowledge-OS-Pro-V5.2-20260827.zip`. The checker found 651 files,
zero forbidden paths, zero missing tracked sources, a verified per-file manifest, and current source freshness.
The whole-archive digest remains in the generated sidecar to avoid a recursive source/hash dependency.

<!-- learning:v5-3-adaptive-policy-20260828 -->
### V5.3 adaptive retrieval policy: make Agent behavior testable before changing production

### What changed
- Retrieval settings moved from scattered runtime constants into immutable SQL policy versions with canonical JSON
  and SHA-256 identity.
- Every new Run pins the exact policy id, version, fingerprint and snapshot; later activation cannot silently change
  an in-flight or historical Run.
- Policy Lab supports bounded draft creation, field comparison, counterfactual simulation, fixed candidate
  evaluation, guarded activation and audited rollback.
- Factual, comparative and temporal requirements can use different Top-K limits. Score threshold, duplicate removal,
  per-source diversity and neighbor context are derived only from the Run-pinned snapshot.

### How it works
`AgentPolicy.submit / inspect / simulate` is the small public Interface. SQL lifecycle, idempotency, optimistic
concurrency, activation audit, deterministic projection and strict configuration validation remain behind it. A
candidate cannot become active until the fixed 60-case evaluator records the same policy fingerprint, all required
hard gates, zero failures and zero external provider calls. The activation path independently rechecks those facts,
so a truncated or tampered database gate set cannot authorize release.

### Adversarial findings
- SQLite timestamps without explicit UTC offsets broke the strict frontend contract; the module now normalizes them.
- An already-visible E2E label could falsely signal activation completion; the test now waits for exact POST responses.
- The Run API initially omitted a persisted policy snapshot; the response projector and API regression were fixed.
- Updating the evaluator changed its source fingerprint and correctly invalidated the stored report. The canonical
  60-case report was regenerated instead of weakening provenance validation.
- A hand-forged evaluation row with only one true gate could pass the first activation predicate. Test-first
  hardening now requires the exact fixed gate set, dataset identity, digests and honest provider boundary.

### Honest boundary
Counterfactual simulation projects recorded retrieval decisions; it does not rerun search or predict answer quality.
No real LLM, embedding, OCR, vision, transcription or rerank provider was configured in this stage. Fixed evaluation
proves deterministic architecture and regression behavior, not real-model intelligence.

<!-- learning:v5-3-final-closure-20260828 -->
### V5.3 final closure: privacy is also about what code reads

The first two-axis review had no documented-standard violation, but found repeated field metadata, duplicated Run
snapshot parsing, an oversized policy service, a simulation privacy-read defect, a missing Run Trace fingerprint,
and incomplete keyboard/adaptive E2E evidence. Metadata now has one frontend descriptor; snapshot parsing has one
domain object; activation and recorded-decision loading are separate deep modules; Run Trace displays the exact
policy SHA-256; and browser tests verify keyboard-only draft creation plus terminal adaptive Top-K facts.

The follow-up review noticed that a public `tool.started` event is only an attempt, not proof of completion.
Simulation now joins the public event to its ToolCall status while selecting no private arguments; a failed-call
regression proves abandoned attempts do not affect deltas or digest. Final review result: Standards 0, Spec 0.

Final evidence: backend `582 passed, 1 skipped in 235.58s`; frontend `28 files / 105 tests`, lint, typecheck,
36-static-page production build and 0 dependency vulnerabilities; strict runtime tokens `22736-058d00e4` and
`35052-dc01de48` each passed `40/40` and removed exact owned resources. The V5.3 archive contains 693 tracked files
with forbidden 0, missing 0, verified manifest and current freshness; the final GitHub branch SHA matches local.


## V5.4A：离线检索策略优化器核心（Offline Retrieval Optimizer Core）

### 版本总结

V5.4A 在不触碰 V5.3 稳定分支的前提下，新增了"离线检索策略优化器核心"：
自动生成多组安全的 RAG 检索策略候选，用固定 60 场景评测器运行可持久化的
Trial，比较质量、延迟与检索窗口成本，计算帕累托前沿并给出带完整理由的
推荐候选。推荐只输出数据，激活仍然只能走 V5.3 的人工硬门接口。

### 本版本实现了什么

- Optimization Study：幂等创建（request_id + payload hash）、预算（候选数/
  评测数/deadline）、搜索空间与 permille 权重持久化。
- Candidate Generation：以 seed 驱动 `random.Random`，ordinal 1 固定为基准
  锚点，重复配置丢弃补采，唯一 SHA-256 指纹，越界直接拒绝。
- Durable Trial Execution：SQL Outbox（topic=`agent.optimize.trial`）→
  OutboxDispatcher 租约认领 → Redis/RQ（`app.tasks.optimizer_tasks.run_optimization_trial`）
  → `FixedSubprocessTrialAdapter`（复用 V5.2 固定评测器子进程，`--policy-config`
  注入候选快照）→ 条件 UPDATE fence 写回 `agent_evaluations` + Trial 指标。
- Multi-objective Scoring：6 指标（case_pass_rate / mean_source_recall /
  citation_completeness / latency_ms[agent_p95] / retrieval_window /
  external_provider_calls=0）min-max 归一化（退化→0.5），permille 权重加权，
  score_millis 0-1000 整数；每次完成后对全集中算归一化，保证跨 Trial 可比。
- Pareto Frontier：`dominates` 按方向目录逐指标判定；`qualify_trial` 六重
  合格门；`(−score, ordinal, trial_id)` 稳定排序。
- Recommendation Engine：只从合格前沿构建，理由含改进/持平/退步逐指标、
  支配关系、权重取向与全链 SHA-256 引用；模块内无任何激活路径。
- Cancellation/Recovery/Fencing：取消后不再派生（running 允许跑完）、
  过期 lease 原子接管、晚到 worker 被 fence 拒、重复投递去重、预算停机。
- API：九条严格校验路由（extra=forbid + StrictInt + 边界 model_validator +
  prompt/shell/code/secret 文本拒绝），无 HTTP 内联评测端点。

### 本版本新增或修改的主要文件

- 新增 `backend/app/modules/agent_policy_optimizer/`（contracts / objectives /
  candidate_generation / pareto / recommendation / service / executor /
  recovery / wiring / interface）
- 新增 `backend/app/models/optimizer.py`、
  `backend/alembic/versions/0011_v5_4_retrieval_optimizer.py`
- 新增 `backend/app/api/routes_optimizer.py`、`backend/app/schemas/optimizer_schema.py`、
  `backend/app/tasks/optimizer_tasks.py`
- 修改 `backend/app/services/task_broker.py`（新 topic 映射）、
  `backend/app/services/outbox_dispatcher.py`（envelope task_id）、
  `backend/app/worker.py`（优化器恢复循环）、`backend/app/main.py`
  （422 校验错误的 JSON 安全序列化）、`backend/app/api/router.py`
- 新增测试五个文件：`test_v5_4a_optimizer_{pure,sql,api,worker,migration}.py`

### 本版本涉及的 AI 应用开发知识点

**多目标优化与帕累托前沿**
- 小白解释：多个指标互相冲突时，不存在"全面最好"的一个答案，只存在
  "没有被别人全面超过"的一组答案。
- 项目用法：优化器用支配关系筛出前沿 Trial，再按加权分排序展示。
- 后续补课：NSGA-II 等多目标进化算法、超参搜索（Optuna）。
- 面试表达：我用纯函数实现支配判定与前沿计算，保证相同输入必得相同输出，
  并用合格性过滤把失败/作弊 Trial 排除在前沿之外。

**写入围栏（Fence）与租约（Lease）**
- 小白解释：给每个任务发一张"工牌"，只有持有当前工牌的人才能写结果；
  工牌过期可以被回收重发。
- 项目用法：Trial 完成写回必须同时匹配 status（running→completing）和
  lease_owner，晚到 worker 的结果因不匹配被拒。
- 后续补课：分布式锁（Redis SETNX、ZooKeeper）、CAS 操作。
- 面试表达：我用条件 UPDATE 实现乐观围栏，避免分布式锁的复杂性，
  同时用 dedupe_key 唯一约束挡住重复投递。

**SQL Outbox 模式**
- 小白解释：把"要做的事"先写进数据库，再由后台进程投递，保证业务数据
  和消息同生共死。
- 项目用法：Trial 与 outbox 消息在同一事务创建，崩溃后可从 outbox 恢复。
- 后续补课：CDC（Change Data Capture）、Debezium。
- 面试表达：outbox 让我在不引入双写不一致的前提下获得 at-least-once 投递。

### Honest boundary

- 固定 60 场景评测器仍是确定性架构证据，不是真实模型质量基准。
- 推荐策略不自动激活；激活必须走 V5.3 人工硬门。
- Strict E2E 在本机存在与 V5.3 基线完全一致的 2 个环境性 flake
  （agent run 卡在 routing），与 V5.4A 改动无关，已三跑对照验证。


## V5.5：检索优化器闭环（Optimizer Closed Loop）

### 版本总结

V5.5 打通了 V5.4A 留下的最后一公里：推荐候选可以一键转成 V5.3 draft 策略
（绝不自动激活）、候选可与当前生效策略逐字段对比、Study 有了正确的收尾
状态机（全成功→completed，全失败→failed）、失败 Trial 可在预算内重试、
操作员可显式终止跑偏的实验。

### 本版本实现了什么

- Convert To Draft：复用 V5.3 `SqlAgentPolicy.submit` 的幂等命令日志创建
  draft；四重安全链（归属/completed+推荐排名/全集 Pareto 前沿/指纹重建）；
  并发双转换靠 UNIQUE 约束 + IntegrityError 回退返回既有 draft。
- Candidate Diff：`compare_policy_configs(active, candidate)`，left/right
  方向与 Spec 一致，输出双侧 SHA-256 与 Trial 指标摘要。
- Settlement：`_maybe_settle` 在完成/失败写回事务内统一收尾。
- Retry：仅 running Study + 评测预算内可重试；cancel/fail 死信不复活。
- Fail：显式终止端点，终态化未完成 Trial 并死信未派发消息。

### 本版本涉及的 AI 应用开发知识点

**闭环（Closed Loop）设计**
- 小白解释：推荐如果不接上执行路径，就只是报表；闭环 = 推荐 → 草稿 →
  人工门 → 生效，每一步都有闸门。
- 项目用法：convert-draft 复用既有幂等命令日志，让"转草稿"与"建策略"
  共享同一套审计与回放。
- 后续补课：人的监督节点设计（human-in-the-loop）、灰度发布。
- 面试表达：我用幂等命令 + 唯一约束实现并发安全的转换，并用四重校验
  保证"写的和测的是同一份配置"，但从不替代人工激活门。

**幂等性与并发收尾**
- 小白解释：同一个操作做一次和做多次，结果要一样。
- 项目用法：同 request_id 回放、异 request_id 去重、并发撞唯一约束时
  返回已存在结果而不是报错。
- 后续补课：分布式幂等键设计、Outbox + 幂等消费者。
- 面试表达：幂等三态（replay/去重/并发回退）是我在数据层用约束兜底、
  在服务层用条件 UPDATE 实现的，测试覆盖了全部三态。

### Honest boundary

- 转出的永远是 draft；激活必须人工走 V5.3 满分评测硬门。
- Strict E2E 仍有 2 个既有环境 flake（与 V5.3/V5.4A 基线完全一致）。


## V5.6：贝叶斯检索优化器（Bayesian Optimizer + Category Analysis）

### 版本总结

V5.6 让优化器从"随机试错"升级为"观测引导"：用已完成 Trial 的
(配置, 分数) 观测拟合线性代理模型，沿预测改进方向采样，探索率随轮次衰减；
同时实验可多轮推进（next-round）、可暖启动（继承历史观测）；
评测产出增加 7 类场景的胜败明细，推荐理由包含类别级解释。

### 本版本涉及的 AI 应用开发知识点

**贝叶斯优化的工程化入门**
- 小白解释：与其乱试，不如先从已有成绩里学"哪个方向大概率更好"，
  再带着方向去试，但仍留一些乱试的机会以免错过意外好解。
- 项目用法：一维最小二乘斜率作为代理模型（纯 Python、确定性、零依赖），
  探索率 0.6 → 0.2 衰减。
- 后续补课：高斯过程回归、TPE（Optuna 的默认算法）、采集函数
  （expected improvement / UCB）。
- 面试表达：我用最小可行代理模型实现观测引导采样，把"是否更聪明"变成
  可测的统计断言（引导方向、探索收敛），同时保留完整确定性以支撑审计。

**实验的多轮化与暖启动**
- 小白解释：好实验不是一次做完，而是跑一轮学一轮；新实验可以站在旧实验
  的肩膀上。
- 项目用法：next-round 基于全集观测续跑，ordinal 接续、预算分层
  （每轮候选数 / 跨轮评测总量）。
- 后续补课：AutoML 的迭代搜索、实验追踪（MLflow 式 lineage）。
- 面试表达：轮次链通过 warm_start_study_id + round_no 持久化，幂等键
  next_round_request_id 由唯一约束兜底。

**胜败的粒度**
- 小白解释：总分一样不代表一样好——分类别看才能发现"赢了推理、输了召回"。
- 项目用法：60 题按 7 类聚合出 pass_rate/recall 对比与 verdict，
  推荐理由自动附带类别摘要。
- 后续补课：误差分析（error analysis）方法论、分 slice 评估。
- 面试表达：我把逐案例结果做成纯函数对比器，让推荐从"总分排序"升级为
  "可解释的类别级证据"。

### Honest boundary

- 代理模型是启发式引导，不是全局最优求解器。
- 评测仍是确定性架构证据；真实模型质量基准仍待 Provider 配置。


## V5.7：实验工作台后端（Experiment Workbench Backend）

### 版本总结

V5.7 是从算法层转向功能层的第一期：把 V5.4A-V5.6 的算法能力包装成用户
工作流——Study 全景视图（含操作可行性推断）、模板一键创建、生命周期
事件流、对比报告导出、Agent Run 只读分享令牌。纯后端，为 V5.4B 页面铺路。

### 本版本涉及的 AI 应用开发知识点

**工作流聚合接口（BFF 模式）**
- 小白解释：前端要画一个页面，与其调五个接口自己拼，不如后端给一个
  "页面数据"接口，连按钮能不能点都告诉它。
- 项目用法：overview 端点聚合轮次/前沿/推荐/actions；actions 是核心——
  状态机知识在后端，前端只做渲染。
- 后续补课：BFF（Backend for Frontend）模式、GraphQL 片段。
- 面试表达：actions 列表把"状态机可行性"留在后端，避免前端复制状态机
  逻辑造成两端漂移。

**事件溯源的轻量版**
- 小白解释：把"发生了什么"按顺序记下来，就能回答"怎么走到这一步的"。
- 项目用法：12 类生命周期事件与状态变更同事务落库，游标分页读出。
- 后续补课：完整 Event Sourcing、事件回放重建状态。
- 面试表达：事件与状态同事务保证不丢不假，payload 只存摘要防泄漏。

**确定性文档导出**
- 小白解释：报告要能存档对比，同输入必须同输出，还要有指纹。
- 项目用法：markdown 渲染纯函数化 + sha256 + 敏感文本检查。
- 面试表达：纯函数渲染让报告可测试、可复现，sha256 让收件人可验证。

### Honest boundary

- 全部为后端功能，页面归 V5.4B。
- 分享 trace 只读且与直接 trace 同构，无新增暴露。
<!-- learning:v5-7-integration-workbench-20260901 -->
### V5.7 integration: an optimizer is only credible when its history, budget and UI tell the same truth

WorkBuddy 的 V5.4A–V5.7 后端提供了离线检索策略优化主线，但集成审查证明“已有算法”不等于“已有可靠产品”。本阶段补齐了三类关键学习：

- 数据升级也要保存幂等事实。V5.6 只把最后一次 next-round request 留在 Study 行上；V5.7 新建命令收据表时必须回填旧请求，否则升级后重放可能重复创建轮次。
- 前端不能根据状态字符串猜操作。Recover、Retry、Convert 等动作必须由后端状态机返回 availability 与 reason；页面只呈现事实，不复制业务规则。
- 代码拆文件不等于拆边界。最终用 typed Protocol、共享 record lookup 和单一 lifecycle constants，把 comparison export、draft conversion、Trial inspection、workbench projection、terminal commands 从 2,312 行服务中拆成真正有契约的协作者。

对抗性审查还修复了策略/评测指纹错配、真实 latency 丢失、类别数据由聚合值伪造、事件游标跳项、历史轮次幂等、published/dead-letter Outbox 恢复、模板预算被扩大、分享客户端跨域和错误码兼容等问题。最终 Standards 与 Spec 两轴均为 0 findings。

验证证据：优化器聚焦 `99 passed`；后端全量 `681 passed, 1 skipped`；前端 `32 files / 114 tests`；固定评测 `60/60` 且外部 Provider 调用为 0；Strict E2E 两次 `43/43`，tokens 为 `33076-80ffeecb` 与 `43720-a78a94be`，每轮均精确清理 3 Worker、前后端进程、Redis、Qdrant 和 SQLite sidecars。

<!-- learning:v5-7-1-audit-hardening-20260906 -->
### V5.7.1：能跑通一遍，不等于异常发生后仍然可信

这轮不是增加更多 Agent 按钮，而是重新检查“任务历史、实际执行、数据库结果和页面显示是否说同一件事”。关键学习：

- **事务（Transaction）**：评测结果和评分应一起保存；生成草稿和记录转换也应一起保存。先保存一半再补另一半，崩溃就会留下矛盾状态。
- **幂等性（Idempotency）**：网络响应丢失不代表后端没执行。页面重试必须保留同一个意图标识，数据库也要识别它，避免多建一份实验。
- **租约与执行身份（Lease / execution identity）**：同一个 Worker 名不代表同一次执行。每次尝试需要独立凭证，旧进程失效后不能覆盖新结果。
- **快照（Snapshot）**：暖启动要保存当时参考的数据，而不是每次都去读不断变化的父实验。没有记录过的历史快照不能编造，迁移必须声明边界。
- **证据校验**：报告总分漂亮并不够。逐题事实、硬门、数据集指纹和策略身份必须一致；缺失真实报告就明确失败，不能从汇总值补造题目。
- **诚实术语**：当前候选生成是线性观察引导与随机探索，不包含贝叶斯后验。历史模块名可以兼容保留，但简历和说明应准确描述实际算法。

如何验证：使用真实并发、带数据迁移回环、响应中断重试、自动更新和刷新后撤销测试。最终后端 `701 passed, 1 skipped`，前端 `115 passed`，固定场景 `60/60`，严格浏览器链路两轮各 `44/44`。这些是软件流程证据，不是实际大模型质量成绩。

系统学习入口：`docs/v5_7_1_audit/upgrade_explained.md`。推荐先讲清一个完整用户场景，再沿着页面、接口、任务队列、证据和数据库逐层学习，而不是一次背完所有术语。

<!-- learning:v5-8-reviewed-feedback-20260906 -->
### V5.8：反馈不是事实，接受反馈也不等于模型学会了

**反馈快照（Snapshot）**保存当时的问题、答案、策略与引用现场，而不是仅保存一个赞或踩。服务器读取事实并保存内容指纹，客户端不能伪造原文。

**幂等性（Idempotency）**保护网络失败后的重试；**事务（Transaction）**保证接受反馈与生成样例一起成功或一起失败。实际并发和故障注入测试比重复顺序调用更能揭示问题。

**调参（Tuning）与留出测试（Holdout）**需要用途隔离，真实模型结果和演示数据也不能混合导出。人工填写的参考答案是待验证预期，不因为被接受就变成客观真理。

前端的一次真实教训：把“正在提交”当成重新加载详情的触发条件，会卸载表单、清掉输入和错误，连幂等标识也一起丢失。本次通过浏览器故意让审阅失败来捕获，再将提交状态与详情读取解耦。导出时另一条反馈的未完成审阅也必须保留。

工程验证：后端 `733 passed, 1 skipped`，前端 `121 passed`，两轮严格浏览器各 `47/47`，固定场景 `60/60`。新反馈样例本期只完成审阅与导出，没有自动执行评分。完整中文实现说明见 `docs/v5_8_feedback/upgrade_explained.md`。

<!-- learning:v5-8-1-hardening-20260926 -->
### V5.8.1：能找到真实来源，不代表结论一定被来源证明

这轮从已经跑通的功能里寻找反例，而不是增加更多 Agent 名词。最重要的教训是：证据的版本和位置都正确，仍可能把“Alpha 延迟 42 毫秒”错误说成“Omega 支持至少 40 人”。现在数字必须连同主体、指标、单位、比较关系和时间范围一起核对；无法证明的复杂改写退回证据原文，不伪装成“已验证”。

另一个教训是预算要传到真正发请求的地方。只在请求回来后统计，挡不住底层自动重试和已经产生的输出。真实 Agent 现在会把剩余次数、输出额度与请求超时传到模型调用层，修复第二次输出时重新计算额度。输入 token 仍是估算，未配置价格或请求超时后仍无法证明精确费用，说明时必须把限制说清楚。

页面重试不是“重新创建一次”。同一份提交保留请求标识，拿到任务编号后只重读原任务；优化器推荐也不能只看过去留下的名次，而要重新检查评测报告。代码仓库导入还要检查 Windows 目录联接，不让选定文件夹外的资料混进证据库。

验证：后端 `783 passed, 2 skipped`（两项文件符号链接测试受本机权限限制）；前端 `33 files / 125 tests`，正式构建及生产依赖审计通过；固定离线评测 `60/60`。Docker 引擎不可用，严格端到端测试未执行；真实模型效果也未验证。具体反例和边界见 `docs/v5_8_1_hardening/acceptance.md`。

<!-- learning:v5-9-research-journey-20260927 -->
### V5.9：把能力串成一次可信研究，比再加按钮更重要

用户真正需要的是从问题和资料出发，知道下一步该做什么，而不是先学会 Agent 内部有多少运行模式。这轮把“三份技术资料对比”作为入口：准备资料、选择维度、固定来源、运行审批、查看结论和原文。对比请求仍复用原有有界 Agent；页面只是把容易误选的内部模式固定成合适的组合。

最有价值的反例是“目录里有三份文件”不等于“三份资料已经可引用”。UI 只统计存在有效版本的文档；上传未完成、处理失败或已退役都不能凑数。服务状态同理：录制演示能走通流程，不等于真实大模型、向量生成、向量库和任务队列已就绪。

录制样例也要前后一致：来源版本、审批目标、报告类型、标题与三条引用应指向同一个场景；但必须反复说明结论是固定样例，不是按用户问题实时生成。真实结论的反馈仍需人工审阅，不能自动改写知识库。

验证采用单元反例、正式构建、全量后端回归和浏览器操作组合。后端 `787 passed, 2 skipped`，前端 `149 passed`，离线固定评测 `60/60`、外部模型调用 0。Docker 不可用让严格真实服务 E2E 保持未验证；这是环境边界，不应被旧版本成绩或录制演示掩盖。具体操作与英文技术词解释见 `docs/v5_9_research_journey/upgrade_explained.md`。

复审还发现：手动点通反馈表单不等于留下可重复的验收。现在把三资料选择边界、同空间上传和反馈成功确认写成浏览器回归；受控 API 响应只证明页面按合同处理成功提示，不能证明真实数据库已经保存。

<!-- learning:v5-10-research-reliability-20261002 -->
### V5.10：研究范围、提交身份和验证成绩，都不能悄悄改变

**来源覆盖（Source coverage）**必须按真正采纳的证据计算。目录有文件、检索得到片段，都不代表报告已经用到它。发布和审批恢复都重新检查固定来源版本；有缺口就明确保存缺口报告。

**幂等性（Idempotency）**需要先保存原始请求身份，再发送创建请求。可编辑草稿与不可变的待确认提交是两份不同状态；清草稿不是取消任务，改问题也不是修改已经发出的请求。拿到任务编号后只读取原任务，录制模式也不能误建新任务。

**存储失败（Storage failure）**不只有完全禁用，还有能读取旧状态却写不进去的情况。切换场景必须保留当前内存意图，不能把旧草稿读回来撤销用户操作；保存失败要说明刷新风险。后端成功也不能因本地缓存写失败而被误报成创建失败。

数字冲突不能只比较数值和单位。主体、指标、词边界、时期、区间和上下限也要一起考虑；模型把候选采纳为支持证据后，仍需执行同一道冲突检查。确定性规则只是保守防线，不是通用语义理解器。

分工的价值在于独立复核，而不是同时修改同一文件。本轮让旧窗口核对新反例，在统一工作树按文件所有权实施；所有初次失败、修复与最终实测都记入 `docs/v5_10_research_reliability/acceptance_report.md`。真实模型和 Docker 全链路仍不应被受控浏览器或离线成绩替代，逐项实现说明见同目录 `upgrade_explained.md`。

<!-- learning:interface-polish-20261004 -->
### 界面质感：让用户看清资料和操作，比展示更多 AI 装饰更重要

本轮参考 shadcn/ui（可定制界面组件集合）与 Tremor（数据看板组件），但不整套搬入依赖。现有 Next.js、React 和 CSS 足以实现紧凑导航、常驻资料选择、列表视图和真实状态图。减少过大的标题、重复介绍和不必要的装饰，让问题、资料、证据和下一步成为主要内容。

流畅性首先来自少做重复工作：`useDeferredValue` 让输入先响应、筛选稍后更新；`memo` 隔离整个列表，避免打字时旧列表又渲染；`useMemo` 复用过滤和统计；`content-visibility` 暂缓屏幕外内容绘制。仅延后过滤而不隔离列表仍不足以避免重复渲染。没有真实性能测量时，不编造提升百分比。

状态图不等于完成率。研究会补充检索，等待审批时后端 phase 也可能仍是旧阶段；页面应清楚区分当前执行、等待状态和最近上报阶段。证据分布应保留文字数量，不能仅凭颜色或漂亮图形让候选证据看起来已经被采用。

键盘验收还暴露了浏览器细节：折叠 details 内的子项可能仍有布局框，用 `getClientRects` 判断“可切换焦点”并不充分。加入折叠祖先和 tabIndex 检查，并实测正反 Tab、Esc 和窗口拉宽，才能确认手机菜单不会把焦点或正文困住。

本轮前端 171 项测试与 20 项受控浏览器流程通过，生产构建通过；它们证明界面合同，不证明真实模型质量或后端最终全验收。具体原理、操作与限制见 `docs/interface_polish_20261004/upgrade_explained.md`。

<!-- learning:main-merge-review-20261004 -->
### 合并前审查：先检查用户最后看到的判断，再判断代码是否正确

数字解析支持“系统延迟为12毫秒”，不等于支持用户更自然的“系统延迟12毫秒”。公开任务流程复现了省略“为”导致漏报冲突；增加这一分支后，独立审查又指出“不会、可能、没有、可能会、约、大概、左右”的误报。每轮先让对应成果测试失败，再补有限规则，保留原来的主体、时间、单位和“合约金额”等名词边界。

本轮新增 20 项公开任务到成果的反例，可靠性文件最终 66 项通过。可复现测试验证的范围比“所有中文表达都能理解”小得多，说明时必须保留这一限制。两处重复代码属于低优先级维护建议，不应为了合并顺手扩大成跨模块重构。完整回归和真实服务的验证范围分别记录，不用软件测试替代真实大模型效果。

<!-- learning:v5-11-trusted-research-experience-20261013 -->
### V5.11：证据条件、连接状态和文件归属，都要保留真实边界

Claim（事实结论）即使数字与原文一致，丢掉前面的年份、方案或负载条件，也可能变成错误结论。本轮把前置语境放进数字核验，把每份 Evidence（证据原文）独立处理；不能证明改写时保守拒绝，沿用带条件原文，而不假装已经实现通用语义理解。

SSE（服务器持续推送事件）结束不等于研究完成。读取重连只带 Cursor（最后接受的事件位置），不能重放创建、审批和取消命令；旧事件可补充账本，却不能倒退当前状态。页面离开还要取消准备中的计时器，防止后台不断请求。

无障碍不是给标签补一个属性：上传要能用键盘触发，拖放要真正接收文件；手机证据要在当前屏幕打开，退出后把焦点交回引用按钮。Markdown（带标题、表格和代码的文本格式）需要安全渲染，远程图片不能在打开报告时自动请求外站。

测试程序退出不代表它启动的所有服务已退出。Windows Job Object（系统进程归属容器）在执行前登记整个进程树，测试后只清理这一组。日志与 pytest 临时目录分开，还必须同时排除 Git、源码打包和编码检查，不能只依赖一份忽略规则。

红绿记录、最终验收与限制统一保存在 `docs/v5_11_trusted_research_experience/acceptance_report.md`；通俗实现解释见同目录 `upgrade_explained.md`。真实模型质量、中文检索效果与真实服务全链路依然需要独立验收。

<!-- learning:v5-11-final-review-20261013 -->
### V5.11 收口：任务完成、页面同步和测试通过，是三种不同结论

任务终态快照不代表页面读齐了事件。如果后台告诉页面最后位置是 12，页面只收到 6 就断线，必须继续补读，不能显示“已同步”。独立审查通过这一反例推动控制器和提示共用同一个判定；同版本旧历史也不能把已知末尾调小。

Linux 的进程组清理还要保留组长身份，避免退出进程的编号被其他程序复用；观察退出与真正回收分开，并限定单一回收者。Windows 的系统进程归属容器和 Linux 真内核测试要分别验收，不能把模拟接口通过当成跨平台实测。

CI（云端自动检查）会发现本机此前未覆盖的环境与依赖问题。旧浏览器测试应同步页面语义和真实资料格式，但不能删除审批、来源门槛或引用身份断言来变绿。依赖安全补丁还要核对版本范围：本轮审查拦住了开发工具自动升级与原 CSS 组件约束不一致的问题，将非必要升级收回，保留安全修复。生产扫描没有告警不等于开发工具也没有风险，未修复的上游告警要单列。

<!-- learning:v5-11-navigation-budget-20261019 -->
### 浏览器重试通过，也要保留首轮失败的事实

云端四个任务成功，但其中一条成果导航首次 15 秒超时、重试才通过，应写成 76 通过加 1 项重试通过。已有路由预热，不能未经证明就归因于冷编译。临时延迟同一个真实导航响应 18 秒，先看到局部 15 秒断言失败，再沿用既定 30 秒预算看到成功，验证的是等待策略；不能由此宣称产品性能已经提升。结束后删除人为延迟，保留精确成果、审批和引用断言，再正常复测。

<!-- learning:v5-12-literal-retrieval-20261020 -->
### V5.12：能找到原文，和真正理解答案，是两件事

SSE（持续发送任务进度的连接）成功响应头一旦发出，后面才发现任务不存在，就不能再正常返回 JSON（结构化数据）404 错误。应复用公开任务查询，在打开连接前检查；不要为了检查而等首个事件，导致正常空闲连接也迟迟打不开。请求校验以后出现的新故障仍可能断开，不能承诺所有后台异常消失。

中文不天然带空格。Lexical Retrieval（字面检索）可以先统一全角、大小写，再用相邻两字/三字片段匹配共同文字；不必冒称系统已理解同义词。重复同一个词不应无限加分；两条检索路径共享评分，避免一边纠正排名、另一边又按重复次数逆转。限定空间、来源、历史版本后再排名和截取候选，比最后丢掉越界结果可靠。

人工先锁定问题和答案，再分别运行旧新算法，保存语料、评测器和实现摘要，才能公平比较。20 个正例与 4 个无答案反例分开统计，漏召回不能移出分母。固定小题集全对不等于真实中文资料准确率全对；strict（严格检查）也不等于准确率门槛，身份/范围/负例检查和正例质量要分别验证。实际测试与审查结果见 `docs/v5_12_reliable_chinese_retrieval/acceptance_report.md`。


<!-- learning:v5-13-operational-quality-20261107 -->
### V5.13：能启动、能证明、能恢复，才算存储保证

配置项的“文档写法”和“代码解析”必须由同一份契约约束：`.env.example` 写逗号分隔，而 pydantic-settings 先按 JSON 解码，进程会在导入阶段就崩溃。修复应落在解析边界，而不是在启动脚本里加 try/except。

Windows 上 `subprocess.run(text=True)` 使用本地代码页；ffmpeg 的 stderr 不是 UTF-8 时，读取线程会抛异常，随后 `duration_ms=1` 被当成真实元数据。凡是要落库的外部进程输出，都应显式指定编码并对回退结果保持怀疑。

“文件存在”不等于“证据一致”。备份必须把磁盘内容和数据库登记指纹交叉核对；演示种子把 content_hash 写成固定标签，正好制造了这种漂移。自检默认只查存在性时，问题不会被发现。

上传路径的顺序也属于证据语义：先写入、fsync、核对大小，再写数据库；任何一步失败都应删除残留文件。恢复则必须先验证、再保留旧副本、最后替换，不能把“恢复成功”建立在覆盖唯一副本上。

全量测试的 89 个错误里，很多是同一个编码问题级联出来的。先定位首个真实失败，再逐项复跑，才能区分产品回归、测试污染和本机能力边界。

依赖审计也不是一次性动作：上一次“0 vulnerabilities”会随着新公告失效。本轮重新审计发现 Next 15.5.27 的 critical RCE/DoS 与 zod 的 high 内存问题，升级后生产依赖归零；开发链仍有 moderate，必须单独说明，而不是把 `--omit=dev` 的结果写成整个应用无风险。
