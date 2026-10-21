"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  FileText,
  GraduationCap,
  MessageSquare,
  PlayCircle,
  ServerCog,
  UploadCloud
} from "lucide-react";

import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, ProgressSteps, StatusBadge } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import type { DashboardSummary, IngestionJob, LearningDashboard, OnboardingState, SystemStatus } from "@/types/api";

const activeStatuses = new Set(["queued", "claimed", "running", "cancelling", "retry_scheduled"]);

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [learning, setLearning] = useState<LearningDashboard | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [summaryData, systemData, learningData, onboardingData, jobData] = await Promise.all([
        api.dashboard(),
        api.systemStatus(),
        api.learningDashboard(),
        api.onboarding(),
        api.listIngestionJobs()
      ]);
      setSummary(summaryData);
      setSystem(systemData);
      setLearning(learningData);
      setOnboarding(onboardingData);
      setJobs(jobData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const onboardingSteps = ["检查系统服务", "创建知识库", "上传资料", "提出问题", "沉淀学习"];
  const readiness = useMemo(() => capabilityReadiness(system), [system]);
  const taskStats = useMemo(() => taskDistribution(jobs), [jobs]);

  return (
    <div className="page">
      <PageHeader
        action={
          <Link className="button" href="/upload">
            <UploadCloud size={17} />
            上传资料
          </Link>
        }
        description="V4.7 把首页收口成行动面板：先看系统是否可用，再看任务是否卡住，最后直接进入上传、问答、学习或作品集讲解。"
        eyebrow="个人 AI 学习工作台"
        title="学习工作台"
      />

      {error && <ErrorState message={error} onRetry={load} />}
      {!summary ? (
        <LoadingSkeleton lines={6} />
      ) : (
        <>
          <section className="panel dashboard-hero">
            <div className="stack">
              <div className="row wrap">
                <StatusBadge status={system?.runtime.runtime_mode || "real"} />
                <span className="pill gray">{summary.current_version}</span>
              </div>
              <h2>下一步：{summary.next_step_suggestion}</h2>
              <ProgressSteps steps={onboardingSteps} active={Math.min(4, Math.floor((onboarding?.progress ?? 0) / 20))} />
            </div>
            <div className="next-action-grid">
              <ActionLink href="/upload" icon={<UploadCloud size={18} />} label="接入资料" note="文档、图片、音频、视频" />
              <ActionLink href="/tasks" icon={<ClipboardList size={18} />} label="检查任务" note={`${taskStats.active} 个处理中，${taskStats.failed} 个需处理`} />
              <ActionLink href="/chat" icon={<MessageSquare size={18} />} label="开始问答" note={`${summary.qa_count} 条历史问答`} />
            </div>
          </section>

          <section className="grid cols-4">
            <MetricCard icon={<BookOpen size={18} />} label="知识库" value={summary.knowledge_space_count} />
            <MetricCard icon={<FileText size={18} />} label="文档" value={summary.document_count} />
            <MetricCard icon={<MessageSquare size={18} />} label="问答" value={summary.qa_count} />
            <MetricCard icon={<GraduationCap size={18} />} label="待复习" value={learning?.review_needed_count ?? 0} />
          </section>

          <section className="grid cols-2">
            <article className="panel stack capability-bars">
              <div className="row between wrap">
                <div className="row">
                  <ServerCog size={18} />
                  <h2>能力可用度</h2>
                </div>
                <span className="pill">{readiness.ready}/{readiness.total}</span>
              </div>
              {readiness.items.map((item) => (
                <CapabilityBar key={item.label} label={item.label} ok={item.ok} status={item.status} />
              ))}
              <Link className="button secondary small" href="/system">
                查看模型与服务
                <ArrowRight size={14} />
              </Link>
            </article>

            <article className="panel stack task-distribution">
              <div className="row between wrap">
                <div className="row">
                  <Activity size={18} />
                  <h2>任务状态分布</h2>
                </div>
                <span className="pill gray">{jobs.length} 个任务</span>
              </div>
              {jobs.length ? (
                <div className="mini-chart">
                  <TaskSegment label="处理中" value={taskStats.active} total={jobs.length} tone="ok" />
                  <TaskSegment label="已完成" value={taskStats.completed} total={jobs.length} tone="muted" />
                  <TaskSegment label="需处理" value={taskStats.failed} total={jobs.length} tone="danger" />
                </div>
              ) : (
                <EmptyState description="上传资料或执行媒体处理后，任务会出现在这里。" title="暂无任务" />
              )}
              <Link className="button secondary small" href="/tasks">
                打开任务中心
                <ArrowRight size={14} />
              </Link>
            </article>
          </section>

          <section className="panel stack">
            <div className="row">
              <PlayCircle size={18} />
              <h2>推荐行动</h2>
            </div>
            <div className="next-action-grid">
              <ActionLink href="/learning/project-structure" icon={<CheckCircle2 size={18} />} label="看项目构造" note="按模块理解代码和产品闭环" />
              <ActionLink href="/learning/cards" icon={<GraduationCap size={18} />} label="复习学习资产" note={`${learning?.due_card_count ?? 0} 张卡片待复习`} />
              <ActionLink href="/portfolio" icon={<FileText size={18} />} label="准备作品集" note="把真实证据转成面试表达" />
            </div>
          </section>

          <section className="grid cols-2">
            <article className="panel stack">
              <h2>最近证据</h2>
              <div className="list">
                {summary.recent_documents.length ? (
                  summary.recent_documents.map((document) => (
                    <Link className="list-item" href={`/documents/${document.id}`} key={document.id}>
                      <strong>{document.original_filename}</strong>
                      <span className="muted">
                        {document.chunk_count} 个片段 / {formatDate(document.created_at)}
                      </span>
                    </Link>
                  ))
                ) : (
                  <EmptyState description="上传 txt、md、pdf 或媒体资料后，这里会显示可追踪来源。" title="还没有资料" />
                )}
              </div>
            </article>
            <article className="panel stack">
              <h2>学习档案</h2>
              {summary.recent_learning_log ? (
                <article className="timeline-item">
                  <strong>{summary.recent_learning_log.version_name}</strong>
                  <p className="muted">{summary.recent_learning_log.summary}</p>
                  <Link className="button secondary small" href="/learning">
                    查看版本档案
                  </Link>
                </article>
              ) : (
                <EmptyState description="完成版本后会追加记录，不覆盖旧学习档案。" title="学习档案待生成" />
              )}
            </article>
          </section>
        </>
      )}
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <article className="card">
      <div className="row">
        {icon}
        <span className="muted">{label}</span>
      </div>
      <p className="stat-value">{value}</p>
    </article>
  );
}

