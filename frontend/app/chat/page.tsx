"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { KnowledgeChat } from "@/components/KnowledgeChat";
import { EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import type { KnowledgeSpace, QALog } from "@/types/api";

function ChatContent() {
  const searchParams = useSearchParams();
  const defaultSpaceId = Number(searchParams.get("space_id") || 0);
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [history, setHistory] = useState<QALog[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [spaceData, historyData] = await Promise.all([api.listSpaces(), api.history(defaultSpaceId || undefined)]);
      setSpaces(spaceData);
      setHistory(historyData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <div className="page">
      <PageHeader eyebrow="AI 助手" title="知识问答" description="选择知识库后连续提问。回答会显示引用来源、检索状态和相关知识片段。" />
      {error && <ErrorState message={error} onRetry={load} />}
      {spaces.length === 0 ? <EmptyState title="还没有知识库" description="先创建知识库并上传资料，再开始问答。" /> : <KnowledgeChat defaultSpaceId={defaultSpaceId || spaces[0]?.id} onAsked={load} spaces={spaces} />}
      <section className="panel">
        <h2>最近问答</h2>
        <div className="list">
          {history.slice(0, 8).map((qa) => (
            <article className="list-item" key={qa.id}>
              <div className="row between"><strong>{qa.question}</strong><span className="pill gray">{statusLabel(qa.retrieval_status)}</span></div>
              <span className="muted">{formatDate(qa.created_at)}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export default function ChatPage() {
  return <Suspense fallback={null}><ChatContent /></Suspense>;
}
