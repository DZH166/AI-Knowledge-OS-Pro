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
    await api.confirmLearningPackage(slug);
    setMessage("Learning package confirmed and appended to the learning archive.");
    await api.updateOnboarding({ steps: { start_learning: true } });
    await load();
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
                Generate package
              </>
            )}
          </button>
        }
        description="Turn each project version and real source chunk into reviewable knowledge points, cards, quizzes, notes and interview-ready explanations."
        eyebrow="Learning growth"
        title="Learning Roadmap"
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      {dashboard && (
        <section className="grid cols-4">
          <article className="card">
            <h3>Knowledge Points</h3>
            <p className="stat-value">{dashboard.total_knowledge_points}</p>
          </article>
          <article className="card">
            <h3>Mastered</h3>
            <p className="stat-value">{dashboard.mastered_count}</p>
          </article>
          <article className="card">
            <h3>Review Needed</h3>
            <p className="stat-value">{dashboard.review_needed_count}</p>
          </article>
          <article className="card">
            <h3>Notes</h3>
            <p className="stat-value">{dashboard.note_count}</p>
          </article>
        </section>
      )}
      <section className="grid cols-2">
        <div className="panel">
          <div className="row">
            <GraduationCap size={18} />
            <h2>Version Timeline</h2>
          </div>
          <div className="timeline">
            {[...packages, ...logs].length === 0 ? (
              <EmptyState description="Generate a package draft or append a version log to start the timeline." title="No versions yet" />
            ) : (
              [...packages, ...logs].map((item) => (
                <button className="list-item timeline-item" key={`${item.slug}-${"status" in item ? item.status : "log"}`} onClick={() => setActive(item)} type="button">
                  <strong>{item.version_name}</strong>
                  <span className="muted">{formatDate(item.created_at)}</span>
                  {"status" in item && <StatusBadge status={String(item.status)} label={item.status === "confirmed" ? "Archived" : "Draft"} />}
                </button>
              ))
            )}
          </div>
        </div>
        <div className="panel">
          <div className="row">
            <BookOpenCheck size={18} />
            <h2>Knowledge Points</h2>
          </div>
          <div className="list">
            {points.length === 0 ? (
              <EmptyState description="Create learning artifacts from a real document or media chunk to add review material." title="No knowledge points" />
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
            <h2>Recent Notes</h2>
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
              <EmptyState description="Notes can be created from knowledge points, documents, QA and media chunks." title="No notes yet" />
            )}
          </div>
        </div>
        <div className="panel stack">
          <h2>Current Learning Package</h2>
          {active ? (
            <>
              {"status" in active && active.status !== "confirmed" && (
                <button className="button secondary small" onClick={() => confirm(active.slug)} type="button">
                  Confirm archive
                </button>
              )}
              <LearningLogPanel log={active} />
            </>
          ) : (
            <EmptyState description="Generate a draft to create a learning package from the current project changes." title="No learning package yet" />
          )}
        </div>
      </section>
    </div>
  );
}