function ActionLink({ href, icon, label, note }: { href: string; icon: ReactNode; label: string; note: string }) {
  return (
    <Link className="next-action" href={href}>
      <span>{icon}</span>
      <strong>{label}</strong>
      <small>{note}</small>
    </Link>
  );
}

function CapabilityBar({ label, ok, status }: { label: string; ok: boolean; status: string }) {
  return (
    <div className="capability-row">
      <div className="row between">
        <strong>{label}</strong>
        <span className={ok ? "pill" : "pill gold"}>{ok ? "可用" : statusLabel(status)}</span>
      </div>
      <div className="progress">
        <span style={{ width: ok ? "100%" : "34%" }} />
      </div>
    </div>
  );
}

function TaskSegment({ label, value, total, tone }: { label: string; value: number; total: number; tone: "ok" | "danger" | "muted" }) {
  const percent = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className={`task-segment ${tone}`}>
      <div className="row between">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="progress">
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function capabilityReadiness(system: SystemStatus | null) {
  const items = [
    { label: "向量数据库", ok: Boolean(system?.qdrant.ok), status: system?.qdrant.status || "unknown" },
    { label: "Redis / Worker", ok: Boolean(system?.redis.ok && system?.worker.ok), status: system?.worker.status || "unknown" },
    { label: "LLM 问答", ok: Boolean(system?.llm.ok), status: system?.llm.status || "not_configured" },
    { label: "Embedding", ok: Boolean(system?.embedding.ok), status: system?.embedding.status || "not_configured" },
    { label: "OCR / Vision", ok: Boolean(system?.ocr.ok), status: system?.ocr.status || "not_configured" },
    { label: "转写 Provider", ok: Boolean(system?.transcription.ok), status: system?.transcription.status || "not_configured" }
  ];
  return { items, ready: items.filter((item) => item.ok).length, total: items.length };
}

function taskDistribution(jobs: IngestionJob[]) {
  return {
    active: jobs.filter((job) => activeStatuses.has(job.status)).length,
    completed: jobs.filter((job) => job.status === "completed").length,
    failed: jobs.filter((job) => ["failed", "interrupted"].includes(job.status)).length
  };
}
