"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, Download, FileText, Workflow } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioMarkdownResponse, PortfolioSummary } from "@/types/api";

export default function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [exported, setExported] = useState<PortfolioMarkdownResponse | null>(null);
  const [error, setError] = useState("");
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function loadSummary() {
    setError("");
    setLoadingSummary(true);
    try {
      const [summaryData, exportData] = await Promise.all([api.portfolioSummary(), api.exportPortfolioMarkdown()]);
      setSummary(summaryData);
      setExported(exportData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载作品集概览失败。");
    } finally {
      setLoadingSummary(false);
    }
  }

  async function regenerateReview() {
    setError("");
    setExporting(true);
    try {
      setExported(await api.generatePortfolioProjectReview());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "生成项目复盘失败。");
    } finally {
      setExporting(false);
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
        description="从真实数据、证据边界和可验证能力组织作品集讲解，不依赖虚假的 LLM 包装。"
        action={
          <div className="row wrap">
            <button className="button secondary" disabled={loadingSummary} onClick={loadSummary} type="button">
              {loadingSummary ? <ButtonLoading label="刷新中" /> : <><Download size={17} />刷新摘要</>}
            </button>
            <button className="button secondary" disabled={exporting} onClick={regenerateReview} type="button">
              {exporting ? <ButtonLoading label="生成中" /> : <><Workflow size={16} />生成复盘</>}
            </button>
            <Link className="button" href="/portfolio/resume">
              <FileText size={17} />
              简历表达
            </Link>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={loadSummary} />}
      {!summary ? (
        <EmptyState title="正在读取真实项目概览" description="后端会汇总当前数据库里的资料、任务、引用和学习资产计数。" />
      ) : (
        <div className="stack">
          <section className="panel stack">
            <span className="muted">真实项目概览</span>
            <div className="row between">
              <div>
                <h2>{summary.project_name}</h2>
                <p>{summary.positioning}</p>
              </div>
              <StatusBadge status={summary.runtime_mode} label={`${summary.version} / ${summary.semantic_version}`} />
            </div>
            <div className="row wrap">
              <span className="muted">未配置 LLM provider 时会返回 NOT_CONFIGURED，而不是编造内容。</span>
            </div>
          </section>

          <section className="grid cols-3">
            {summary.metrics.map((metric) => (
              <article className="panel" key={metric.key}>
                <span className="muted">{metric.label}</span>
                <p className="stat-value">{metric.value}</p>
                <p>{metric.description}</p>
              </article>
            ))}
          </section>

          <section className="grid cols-2">
            <article className="panel stack">
              <div className="row">
                <Briefcase size={18} />
                <h2>能力证据</h2>
              </div>
              <div className="list">
                {summary.capabilities.map((capability) => (
                  <article className="list-item" key={capability.name}>
                    <div className="row between">
                      <strong>{capability.name}</strong>
                      <StatusBadge status={capability.status === "implemented" ? "ready" : "pending"} label={capabilityStatus(capability.status)} />
                    </div>
                    <p>{capability.evidence}</p>
                    <span className="muted">{capability.boundary}</span>
                  </article>
                ))}
              </div>
            </article>
            <article className="panel stack">
              <div className="row">
                <Workflow size={18} />
                <h2>讲解入口</h2>
              </div>
              <div className="list">
                <Link className="list-item" href="/portfolio/resume">简历表达要点</Link>
                <Link className="list-item" href="/portfolio/interview">面试讲解提纲</Link>
                <Link className="list-item" href="/system/observability">可观测性说明</Link>
                <Link className="list-item" href="/portfolio/project-review">项目复盘路线</Link>
              </div>
            </article>
          </section>

          {exported && (
            <section className="panel stack">
              <div className="row between">
                <div>
                  <h2>{exported.title}</h2>
                  <p className="muted">{exported.message}</p>
                </div>
                <span className="pill gray">{exported.source_branch || "unknown branch"}</span>
              </div>
              <div className="markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{exported.markdown}</ReactMarkdown>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function capabilityStatus(status: string) {
  const labels: Record<string, string> = {
    implemented: "已实现",
    in_progress: "进行中",
    planned: "规划中",
    requires_provider: "需配置"
  };
  return labels[status] || status;
}
