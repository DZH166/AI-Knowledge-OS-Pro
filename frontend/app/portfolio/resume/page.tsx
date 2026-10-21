"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, FileText } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/services/api";
import type { PortfolioSummary } from "@/types/api";

export default function PortfolioResumePage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setSummary(await api.portfolioSummary());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载简历表达失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="作品集求职"
        title="简历表达"
        description="把真实技术事实整理成可以写进简历的项目条目；这里不调用模型自动润色，也不制造未完成能力。"
        action={
          <Link className="button" href="/portfolio">
            <Briefcase size={17} />
            返回复盘
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!summary ? (
        <EmptyState title="正在读取简历要点" description="简历条目来自项目当前真实能力清单。" />
      ) : (
        <section className="panel stack">
          <div className="row">
            <FileText size={18} />
            <h2>可用简历条目</h2>
          </div>
          <div className="list">
            {summary.resume_bullets.map((bullet) => (
              <article className="list-item" key={bullet}>
                <p>{bullet}</p>
              </article>
            ))}
          </div>
          <p className="quote">后续 V4.0 会接入真实 LLM Provider 生成不同岗位版本；未配置时必须明确拒绝，而不是输出假润色。</p>
        </section>
      )}
    </div>
  );
}
