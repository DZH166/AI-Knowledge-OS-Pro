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
- 项目用法：V1 将 chunk embedding、文档名、chunk_id、预览内容等 payload 写入 Qdrant，并按知识库过滤检索；本地验证使用 `E:\Qdrant\qdrant.exe` 启动真正的 Qdrant Server。
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
- `E:\python3.12.9\python.exe -m compileall backend/app scripts`：通过。
- `E:\python3.12.9\python.exe -m pytest`：46 passed，22 warnings。
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
- `E:\python3.12.9\python.exe -m compileall backend/app scripts`：通过。
- `E:\python3.12.9\python.exe -m pytest`：49 passed，21 warnings。
- `E:\python3.12.9\python.exe -m pytest backend/tests/test_v3_9_frontend_smoke.py`：1 passed。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=19，nav_targets=16，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，20 个 build entries（含 `_not-found`）。
- `E:\python3.12.9\python.exe scripts/check_encoding.py`：通过，246 个 UTF-8 文本文件。
- `E:\python3.12.9\python.exe scripts/check_secrets.py`：通过，findings=0。
- `E:\python3.12.9\python.exe scripts/check_repo_clean.py`：通过。

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
- `E:\python3.12.9\python.exe -m pytest backend/tests/test_v4_0_learning_roadmap.py backend/tests/test_v3_9_frontend_smoke.py -q`：3 passed。
- `E:\python3.12.9\python.exe -m compileall backend/app scripts`：通过。
- `E:\python3.12.9\python.exe -m pytest`：58 passed，20 warnings。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=27，nav_targets=24，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，28 个 build entries（含 `_not-found`）。
- `E:\python3.12.9\python.exe scripts/check_encoding.py`：通过，266 个 UTF-8 文本文件。
- `E:\python3.12.9\python.exe scripts/check_secrets.py`：通过，findings=0。
- `E:\python3.12.9\python.exe scripts/check_repo_clean.py`：通过。
- `E:\python3.12.9\python.exe scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `E:\python3.12.9\python.exe scripts/evaluate_rag.py --demo`：通过。
- `E:\python3.12.9\python.exe scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `E:\python3.12.9\python.exe scripts/evaluate_rag.py --demo`：通过。

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
- `E:\python3.12.9\python.exe -m compileall backend/app scripts`：通过。
- `E:\python3.12.9\python.exe -m pytest`：53 passed，22 warnings。
- `E:\python3.12.9\python.exe -m pytest backend/tests/test_v3_audio_transcription.py::test_audio_upload_and_transcription_create_timestamped_rag_chunks backend/tests/test_v4_0_hybrid_retrieval.py -q`：3 passed。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=24，nav_targets=21，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，25 个 build entries（含 `_not-found`）。
- `E:\python3.12.9\python.exe scripts/check_encoding.py`：通过，258 个 UTF-8 文本文件。
- `E:\python3.12.9\python.exe scripts/check_secrets.py`：通过，findings=0。
- `E:\python3.12.9\python.exe scripts/check_repo_clean.py`：通过。
- `E:\python3.12.9\python.exe scripts/evaluate_rag.py --demo`：通过。

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
- `E:\python3.12.9\python.exe -m compileall backend/app scripts`：通过。
- `E:\python3.12.9\python.exe -m pytest`：56 passed，25 warnings。
- `E:\python3.12.9\python.exe -m pytest backend/tests/test_v4_0_code_repository_ingestion.py -q`：3 passed。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=25，nav_targets=22，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，26 个 build entries（含 `_not-found`）。
- `E:\python3.12.9\python.exe scripts/check_encoding.py`：通过，263 个 UTF-8 文本文件。
- `E:\python3.12.9\python.exe scripts/check_secrets.py`：通过，findings=0。
- `E:\python3.12.9\python.exe scripts/check_repo_clean.py`：通过。
- `E:\python3.12.9\python.exe scripts/release.py --version V3.8 --dry-run`：通过，未发现 secrets/database/uploads/cache。

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
- `E:\python3.12.9\python.exe -m compileall backend/app scripts`：通过。
- `E:\python3.12.9\python.exe -m pytest`：51 passed，22 warnings。
- `E:\python3.12.9\python.exe -m pytest backend/tests/test_v4_0_portfolio_summary.py backend/tests/test_v3_9_frontend_smoke.py`：3 passed。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：通过，required_routes=24，nav_targets=21，warnings=0。
- frontend typecheck：通过。
- frontend build：通过，25 个 build entries（含 `_not-found`）。
- `E:\python3.12.9\python.exe scripts/check_encoding.py`：通过，255 个 UTF-8 文本文件。
- `E:\python3.12.9\python.exe scripts/check_secrets.py`：通过，findings=0。
- `E:\python3.12.9\python.exe scripts/check_repo_clean.py`：通过。
- `E:\python3.12.9\python.exe scripts/check_version.py`：通过，`V3.8 / 3.8.0`。
- `E:\python3.12.9\python.exe scripts/evaluate_rag.py --demo`：通过。
<!-- learning:v4-0-portfolio-ui-resilience-20260702 -->
## V4.0 起步：作品集页面的服务边界和烟雾校验
### 本次补充做了什么?
- 将 `/portfolio`、`/portfolio/resume`、`/portfolio/interview`、`/portfolio/project-review` 的真实摘要加载与可选 markdown 生成拆开，避免 LLM provider 未配置时整页失败。
- 根作品集页补入“真实项目概览”文案，满足 frontend smoke 对关键文本的校验。
- 继续保留真实模式边界：生成接口缺 provider 仍然返回明确 `NOT_CONFIGURED`，不伪造内容。
### 本阶段验证结果
- `E:\python3.12.9\python.exe -m pytest`：61 passed, 25 warnings。
- `E:\python3.12.9\python.exe scripts/check_frontend_smoke.py`：passed，required_routes=27，nav_targets=24，warnings=0。
- `C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe .\node_modules\typescript\bin\tsc --noEmit`：passed。
- `C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe .\node_modules\next\dist\bin\next build`：passed，28 个 App Router routes built successfully。

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
