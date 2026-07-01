"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileQuestion, MessageSquare } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioSummary } from "@/types/api";

export default function PortfolioInterviewPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setSummary(await api.portfolioSummary());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载面试讲解失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="作品集求职"
        title="面试讲解"
        description="围绕项目定位、架构取舍、RAG 证据链、任务队列和真实模式边界准备可追问的讲解提纲。"
        action={
          <Link className="button" href="/chat">
            <MessageSquare size={17} />
            去问答
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!summary ? (
        <EmptyState title="正在读取讲解提纲" description="讲解点来自项目当前能力和边界说明。" />
      ) : (
        <section className="grid cols-2">
          <article className="panel stack">
            <div className="row">
              <FileQuestion size={18} />
              <h2>核心追问</h2>
            </div>
            <div className="list">
              {summary.interview_talking_points.map((point) => (
                <article className="list-item" key={point}>
                  <p>{point}</p>
                </article>
              ))}
            </div>
          </article>
          <article className="panel stack">
            <h2>诚实边界</h2>
            <div className="list">
              {summary.honest_boundaries.map((boundary) => (
                <article className="list-item" key={boundary}>
                  <p>{boundary}</p>
                </article>
              ))}
            </div>
          </article>
        </section>
      )}
    </div>
  );
}
