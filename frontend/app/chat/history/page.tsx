"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileQuestion, MessageSquare } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import type { ChatSession, QALog } from "@/types/api";

export default function ChatHistoryPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [history, setHistory] = useState<QALog[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [sessionData, historyData] = await Promise.all([api.listChatSessions(), api.history()]);
      setSessions(sessionData);
      setHistory(historyData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载会话记录失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="AI 助手"
        title="会话记录"
        description="复盘历史问题、回答置信度、引用使用情况和多轮会话，不把调试 payload 暴露给普通用户。"
        action={
          <Link className="button" href="/chat">
            <MessageSquare size={17} />
            继续问答
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      <section className="grid cols-2">
        <div className="panel stack">
          <div className="row">
            <MessageSquare size={18} />
            <h2>多轮会话</h2>
          </div>
          <div className="list">
            {sessions.length === 0 ? (
              <EmptyState title="暂无会话" description="到知识问答页提出第一个问题后，会话会出现在这里。" />
            ) : (
              sessions.map((session) => (
                <article className="list-item" key={session.id}>
                  <div className="row between">
                    <strong>{session.title}</strong>
                    <StatusBadge status={session.is_archived ? "archived" : "ready"} label={session.is_archived ? "已归档" : "进行中"} />
                  </div>
                  <span className="muted">{session.messages.length} 条消息 / {formatDate(session.updated_at)}</span>
                </article>
              ))
            )}
          </div>
        </div>
        <div className="panel stack">
          <div className="row">
            <FileQuestion size={18} />
            <h2>最近问答</h2>
          </div>
          <div className="list">
            {history.length === 0 ? (
              <EmptyState title="暂无问答" description="问答记录会保留检索状态、引用数量和回答置信度，方便复盘。" />
            ) : (
              history.map((qa) => (
                <article className="list-item" key={qa.id}>
                  <div className="row between">
                    <strong>{qa.question}</strong>
                    <span className="pill gray">{statusLabel(qa.retrieval_status)}</span>
                  </div>
                  <p>{qa.answer.slice(0, 180)}</p>
                  <span className="muted">
                    {formatDate(qa.created_at)} / 引用 {qa.used_citation_ids.length} / 置信度 {statusLabel(qa.answer_confidence)}
                  </span>
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
