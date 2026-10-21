"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, Workflow } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioSummary } from "@/types/api";

export default function ProjectReviewPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setSummary(await api.portfolioSummary());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载讲解路线失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="作品集求职"
        title="讲解路线"
        description="按陌生人第一次看 GitHub 项目的顺序组织演示：定位、资料接入、RAG 证据、学习沉淀和工程质量门。"
        action={
          <Link className="button" href="/portfolio">
            <Briefcase size={17} />
            项目复盘
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!summary ? (
        <EmptyState title="正在读取讲解路线" description="讲解路线来自后端 portfolio summary。" />
      ) : (
        <section className="grid cols-2">
          <article className="panel stack">
            <div className="row">
              <Workflow size={18} />
              <h2>推荐演示顺序</h2>
            </div>
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
      )}
    </div>
  );
}
