"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpenCheck, GraduationCap, NotebookPen, Sparkles } from "lucide-react";

import { LearningLogPanel } from "@/components/LearningLogPanel";
import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import type { LearningDashboard, LearningKnowledgePoint, LearningLog, LearningNote, LearningPackage } from "@/types/api";

export default function LearningPage() {
  const [dashboard, setDashboard] = useState<LearningDashboard | null>(null);
  const [logs, setLogs] = useState<LearningLog[]>([]);
  const [packages, setPackages] = useState<LearningPackage[]>([]);
  const [points, setPoints] = useState<LearningKnowledgePoint[]>([]);
  const [notes, setNotes] = useState<LearningNote[]>([]);
  const [active, setActive] = useState<LearningLog | LearningPackage | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [confirmingSlug, setConfirmingSlug] = useState<string | null>(null);

  async function load() {
    setError("");
    try {
      const [dashboardData, logData, packageData, pointData, noteData] = await Promise.all([
        api.learningDashboard(),
        api.learningLogs(),
        api.learningPackages(),
        api.knowledgePoints(),
        api.learningNotes()
      ]);
      setDashboard(dashboardData);
      setLogs(logData);
      setPackages(packageData);
      setPoints(pointData);
      setNotes(noteData);
      setActive(packageData[0] || logData[0] || null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load learning data.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function generateDraft() {
    setDrafting(true);
    try {
      const draft = await api.generateLearningPackageDraft();
      setMessage("Learning package draft created.");
      setActive(draft);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to generate learning package.");
    } finally {
      setDrafting(false);
    }
  }

  async function confirm(slug: string) {
    setConfirmingSlug(slug);
    setError("");
    try {
      await api.confirmLearningPackage(slug);
      setMessage("Learning package confirmed and appended to the learning archive.");
      await api.updateOnboarding({ steps: { start_learning: true } });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to confirm learning package.");
    } finally {
      setConfirmingSlug(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        action={
          <button className="button" disabled={drafting} onClick={generateDraft} type="button">
            {drafting ? (
              <ButtonLoading label="Generating" />
            ) : (
              <>
                <Sparkles size={17} />
                生成学习包
              </>
            )}
          </button>
        }
        description="把每个项目版本和真实来源片段转化为可复习的知识点、卡片、测验、笔记与面试讲解。"
        eyebrow="学习成长"
        title="学习路线图"
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      {dashboard && (
        <section className="grid cols-4">
          <article className="card">
            <h3>知识点</h3>
            <p className="stat-value">{dashboard.total_knowledge_points}</p>
          </article>
          <article className="card">
            <h3>已掌握</h3>
            <p className="stat-value">{dashboard.mastered_count}</p>
          </article>
          <article className="card">
            <h3>待复习</h3>
            <p className="stat-value">{dashboard.review_needed_count}</p>
          </article>
          <article className="card">
            <h3>笔记</h3>
            <p className="stat-value">{dashboard.note_count}</p>
          </article>
        </section>
      )}
      <section className="grid cols-2">
        <div className="panel">
          <div className="row">
            <GraduationCap size={18} />
            <h2>版本时间线</h2>
          </div>
          <div className="timeline">
            {[...packages, ...logs].length === 0 ? (
              <EmptyState description="生成学习包草稿或追加版本日志后，时间线会从这里开始。" title="暂无版本" />
            ) : (
              [...packages, ...logs].map((item) => (
                <button className="list-item timeline-item" key={`${item.slug}-${"status" in item ? item.status : "log"}`} onClick={() => setActive(item)} type="button">
                  <strong>{item.version_name}</strong>
                  <span className="muted">{formatDate(item.created_at)}</span>
                  {"status" in item && <StatusBadge status={String(item.status)} label={item.status === "confirmed" ? "已归档" : "草稿"} />}
                </button>
              ))
            )}
          </div>
        </div>
        <div className="panel">
          <div className="row">
            <BookOpenCheck size={18} />
            <h2>知识点</h2>
          </div>
          <div className="list">
            {points.length === 0 ? (
              <EmptyState description="从真实文档或媒体片段生成学习材料后，知识点会出现在这里。" title="暂无知识点" />
            ) : (
              points.slice(0, 8).map((point) => (
                <Link className="list-item" href={`/learning/knowledge-points/${point.id}`} key={point.id}>
                  <div className="row between">
                    <strong>{point.name}</strong>
                    <StatusBadge status={point.mastery_status} label={statusLabel(point.mastery_status)} />
                  </div>
                  <span className="muted">{point.review_suggestion}</span>
                </Link>
              ))
            )}
          </div>
        </div>
      </section>
      <section className="grid cols-2">
        <div className="panel">
          <div className="row">
            <NotebookPen size={18} />
            <h2>最近笔记</h2>
          </div>
          <div className="list">
            {notes.length ? (
              notes.slice(0, 5).map((note) => (
                <article className="list-item" key={note.id}>
                  <strong>{note.title}</strong>
                  <span className="muted">{note.content.slice(0, 90)}</span>
                </article>
              ))
            ) : (
              <EmptyState description="可以从知识点、文档、问答和媒体片段创建笔记。" title="暂无笔记" />
            )}
          </div>
        </div>
        <div className="panel stack">
          <h2>当前学习包</h2>
          {active ? (
            <>
              {"status" in active && active.status !== "confirmed" && (
                <button className="button secondary small" disabled={confirmingSlug === active.slug} onClick={() => confirm(active.slug)} type="button">
                  {confirmingSlug === active.slug ? <ButtonLoading label="归档中" /> : "确认归档"}
                </button>
              )}
              <LearningLogPanel log={active} />
            </>
          ) : (
            <EmptyState description="生成草稿后，系统会把当前项目变更整理成学习包。" title="暂无学习包" />
          )}
        </div>
      </section>
    </div>
  );
}
