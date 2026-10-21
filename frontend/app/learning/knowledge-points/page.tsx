"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardList } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, statusLabel } from "@/services/api";
import type { LearningKnowledgePoint } from "@/types/api";

export default function KnowledgePointsPage() {
  const [points, setPoints] = useState<LearningKnowledgePoint[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setPoints(await api.knowledgePoints());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载知识点失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="学习成长"
        title="知识点"
        description="把版本变化、真实来源片段和项目难点沉淀成可复习、可讲解的知识点。"
        action={
          <Link className="button" href="/learning">
            <ClipboardList size={17} />
            返回学习路线
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      <section className="panel">
        <div className="list">
          {points.length === 0 ? (
            <EmptyState title="暂无知识点" description="从文档或媒体详情页生成学习资料，或确认版本学习包后再回来查看。" />
          ) : (
            points.map((point) => (
              <Link className="list-item" href={`/learning/knowledge-points/${point.id}`} key={point.id}>
                <div className="row between">
                  <strong>{point.name}</strong>
                  <StatusBadge status={point.mastery_status} label={statusLabel(point.mastery_status)} />
                </div>
                <p>{point.project_usage}</p>
                <span className="muted">{point.review_suggestion}</span>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
