"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, FileText, GraduationCap, MessageSquare, ServerCog, UploadCloud } from "lucide-react";

import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, ProgressSteps, StatusBadge } from "@/components/ui";
import { api, formatDate } from "@/services/api";
import type { DashboardSummary, LearningDashboard, OnboardingState, SystemStatus } from "@/types/api";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [learning, setLearning] = useState<LearningDashboard | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [summaryData, systemData, learningData, onboardingData] = await Promise.all([
        api.dashboard(),
        api.systemStatus(),
        api.learningDashboard(),
        api.onboarding()
      ]);
      setSummary(summaryData);
      setSystem(systemData);
      setLearning(learningData);
      setOnboarding(onboardingData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const onboardingSteps = ["检查系统服务", "创建知识库", "上传第一份资料", "提出第一个问题", "开始学习"];

  return (
    <div className="page">
      <PageHeader
        eyebrow="个人 AI 学习大脑"
        title="学习工作台"
        description="这里会告诉你现在应该做什么、哪些任务需要处理、哪些知识点应该继续复习。"
        action={<Link className="button" href="/upload"><UploadCloud size={17} />上传资料</Link>}
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!summary ? <LoadingSkeleton lines={5} /> : (
        <>
          <section className="panel stack">
            <div className="row between">
              <h2>首次使用向导</h2>
              <StatusBadge status={onboarding?.progress === 100 ? "completed" : "running"} label={`${onboarding?.progress ?? 0}%`} />
            </div>
            <ProgressSteps steps={onboardingSteps} active={Math.min(4, Math.floor((onboarding?.progress ?? 0) / 20))} />
            <div className="row wrap">
              <Link className="button secondary small" href="/system">检查系统</Link>
              <Link className="button secondary small" href="/knowledge">创建知识库</Link>
              <Link className="button secondary small" href="/upload">上传资料</Link>
              <Link className="button secondary small" href="/chat">开始提问</Link>
            </div>
          </section>

          <section className="grid cols-4">
            <article className="card"><div className="row"><BookOpen size={18} /><span className="muted">知识库</span></div><p className="stat-value">{summary.knowledge_space_count}</p></article>
            <article className="card"><div className="row"><FileText size={18} /><span className="muted">文档</span></div><p className="stat-value">{summary.document_count}</p></article>
            <article className="card"><div className="row"><MessageSquare size={18} /><span className="muted">问答</span></div><p className="stat-value">{summary.qa_count}</p></article>
            <article className="card"><div className="row"><GraduationCap size={18} /><span className="muted">待复习</span></div><p className="stat-value">{learning?.review_needed_count ?? 0}</p></article>
          </section>

          <section className="grid cols-2">
            <div className="panel stack">
              <div className="row"><ServerCog size={18} /><h2>系统准备状态</h2></div>
              {system && (
                <div className="status-line">
                  <StatusBadge status={system.runtime.runtime_mode} />
                  <StatusBadge status={system.qdrant.ok ? "ready" : "failed"} label={`向量数据库：${system.qdrant.ok ? "正常" : "未就绪"}`} />
                  <StatusBadge status={system.llm.ok ? "ready" : "failed"} label={`AI 回答：${system.llm.ok ? "正常" : "需配置"}`} />
                  <StatusBadge status={system.embedding.ok ? "ready" : "failed"} label={`检索模型：${system.embedding.ok ? "正常" : "需配置"}`} />
                </div>
              )}
              <Link className="button secondary" href="/system">查看修复建议</Link>
            </div>
            <div className="panel stack">
              <h2>今天建议做</h2>
              <div className="list">
                <Link className="list-item" href="/learning/cards"><strong>复习学习卡片</strong><span className="muted">{learning?.due_card_count ?? 0} 张卡片需要确认掌握状态</span></Link>
                <Link className="list-item" href="/documents"><strong>处理文档任务</strong><span className="muted">检查失败或等待处理的资料</span></Link>
                <Link className="list-item" href="/learning"><strong>继续学习</strong><span className="muted">{learning?.next_lesson}</span></Link>
              </div>
            </div>
          </section>

          <section className="grid cols-2">
            <div className="panel">
              <h2>最近上传</h2>
              <div className="list">
                {summary.recent_documents.length ? summary.recent_documents.map((document) => (
                  <Link className="list-item" href={`/documents/${document.id}`} key={document.id}>
                    <strong>{document.original_filename}</strong>
                    <span className="muted">{document.chunk_count} 个片段 · {formatDate(document.created_at)}</span>
                  </Link>
                )) : <EmptyState title="还没有资料" description="上传一份 txt、md 或 pdf，系统会自动切片并建立索引。" />}
              </div>
            </div>
            <div className="panel">
              <h2>版本成长时间线</h2>
              <div className="timeline">
                {summary.recent_learning_log ? (
                  <article className="timeline-item">
                    <strong>{summary.recent_learning_log.version_name}</strong>
                    <p className="muted">{summary.recent_learning_log.summary}</p>
                    <Link className="button secondary small" href="/learning">查看学习档案</Link>
                  </article>
                ) : <EmptyState title="学习档案待确认" description="完成版本后会追加记录，不覆盖旧档案。" />}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
