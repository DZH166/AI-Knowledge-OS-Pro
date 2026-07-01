"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, RefreshCw, Workflow } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ButtonLoading, EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioMarkdownResponse, PortfolioSummary } from "@/types/api";

export default function ProjectReviewPage() {
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
      setError(exc instanceof Error ? exc.message : "加载项目复盘基础信息失败。");
    } finally {
      setLoadingSummary(false);
    }
  }

  async function generateProjectReview() {
    setError("");
    setGenerating(true);
    try {
      setGenerated(await api.generatePortfolioProjectReview());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "生成项目复盘失败。");
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
        title="项目复盘"
        description="按陌生人第一次看 GitHub 项目的顺序组织演示：定位、资料接入、RAG 证据、学习沉淀和工程质量。"
        action={
          <div className="row wrap">
            <button className="button secondary" disabled={loadingSummary} onClick={loadSummary} type="button">
              {loadingSummary ? <ButtonLoading label="刷新中" /> : <><RefreshCw size={17} />刷新基础</>}
            </button>
            <button className="button" disabled={generating} onClick={generateProjectReview} type="button">
              {generating ? <ButtonLoading label="生成中" /> : <><Workflow size={17} />生成复盘</>}
            </button>
            <Link className="button" href="/portfolio">
              <Briefcase size={17} />
              返回复盘
            </Link>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={loadSummary} />}

      {!summary ? (
        <EmptyState title="正在读取复盘素材" description="这里只展示真实摘要和可选的 LLM 复盘输出。" />
      ) : (
        <section className="stack">
          {generated ? (
            <section className="panel stack">
              <div className="row between">
                <div>
                  <h2>{generated.title}</h2>
                  <p className="muted">{generated.message}</p>
                </div>
                <span className="pill gray">{generated.source_commit?.slice(0, 8) || "no-commit"}</span>
              </div>
              <div className="markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{generated.markdown}</ReactMarkdown>
              </div>
            </section>
          ) : null}

          <section className="grid cols-2">
            <article className="panel stack">
              <h2>推荐讲解顺序</h2>
              <div className="list">
                {summary.recommended_storyline.map((step, index) => (
                  <article className="list-item" key={step}>
                    <strong>第 {index + 1} 步</strong>
                    <p>{step}</p>
                  </article>
                ))}
              </div>
            </article>
            <article className="panel stack">
              <h2>下一步增强</h2>
              <div className="list">
                {summary.next_steps.map((step) => (
                  <article className="list-item" key={step}>
                    <p>{step}</p>
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
