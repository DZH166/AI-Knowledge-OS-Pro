import Link from "next/link";
import {
  BookOpenCheck,
  Brain,
  CheckCircle2,
  Code2,
  Database,
  FileText,
  GitBranch,
  Images,
  MessageSquare,
  Route,
  ServerCog,
  ShieldCheck,
  TimerReset
} from "lucide-react";

import { PageHeader } from "@/components/ui";

const productModel = [
  "知识空间把资料按学习主题归档，是文档、媒体、代码和问答证据的共同边界。",
  "资料源进入解析、切片、向量化和任务中心后，才会成为可检索、可引用的证据。",
  "RAG 回答必须绑定引用；证据不足或 provider 缺失时明确拒绝，不用假回答补空白。",
  "学习档案把每个版本的真实改动、测试结果和复盘表达沉淀成可复习的知识资产。"
];

const architectureLayers = [
  {
    title: "后端结构",
    icon: ServerCog,
    summary: "FastAPI routes 接收请求，services 执行业务，schemas 约束响应，SQLAlchemy models 持久化数据。",
    items: ["routes_* 暴露 API", "services 编排 RAG / media / learning", "providers 连接 LLM、embedding、OCR、transcription", "Qdrant 存向量证据，Redis/RQ 执行后台任务"]
  },
  {
    title: "前端结构",
    icon: Code2,
    summary: "Next.js App Router 提供页面，AppShell 统一导航，services/api.ts 统一调用后端，types/api.ts 对齐数据结构。",
    items: ["app/* 对应主要工作流页面", "components 承载通用 UI 和证据组件", "services 管理请求、状态标签和格式化", "E2E 与 smoke 检查保护展示路径"]
  },
  {
    title: "数据结构",
    icon: Database,
    summary: "Document、Source、MultimodalChunk、CitationLocator、IngestionJob 和 LearningArtifact 把资料、任务、证据和学习结果连起来。",
    items: ["文档块记录页码和章节", "媒体块记录 OCR / transcript / keyframe 证据", "CitationLocator 支撑跳页、跳图、跳时间戳", "学习资产保留来源归属"]
  }
];

const ragFlow = [
  "上传或同步资料",
  "解析真实内容",
  "按文档结构或媒体片段切块",
  "调用真实 embedding provider",
  "写入 Qdrant 检索集合",
  "按问题检索候选证据",
  "生成带引用的回答或明确拒绝",
  "记录问答、引用和学习沉淀"
];

const mediaFlow = [
  "图片：读取真实元数据，任务中心执行 OCR，保存可引用 OCR chunk。",
  "音频：读取真实时长，转写 provider 生成时间戳 transcript segments。",
  "视频：读取 duration / width / height / has_audio，抽音轨转写并提取关键帧。",
  "引用：图片跳详情页，音频和视频跳时间戳并高亮片段。"
];

const qualityFlow = [
  "backend compileall",
  "pytest",
  "Alembic upgrade/current",
  "frontend typecheck",
  "production build",
  "browser E2E",
  "demo RAG evidence",
  "release dry-run",
  "release safety check"
];

const studyPath = [
  { href: "/dashboard", label: "先看 Dashboard", note: "理解项目面向学习者的总入口和版本状态。" },
  { href: "/upload", label: "再看上传中心", note: "理解文档、图片、音频、视频如何进入处理流。" },
  { href: "/tasks", label: "跟进任务中心", note: "观察媒体处理、重试、取消、阶段日志和失败边界。" },
  { href: "/chat", label: "进入知识问答", note: "检查 RAG 如何使用引用支撑回答和拒绝。" },
  { href: "/media", label: "检查媒体库", note: "看多模态源、转写、关键帧和引用定位。" },
  { href: "/learning", label: "沉淀学习档案", note: "把真实版本改动转成复盘、知识点和表达材料。" },
  { href: "/portfolio/project-review", label: "最后讲作品集", note: "把工程结构、质量证据和能力边界讲给面试官听。" }
];

const docLinks = [
  { href: "https://github.com/DZH166/AI-Knowledge-OS-Pro/blob/main/docs/architecture.md", label: "architecture.md" },
  { href: "https://github.com/DZH166/AI-Knowledge-OS-Pro/blob/main/docs/rag_evaluation.md", label: "rag_evaluation.md" },
  { href: "https://github.com/DZH166/AI-Knowledge-OS-Pro/blob/main/docs/v4_6_rag_eval_report.md", label: "v4_6_rag_eval_report.md" },
  { href: "https://github.com/DZH166/AI-Knowledge-OS-Pro/blob/main/docs/release_checklist.md", label: "release_checklist.md" }
];

