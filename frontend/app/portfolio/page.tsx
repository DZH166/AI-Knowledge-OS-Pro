"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, FileQuestion, FileText, Workflow } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioSummary } from "@/types/api";

export default function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setSummary(await api.portfolioSummary());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载作品集概览失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="作品集求职"
        title="项目复盘"
        description="真实项目概览：从数据库计数、工程质量门和能力边界组织作品集讲解，不用假 LLM 输出包装未实现功能。"
        action={
          <Link className="button" href="/portfolio/resume">
            <FileText size={17} />
            简历表达
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!summary ? (
        <EmptyState title="正在读取作品集概览" description="后端会汇总当前数据库里的资料、任务、引用和学习资产计数。" />
      ) : (
        <div className="stack">
          <section className="panel stack">
            <div className="row between">
              <div>
                <h2>{summary.project_name}</h2>
                <p>{summary.positioning}</p>
              </div>
              <StatusBadge status={summary.runtime_mode} label={`${summary.version} / ${summary.semantic_version}`} />
            </div>
            <p className="quote">真实 Provider 未配置时继续返回 NOT_CONFIGURED 类错误；Demo 数据只用于展示工作流。</p>
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
                <Link className="list-item" href="/portfolio/project-review">项目复盘路线</Link>
                <Link className="list-item" href="/portfolio/resume">简历表达要点</Link>
                <Link className="list-item" href="/portfolio/interview">面试讲解提纲</Link>
                <Link className="list-item" href="/system/observability">可观测性说明</Link>
              </div>
              <div className="row wrap">
                <FileQuestion size={17} />
                <span className="muted">模拟面试反馈仍需真实 LLM Provider，未配置时不得伪造评分。</span>
              </div>
            </article>
          </section>
        </div>
      )}
    </div>
  );
}

function capabilityStatus(status: string) {
  const labels: Record<string, string> = {
    implemented: "已实现",
    in_progress: "进行中",
    planned: "计划中",
    requires_provider: "需配置"
  };
  return labels[status] || status;
}
