import Link from "next/link";
import {
  ArrowRight,
  BookOpenCheck,
  Boxes,
  Brain,
  ClipboardList,
  Code2,
  Database,
  GitBranch,
  Images,
  MessageSquare,
  Route,
  ServerCog,
  ShieldCheck,
  TimerReset,
  Workflow
} from "lucide-react";

import { PageHeader } from "@/components/ui";

const closedLoops = [
  { title: "资料闭环", path: ["Upload", "Task", "Source", "Evidence"], href: "/upload" },
  { title: "问答闭环", path: ["Question", "Retrieval", "Citation", "Jump"], href: "/chat" },
  { title: "学习闭环", path: ["Evidence", "Card", "Quiz", "Note", "Interview"], href: "/learning/cards" }
];

const modules = [
  {
    title: "前端",
    icon: Code2,
    files: ["frontend/app/*", "frontend/components/*", "frontend/services/api.ts", "frontend/types/api.ts"],
    explanation: "页面负责把上传、任务、问答、媒体、学习和作品集串成工作流。服务层统一请求后端，类型层对齐 API 响应。"
  },
  {
    title: "后端",
    icon: ServerCog,
    files: ["backend/app/api/*", "backend/app/services/*", "backend/app/schemas/*", "backend/app/models/*"],
    explanation: "FastAPI routes 暴露接口，services 编排业务，schemas 约束响应，models 保存知识库、任务、证据和学习资产。"
  },
  {
    title: "证据存储",
    icon: Database,
    files: ["Document", "Source", "MultimodalChunk", "CitationLocator", "TranscriptSegment", "VisualFrame"],
    explanation: "所有可被 RAG 使用的内容都必须能回到真实来源：文档页码、图片详情、音视频时间戳、代码文件行号。"
  },
  {
    title: "Provider 边界",
    icon: ShieldCheck,
    files: ["llm_service.py", "embedding_service.py", "ocr_service.py", "transcription_service.py"],
    explanation: "真实模式缺少 key 时返回 NOT_CONFIGURED，不生成假回答、假 OCR、假转写或假引用。"
  }
];

const ragEvidence = [
  "上传资料",
  "解析真实内容",
  "切片并保留 locator",
  "调用 embedding provider",
  "写入 Qdrant",
  "检索候选证据",
  "生成带引用回答",
  "点击跳回来源"
];

const mediaFlow = [
  { title: "图片 OCR", detail: "上传后保存真实元数据，OCR 进入任务中心；成功后写入 MultimodalChunk 和 CitationLocator。" },
  { title: "音频转写", detail: "读取真实时长；转写 provider 生成 TranscriptSegment；引用跳到时间戳。" },
  { title: "视频转写", detail: "读取 duration、width、height、has_audio；提取音轨后转写，缺 provider 明确拒绝。" },
  { title: "关键帧", detail: "抽取带 timestamp_ms 的 VisualFrame 和 MediaAsset，视频页以时间轴展示并支持点击跳转。" }
];

const learningSteps = [
  {
    title: "先看产品入口",
    page: "/dashboard",
    code: "frontend/app/dashboard/page.tsx",
    doc: "README.md",
    interview: "我把复杂 AI 项目收口成用户下一步行动，而不是堆功能入口。"
  },
  {
    title: "再看资料如何进入系统",
    page: "/upload",
    code: "backend/app/api/routes_documents.py / routes_media.py",
    doc: "docs/architecture.md",
    interview: "资料先成为可追踪 Source 或 Document，再进入任务、切片和索引。"
  },
  {
    title: "跟任务中心理解异步处理",
    page: "/tasks",
    code: "backend/app/services/task_service.py",
    doc: "docs/task_center.md",
    interview: "长耗时 OCR、转写和索引用队列治理，前端只展示真实进度和恢复建议。"
  },
  {
    title: "看 RAG 如何回答",
    page: "/chat",
    code: "backend/app/services/rag_service.py",
    doc: "docs/rag_evaluation.md",
    interview: "答案必须绑定引用；证据不足就拒答，避免把模型想象包装成事实。"
  },
  {
    title: "最后看作品集表达",
    page: "/portfolio",
    code: "backend/app/services/portfolio_service.py",
    doc: "docs/interview_qa.md",
    interview: "把真实 diff、测试结果和质量门整理成可讲解的工程故事。"
  }
];

const userActionMap = [
  ["上传视频", "/upload", "POST /api/media/video/upload", "media_service.upload_video", "Source + MediaAsset + IngestionJob"],
  ["点击转写", "/media/sources/[id]", "POST /api/media/sources/{id}/transcribe", "transcription_service", "TranscriptSegment + MultimodalChunk"],
  ["提出问题", "/chat", "POST /api/chat/sessions/{id}/messages", "rag_service", "CitationLocator + QALog"],
  ["复习卡片", "/learning/cards", "PATCH /api/learning/cards/{id}/progress", "learning_service", "LearningCard"],
  ["生成作品集", "/portfolio", "POST /api/portfolio/generate-project-review", "portfolio_service", "PortfolioMarkdownResponse"]
];

