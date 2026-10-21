"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, FileText, RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioMarkdownResponse, PortfolioSummary } from "@/types/api";

export default function PortfolioResumePage() {
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
      setError(exc instanceof Error ? exc.message : "加载简历页基础信息失败。");
    } finally {
      setLoadingSummary(false);
    }
  }

  async function generateResumeEntry() {
    setError("");
    setGenerating(true);
    try {
      setGenerated(await api.generatePortfolioResumeEntry());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "生成简历表达失败。");
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
        title="简历表达"
        description="把真实工程事实组织成可以写进简历的条目，未配置 provider 时会明确拒绝，而不是编造内容。"
        action={
          <div className="row wrap">
            <button className="button secondary" disabled={loadingSummary} onClick={loadSummary} type="button">
              {loadingSummary ? <ButtonLoading label="刷新中" /> : <><RefreshCw size={17} />刷新基础</>}
            </button>
            <button className="button" disabled={generating} onClick={generateResumeEntry} type="button">
              {generating ? <ButtonLoading label="生成中" /> : <><FileText size={17} />生成简历表达</>}
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
        <EmptyState title="正在读取简历素材" description="后端会从真实项目概览和证据边界生成简历草稿。" />
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
            <p className="muted">当前版本会基于真实摘要生成；未配置 LLM provider 时会返回 NOT_CONFIGURED。</p>
          </section>

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

          <section className="panel stack">
            <div className="row">
              <FileText size={18} />
              <h2>可写入简历的条目</h2>
            </div>
            <div className="list">
              {summary.resume_bullets.map((bullet) => (
                <article className="list-item" key={bullet}>
                  <p>{bullet}</p>
                </article>
              ))}
            </div>
          </section>
        </section>
      )}
    </div>
  );
}
