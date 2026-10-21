"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileQuestion, RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioMarkdownResponse, PortfolioSummary } from "@/types/api";

export default function PortfolioInterviewPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [generated, setGenerated] = useState<PortfolioMarkdownResponse | null>(null);
  const [error, setError] = useState("");
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [generating, setGenerating] = useState(false);

  async function loadSummary() {
    setError("");
    setLoadingSummary(true);
    try {
      setSummary(await api.portfolioSummary());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载面试页基础信息失败。");
    } finally {
      setLoadingSummary(false);
    }
  }

  async function generateInterviewQa() {
    setError("");
    setGenerating(true);
    try {
      setGenerated(await api.generatePortfolioInterviewQa());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "生成面试讲解失败。");
    } finally {
      setGenerating(false);
    }
  }

  useEffect(() => {
    loadSummary();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="作品集求职"
        title="面试讲解"
        description="把项目定位、RAG 证据链、任务中心和真实边界整理成可以对外讲清楚的讲解稿。"
        action={
          <div className="row wrap">
            <button className="button secondary" disabled={loadingSummary} onClick={loadSummary} type="button">
              {loadingSummary ? <ButtonLoading label="刷新中" /> : <><RefreshCw size={17} />刷新基础</>}
            </button>
            <button className="button" disabled={generating} onClick={generateInterviewQa} type="button">
              {generating ? <ButtonLoading label="生成中" /> : <><FileQuestion size={17} />生成面试讲解</>}
            </button>
            <Link className="button" href="/chat">
              <FileQuestion size={17} />
              去问答
            </Link>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={loadSummary} />}

      {!summary ? (
        <EmptyState title="正在读取面试素材" description="后端会从真实摘要生成讲解稿。" />
      ) : (
        <section className="stack">
          <section className="panel stack">
            <div className="row between">
              <div>
                <h2>{summary.project_name}</h2>
                <p>{summary.positioning}</p>
              </div>
              <StatusBadge status={summary.runtime_mode} label={`${summary.version} / ${summary.semantic_version}`} />
            </div>
            <p className="muted">未配置 provider 时不会伪造答案，只会保留真实边界说明。</p>
          </section>

          {generated ? (
            <section className="panel stack">
              <div className="row between">
                <div>
                  <h2>{generated.title}</h2>
                  <p className="muted">{generated.message}</p>
                </div>
                <span className="pill gray">{generated.source_branch || "unknown branch"}</span>
              </div>
              <div className="markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{generated.markdown}</ReactMarkdown>
              </div>
            </section>
          ) : null}

          <section className="grid cols-2">
            <article className="panel stack">
              <h2>核心追问</h2>
              <div className="list">
                {summary.interview_talking_points.map((point) => (
                  <article className="list-item" key={point}>
                    <p>{point}</p>
                  </article>
                ))}
              </div>
            </article>
            <article className="panel stack">
              <h2>真实边界</h2>
              <div className="list">
                {summary.honest_boundaries.map((boundary) => (
                  <article className="list-item" key={boundary}>
                    <p>{boundary}</p>
                  </article>
                ))}
              </div>
            </article>
          </section>
        </section>
      )}
    </div>
  );
}