export default function ProjectStructurePage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="学习成长"
        title="项目构造讲解"
        description="把 AI Knowledge OS Pro 拆成产品模型、前后端结构、RAG 证据流、多模态处理流和发布质量流，方便按真实工程路径学习和讲解。"
        action={
          <div className="row wrap">
            <Link className="button secondary" href="/learning/roadmap">
              <Route size={17} />
              学习路线
            </Link>
            <Link className="button" href="/portfolio/project-review">
              <MessageSquare size={17} />
              讲解路线
            </Link>
          </div>
        }
      />

      <section className="grid cols-2">
        <article className="panel stack">
          <div className="row">
            <Brain size={20} />
            <h2>产品心智模型</h2>
          </div>
          <div className="list">
            {productModel.map((item) => (
              <div className="list-item" key={item}>
                <div className="row">
                  <CheckCircle2 size={17} />
                  <span>{item}</span>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel stack">
          <div className="row">
            <GitBranch size={20} />
            <h2>从代码到作品集的主线</h2>
          </div>
          <p className="muted">
            这个项目不是单个聊天页面，而是一套把资料、任务、证据、问答、学习和发布验收串起来的个人知识操作系统。
            学习时先看数据如何进入系统，再看证据如何被检索和引用，最后看版本如何被记录成可讲解成果。
          </p>
          <div className="status-line">
            <span className="pill">真实资料优先</span>
            <span className="pill gray">provider 缺失明确拒绝</span>
            <span className="pill gold">演示数据必须标识</span>
          </div>
        </article>
      </section>

      <section className="grid cols-3">
        {architectureLayers.map((layer) => {
          const Icon = layer.icon;
          return (
            <article className="panel stack" key={layer.title}>
              <div className="row">
                <Icon size={20} />
                <h2>{layer.title}</h2>
              </div>
              <p className="muted">{layer.summary}</p>
              <ul className="mini-steps">
                {layer.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          );
        })}
      </section>

      <section className="grid cols-2">
        <article className="panel stack">
          <div className="row">
            <BookOpenCheck size={20} />
            <h2>RAG 证据流</h2>
          </div>
          <ol className="progress-steps">
            {ragFlow.map((step, index) => (
              <li className="done" key={step}>
                <span>{index + 1}</span>
                {step}
              </li>
            ))}
          </ol>
          <p className="muted">
            核心判断标准：回答必须能回到真实 chunk、source 和 locator；证据不足时保留拒绝，而不是用模型想象填补。
          </p>
        </article>

        <article className="panel stack">
          <div className="row">
            <Images size={20} />
            <h2>多模态处理流</h2>
          </div>
          <div className="list">
            {mediaFlow.map((item) => (
              <div className="list-item" key={item}>
                <p>{item}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid cols-2">
        <article className="panel stack">
          <div className="row">
            <ShieldCheck size={20} />
            <h2>质量与发布流</h2>
          </div>
          <p className="muted">
            发布前要把本地检查、浏览器路径、演示证据、编码检查和 release dry-run 放到同一条验收链里，确保 GitHub 上展示、运行和讲解一致。
          </p>
          <div className="status-line">
            {qualityFlow.map((item) => (
              <span className="pill gray" key={item}>
                {item}
              </span>
            ))}
          </div>
        </article>

        <article className="panel stack">
          <div className="row">
            <TimerReset size={20} />
            <h2>学习路线</h2>
          </div>
          <div className="list">
            {studyPath.map((step) => (
              <Link className="list-item" href={step.href} key={step.href}>
                <strong>{step.label}</strong>
                <span className="muted">{step.note}</span>
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className="panel stack">
        <div className="row">
          <FileText size={20} />
          <h2>配套文档</h2>
        </div>
        <p className="muted">阅读这些文档可以把页面里的结构讲解进一步对应到真实仓库记录、RAG 报告和发布检查。</p>
        <div className="status-line">
          {docLinks.map((doc) => (
            <a className="button secondary small" href={doc.href} key={doc.href} rel="noreferrer" target="_blank">
              <FileText size={15} />
              {doc.label}
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
