# V3.7 Learning Package Draft

## 版本主题

GitHub 作品集化、一键演示与工程可信度强化版。

## 知识点 1：GitHub README 作品集化

- 小白解释：README 是陌生人进入项目的首页，要先讲价值，再讲怎么跑。
- 本项目为什么需要：AI Knowledge OS Pro 功能很多，如果首页只堆命令，面试官和招聘方很难快速理解项目价值。
- 相关文件：`README.md`、`docs/demo_script.md`、`docs/assets/screenshots/README.md`。
- 常见错误：夸大未实现能力、引用不存在图片、把 Demo 当真实 AI 输出。
- 面试表达：我把 README 当成产品入口设计，明确项目定位、能力矩阵、架构、Demo 路径、限制和简历表达。
- 补课建议：学习优秀开源项目 README 的结构和信息优先级。

## 知识点 2：GitHub Actions CI

- 小白解释：CI 是每次提交后自动跑的质量闸门。
- 本项目为什么需要：后端、前端、文档和发布脚本都在同一个仓库，必须自动验证不能只靠手动记忆。
- 相关文件：`.github/workflows/ci.yml`。
- 常见错误：CI 调真实付费 API、只跑一个语言栈、失败后仍宣称发布完成。
- 面试表达：我把 compile、pytest、typecheck、build、encoding、secret 和 release dry-run 都放进 CI，保证 GitHub 版本可验证。
- 补课建议：复习 GitHub Actions job、cache、working-directory 和 secrets 管理。

## 知识点 3：一键 Demo

- 小白解释：一键 Demo 是让别人用最少命令看到项目流程。
- 本项目为什么需要：多模态系统依赖 Redis、Qdrant、数据库和样例数据，不做 setup 会让体验门槛太高。
- 相关文件：`scripts/setup_demo.py`、`scripts/seed_demo_data.py`、`scripts/check_demo_ready.py`。
- 常见错误：写入正式数据库、提交私人资料、用假模型结果冒充真实能力。
- 面试表达：我设计了隔离的 synthetic demo database，展示流程但不污染真实数据，也不伪造 provider 输出。
- 补课建议：学习 seed 数据、fixture 数据和环境变量隔离。

## 知识点 4：Docker Compose

- 小白解释：Compose 用来一次启动本地依赖服务。
- 本项目为什么需要：RAG 检索和后台任务依赖 Qdrant/Redis。
- 相关文件：`docker-compose.yml`、`README.md`。
- 常见错误：把开发数据库或上传文件打进镜像/仓库。
- 面试表达：我用 Compose 管理本地服务依赖，同时保留 API/前端本地运行，便于调试和学习。
- 补课建议：复习 volumes、ports、container_name 和本地开发边界。

## 知识点 5：Demo Seed 数据

- 小白解释：seed 是预置样例数据，方便快速看到效果。
- 本项目为什么需要：没有样例源、任务和学习卡片，第一次打开页面会很空。
- 相关文件：`scripts/seed_showcase.py`、`scripts/seed_demo_data.py`。
- 常见错误：seed 里混入真实 API Key 或真实用户上传。
- 面试表达：我使用公开/合成样例构建知识库、媒体记录、任务、问答和学习档案，并明确标注 Demo 数据。
- 补课建议：学习数据库 fixture、幂等 seed 和重置策略。

## 知识点 6：Secret 检查

- 小白解释：Secret 检查会扫描仓库里是否误提交密钥。
- 本项目为什么需要：AI 项目常用 API Key，一旦提交到 GitHub 风险很高。
- 相关文件：`scripts/check_secrets.py`、`.gitignore`、`.github/workflows/ci.yml`。
- 常见错误：只 ignore `.env`，忘记 `.env.local`、`.env.production` 或日志文件。
- 面试表达：我把密钥扫描和 forbidden tracked file 检查放进 CI，降低开源展示时泄露风险。
- 补课建议：学习 GitHub secret scanning、pre-commit 和最小化环境变量暴露。

## 知识点 7：Release Dry-Run

- 小白解释：dry-run 不生成正式包，只报告会包含/排除什么。
- 本项目为什么需要：发布包不能带数据库、上传、缓存或本机临时目录。
- 相关文件：`scripts/release.py`、`scripts/check_release.py`。
- 常见错误：用目录遍历打包，把被 ignore 的嵌套仓库和缓存打进去。
- 面试表达：我让 release 脚本优先基于 Git 跟踪文件，并提供 dry-run 风险报告。
- 补课建议：复习 `git ls-files`、zip 打包和 artifact 安全边界。

