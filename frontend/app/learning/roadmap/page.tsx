"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Route } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, statusLabel } from "@/services/api";
import type { LearningRoadmap } from "@/types/api";

export default function LearningRoadmapPage() {
  const [roadmap, setRoadmap] = useState<LearningRoadmap | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setRoadmap(await api.learningRoadmap());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载学习路线失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="学习成长"
        title="学习路线"
        description="根据 existing_knowledge_points_cards_quizzes_notes 派生学习顺序：优先复习薄弱点，再推进未开始知识点，最后练习面试表达。"
        action={
          <Link className="button" href="/learning/knowledge-graph">
            <Route size={17} />
            查看知识关系
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!roadmap ? (
        <EmptyState title="正在生成路线" description="路线来自已有知识点、卡片、练习、笔记和版本学习包。" />
      ) : roadmap.steps.length === 0 ? (
        <EmptyState title="暂无路线" description="确认学习包或从真实资料生成知识点后，这里会出现学习顺序。" />
      ) : (
        <div className="stack">
          <section className="grid cols-3">
            <article className="panel">
              <span className="muted">总步骤</span>
              <p className="stat-value">{roadmap.total_steps}</p>
            </article>
            <article className="panel">
              <span className="muted">待复习</span>
              <p className="stat-value">{roadmap.review_needed_count}</p>
            </article>
            <article className="panel">
              <span className="muted">关系数</span>
              <p className="stat-value">{roadmap.relations.length}</p>
            </article>
          </section>
          <section className="panel stack">
            <h2>路线步骤</h2>
            <div className="list">
              {roadmap.steps.map((step) => (
                <Link className="list-item" href={`/learning/knowledge-points/${step.knowledge_point_id}`} key={step.knowledge_point_id}>
                  <div className="row between">
                    <strong>{step.order}. {step.title}</strong>
                    <StatusBadge status={step.mastery_status} label={statusLabel(step.mastery_status)} />
                  </div>
                  <p>{step.action_label}</p>
                  <span className="muted">{step.relation_hint}</span>
                  {step.code_locations.length > 0 && <span className="pill gray">{step.code_locations[0]}</span>}
                </Link>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
