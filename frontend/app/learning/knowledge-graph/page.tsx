"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitBranch } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, statusLabel } from "@/services/api";
import type { KnowledgeRelation } from "@/types/api";

export default function KnowledgeGraphPage() {
  const [relations, setRelations] = useState<KnowledgeRelation[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setRelations(await api.knowledgeGraph());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载知识关系失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="学习成长"
        title="知识关系"
        description="从现有知识点和版本学习包派生 prerequisite、related、used_by_project、next_to_learn 关系；当前是轻量关系图，不冒充图数据库。"
        action={
          <Link className="button" href="/learning/roadmap">
            <GitBranch size={17} />
            学习路线
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      <section className="panel stack">
        <h2>关系列表</h2>
        <div className="list">
          {relations.length === 0 ? (
            <EmptyState title="暂无知识关系" description="至少需要两个知识点，或知识点带有项目文件证据，才能派生关系。" />
          ) : (
            relations.map((relation, index) => (
              <article className="list-item" key={`${relation.source_point_id}-${relation.target_point_id}-${relation.relation_type}-${index}`}>
                <div className="row between">
                  <strong>{relation.source_name}</strong>
                  <StatusBadge status="ready" label={statusLabel(relation.relation_type)} />
                </div>
                <p>{relation.target_name ? `${relation.relation_type} -> ${relation.target_name}` : relation.relation_type}</p>
                <span className="muted">{relation.reason}</span>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