## 知识点 8：GitHub Issue/PR 模板

- 小白解释：模板让贡献者按统一格式提供上下文。
- 本项目为什么需要：AI 应用问题可能来自 provider、服务、前端、任务队列或文档，需要结构化信息。
- 相关文件：`.github/ISSUE_TEMPLATE/*`、`.github/pull_request_template.md`。
- 常见错误：模板只问“发生了什么”，不问复现、日志、测试和学习档案。
- 面试表达：我补充了工程协作入口，让项目更像可维护开源项目。
- 补课建议：阅读成熟开源项目的 issue forms。

## 知识点 9：开源项目规范

- 小白解释：LICENSE、SECURITY、CONTRIBUTING 是开源项目的基本契约。
- 本项目为什么需要：GitHub 作品需要说明能否使用、如何贡献、如何报告安全问题。
- 相关文件：`LICENSE`、`SECURITY.md`、`CONTRIBUTING.md`、`docs/github_release_checklist.md`。
- 常见错误：代码开源但没有许可证，或安全问题直接贴到公开 issue。
- 面试表达：我把项目治理文件补齐，展示工程交付意识而不只是功能开发。
- 补课建议：学习 MIT License、Security Policy 和 PR review 流程。

## 知识点 10：架构图和流程图

- 小白解释：图能帮助别人快速理解系统怎么流转。
- 本项目为什么需要：RAG、多模态、任务队列和学习闭环横跨多个模块，纯文字很难讲清。
- 相关文件：`docs/architecture_diagram.md`、`README.md`。
- 常见错误：图太复杂，面试时反而讲不明白。
- 面试表达：我用 Mermaid 把系统架构、RAG、多模态任务、学习闭环和 citation jump 拆成可讲的图。
- 补课建议：练习用 1 分钟讲一张架构图。

## 知识点 11：项目简历表达

- 小白解释：简历表达要讲技术栈、难点、方案和结果。
- 本项目为什么需要：这个项目用于 AI 应用开发求职/展示，需要能从代码讲到能力。
- 相关文件：`docs/resume_pitch.md`。
- 常见错误：只写“做了 RAG 系统”，没有说数据、任务、引用、工程化边界。
- 面试表达：我能把项目讲成一个端到端 AI 应用生命周期，而不是单页 chatbot。
- 补课建议：准备 STAR 结构和追问答案。

## 知识点 12：工程可信度

- 小白解释：可信度来自测试、检查、文档和可复现，而不是口头保证。
- 本项目为什么需要：AI 项目容易演示好看但边界不清，必须用检查证明。
- 相关文件：`.github/workflows/ci.yml`、`scripts/check_*`、`docs/v3_7_predevelopment_audit.md`。
- 常见错误：只在本地跑过一次，README 却写“稳定可用”。
- 面试表达：我用 CI 和 release dry-run 证明项目能被别人拉取、检查、构建和演示。
- 补课建议：学习验收标准和证据化交付。

## 知识点 13：多模态体验收口

- 小白解释：多模态不是能上传文件就结束，关键是处理、引用和学习闭环。
- 本项目为什么需要：图片、音频、视频都应该进入任务中心并能回到证据位置。
- 相关文件：`frontend/app/media/sources/[id]/page.tsx`、`frontend/app/tasks/page.tsx`、`frontend/components/CitationPanel.tsx`。
- 常见错误：上传后没有状态、失败原因或引用跳转。
- 面试表达：我把媒体处理收束到任务中心和 CitationLocator，让回答能跳回视频/音频时间戳。
- 补课建议：复习媒体元数据、播放器 seek 和引用数据结构。

## 知识点 14：发布包安全

- 小白解释：发布包应该只包含源码和必要文档。
- 本项目为什么需要：本地 AI 项目常有数据库、上传文件和缓存，误打包会泄露隐私。
- 相关文件：`scripts/release.py`、`scripts/check_release.py`、`.gitignore`。
- 常见错误：打包整个目录而不是 Git 跟踪文件。
- 面试表达：我把 release 边界设计为 Git-tracked sources plus explicit exclusions，并用 dry-run 和 check_release 双重验证。
- 补课建议：学习 artifact hygiene 和 supply-chain 基础。