export default function ProjectStructurePage() {
  return (
    <div className="page">
      <PageHeader
        action={
          <div className="row wrap">
            <Link className="button secondary" href="/learning/roadmap">
              <Route size={17} />
              学习路线
            </Link>
            <Link className="button" href="/portfolio/project-review">
              <MessageSquare size={17} />
              面试讲解模式
            </Link>
          </div>
        }
        description="用结构图、流程图和证据链理解溯知 Evidence OS：资料如何进入可版本化证据索引，Agent 如何检索、审阅并生成可追溯产物。"
        eyebrow="学习成长"
        title="项目构造讲解"
      />

      <section className="panel structure-map">
        <div className="structure-center">
          <Brain size={26} />
          <strong>项目心智模型</strong>
          <span>知识空间把资料源、任务、RAG、引用和学习档案连成一个闭环。</span>
        </div>
        <div className="structure-loops">
          {closedLoops.map((loop) => (
            <Link className="loop-card" href={loop.href} key={loop.title}>
              <strong>{loop.title}</strong>
              <div className="flow-inline">
                {loop.path.map((item, index) => (
                  <span key={item}>
                    {item}
                    {index < loop.path.length - 1 && <ArrowRight size={13} />}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="grid cols-2">
        <article className="panel stack">
          <div className="row">
            <Boxes size={20} />
            <h2>模块关系图</h2>
          </div>
          <div className="module-grid">
            {modules.map((module) => {
              const Icon = module.icon;
              return (
                <details className="module-node" key={module.title}>
                  <summary>
                    <Icon size={18} />
                    <strong>{module.title}</strong>
                  </summary>
                  <p>{module.explanation}</p>
                  <div className="code-list">
                    {module.files.map((file) => (
                      <code key={file}>{file}</code>
                    ))}
                  </div>
                </details>
              );
            })}
          </div>
        </article>

        <article className="panel stack flow-diagram">
          <div className="row">
            <Workflow size={20} />
            <h2>从页面到证据的路径</h2>
          </div>
          <div className="route-chain">
            {["前端页面", "API", "service", "DB/model", "evidence"].map((item, index) => (
              <span key={item}>
                {item}
                {index < 4 && <ArrowRight size={14} />}
              </span>
            ))}
          </div>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>用户动作</th>
                  <th>页面</th>
                  <th>API</th>
                  <th>落点</th>
                </tr>
              </thead>
              <tbody>
                {userActionMap.map(([action, page, api, service, evidence]) => (
                  <tr key={action}>
                    <td>{action}</td>
                    <td>
                      <code>{page}</code>
                    </td>
                    <td>
                      <code>{api}</code>
                    </td>
                    <td>
                      <code>{service}</code>
                      <br />
                      <span className="muted">{evidence}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="grid cols-2">
        <article className="panel stack evidence-chain">
          <div className="row">
            <BookOpenCheck size={20} />
            <h2>RAG 证据流</h2>
          </div>
          <ol className="evidence-steps">
            {ragEvidence.map((step, index) => (
              <li key={step}>
                <span>{index + 1}</span>
                <strong>{step}</strong>
              </li>
            ))}
          </ol>
          <p className="muted">关键判断：回答必须能回到真实 chunk、source 和 locator；证据不足时拒答，不用模型想象填空。</p>
        </article>

        <article className="panel stack">
          <div className="row">
            <Images size={20} />
            <h2>多模态处理流</h2>
          </div>
          <div className="media-flow-grid">
            {mediaFlow.map((item) => (
              <details className="module-node" key={item.title}>
                <summary>
                  <TimerReset size={17} />
                  <strong>{item.title}</strong>
                </summary>
                <p>{item.detail}</p>
              </details>
            ))}
          </div>
        </article>
      </section>

      <section className="panel stack learning-stepper">
        <div className="row">
          <GitBranch size={20} />
          <h2>学习路线 stepper</h2>
        </div>
        <div className="learning-path">
          {learningSteps.map((step, index) => (
            <article className="learning-step" key={step.title}>
              <span className="step-index">{index + 1}</span>
              <div>
                <h3>{step.title}</h3>
                <Link className="citation-link" href={step.page}>
                  打开页面 {step.page}
                </Link>
                <p>
                  <code>{step.code}</code>
                </p>
                <p className="muted">
                  文档：<code>{step.doc}</code>
                </p>
                <p className="quote">{step.interview}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel stack interview-mode">
        <div className="row">
          <ClipboardList size={20} />
          <h2>面试讲解模式</h2>
        </div>
        <div className="grid cols-3">
          <article className="card stack">
            <strong>60 秒讲法</strong>
            <p>这是一个面向 AI 应用学习者的多模态知识操作系统，把上传、任务、RAG 引用和学习档案串成闭环，并用质量门保证可运行、可测试、可讲解。</p>
          </article>
          <article className="card stack">
            <strong>3 分钟讲法</strong>
            <p>先讲资料进入系统，再讲异步任务和证据索引，接着讲 RAG 引用跳转，最后讲如何用 release dry-run、E2E 和学习档案证明工程质量。</p>
          </article>
          <article className="card stack">
            <strong>追问入口</strong>
            <p>可以追问 Real mode 边界、NOT_CONFIGURED 拒绝、不可变 EvidenceRef、Redis/RQ 任务治理、Qdrant 检索和 V5 Agent 运行时治理。</p>
          </article>
        </div>
        <div className="status-line">
          <Link className="button secondary small" href="/tasks">
            看任务中心
          </Link>
          <Link className="button secondary small" href="/chat">
            看知识问答
          </Link>
          <Link className="button secondary small" href="/media">
            看媒体库
          </Link>
          <Link className="button secondary small" href="/portfolio">
            看作品集
          </Link>
        </div>
      </section>
    </div>
  );
}
