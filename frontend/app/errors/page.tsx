"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bug, ExternalLink } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, SearchInput, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import type { ErrorArchive } from "@/types/api";


export default function ErrorArchivesPage() {
  const [archives, setArchives] = useState<ErrorArchive[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      setArchives(await api.listErrors({ status: status || undefined }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "报错档案加载失败");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return archives;
    return archives.filter((archive) =>
      [archive.title, archive.error_type, archive.error_message, archive.language, archive.tags.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [archives, query]);

  async function updateStatus(archive: ErrorArchive, nextStatus: string) {
    setError("");
    try {
      const updated = await api.updateErrorArchive(archive.id, { status: nextStatus });
      setArchives((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage(`“${archive.error_type}”已更新为${statusLabel(nextStatus)}。`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "状态更新失败");
    }
  }

  return (
    <div className="page">
      <PageHeader
        description="从图片 OCR 文本中提取明确报错类型和消息，保留来源、堆栈片段、可信度和处理状态。系统只记录可验证文本，不虚构根因。"
        eyebrow="知识管理"
        title="报错档案"
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      <section className="grid cols-3">
        <article className="card"><span className="muted">全部记录</span><p className="stat-value">{archives.length}</p></article>
        <article className="card"><span className="muted">待处理</span><p className="stat-value">{archives.filter((item) => item.status === "open").length}</p></article>
        <article className="card"><span className="muted">已解决</span><p className="stat-value">{archives.filter((item) => item.status === "resolved").length}</p></article>
      </section>
      <section className="panel stack">
        <div className="row between wrap">
          <SearchInput onChange={setQuery} placeholder="搜索报错类型、消息、语言或标签" value={query} />
          <select className="select" onChange={(event) => setStatus(event.target.value)} style={{ maxWidth: 170 }} value={status}>
            <option value="">全部状态</option>
            <option value="open">待处理</option>
            <option value="investigating">排查中</option>
            <option value="resolved">已解决</option>
            <option value="ignored">已忽略</option>
          </select>
        </div>
        {filtered.length === 0 ? (
          <EmptyState description="先在图片详情页执行 OCR，再点击“识别并归档报错”。" title="暂无报错档案" />
        ) : (
          <div className="list">
            {filtered.map((archive) => (
              <article className="list-item" key={archive.id}>
                <div className="row between wrap">
                  <div className="row"><Bug size={17} /><strong>{archive.title}</strong></div>
                  <div className="status-line">
                    <StatusBadge status={archive.status} />
                    <span className="pill gray">可信度 {archive.confidence}%</span>
                    <span className="pill gray">严重度 {statusLabel(archive.severity)}</span>
                  </div>
                </div>
                <p className="quote">{archive.error_message}</p>
                <div className="status-line">
                  {archive.language && <span className="pill gray">{archive.language}</span>}
                  {archive.tags.map((tag) => <span className="pill gray" key={tag}>{tag}</span>)}
                  <span className="muted">{formatDate(archive.created_at)}</span>
                </div>
                <div className="row wrap">
                  <select className="select" onChange={(event) => updateStatus(archive, event.target.value)} style={{ maxWidth: 150 }} value={archive.status}>
                    <option value="open">待处理</option>
                    <option value="investigating">排查中</option>
                    <option value="resolved">已解决</option>
                    <option value="ignored">已忽略</option>
                  </select>
                  {archive.source_id && (
                    <Link className="button secondary small" href={`/media/sources/${archive.source_id}`}>
                      <ExternalLink size={14} />查看来源图片
                    </Link>
                  )}
                </div>
                <TechnicalDetails title="堆栈与建议">
                  {archive.stack_excerpt && <pre className="pre-wrap">{archive.stack_excerpt}</pre>}
                  <h3>建议排查步骤</h3>
                  <ol>{archive.suggested_actions.map((action) => <li key={action}>{action}</li>)}</ol>
                </TechnicalDetails>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
