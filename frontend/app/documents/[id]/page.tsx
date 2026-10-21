"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MessageSquare, RefreshCw, Trash2 } from "lucide-react";

import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, StatusBadge, TechnicalDetails } from "@/components/ui";
import { parseImmutableEvidencePin, resolveImmutableEvidence } from "@/modules/evidence-agent/immutable-evidence";
import { api, formatDate, formatFileSize } from "@/services/api";
import type { Chunk, DocumentItem, IngestionJob, SourceItem } from "@/types/api";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const documentId = Number(params.id);
  const requestedChunkId = Number(searchParams.get("chunk") || 0);
  const requestedPage = Number(searchParams.get("page") || 0);
  const requestedHeading = searchParams.get("heading") || "";
  const immutablePinState = parseImmutableEvidencePin(searchParams);
  const pinnedSourceId = immutablePinState.mode === "pinned" ? immutablePinState.pin.sourceId : null;
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [pinnedSource, setPinnedSource] = useState<SourceItem | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [doc, chunkData, jobData, sourceData] = await Promise.all([
        api.getDocument(documentId),
        api.getDocumentChunks(documentId),
        api.listIngestionJobs(),
        pinnedSourceId === null ? Promise.resolve(null) : api.getSource(pinnedSourceId)
      ]);
      setDocument(doc);
      setChunks(chunkData);
      setPinnedSource(sourceData);
      setJobs(jobData.filter((job) => job.document_id === documentId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }, [documentId, pinnedSourceId]);
  useEffect(() => { load(); }, [load]);

  const resolvedPin = immutablePinState.mode === "pinned" && pinnedSource
    ? resolveImmutableEvidence(pinnedSource, immutablePinState.pin)
    : null;
  const pinnedDocumentMismatch = immutablePinState.mode === "pinned" && pinnedSource
    && pinnedSource.document_id !== documentId;
  const immutableError = immutablePinState.mode === "invalid"
    ? immutablePinState.error
    : pinnedDocumentMismatch
      ? "固定证据的 source 不属于当前文档。"
      : resolvedPin && !resolvedPin.ok
        ? resolvedPin.error
        : "";
  const pinnedTargetId = resolvedPin?.ok ? resolvedPin.chunk.id : 0;

  useEffect(() => {
    if (pinnedTargetId) {
      window.setTimeout(() => window.document.getElementById(`canonical-chunk-${pinnedTargetId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
      return;
    }
    if (immutablePinState.mode !== "current") return;
    if (!chunks.length) return;
    const target = requestedChunkId
      ? chunks.find((chunk) => chunk.id === requestedChunkId)
      : chunks.find((chunk) => (requestedPage && chunk.page_number === requestedPage) || (requestedHeading && chunk.heading_path === requestedHeading));
    if (!target) return;
    window.setTimeout(() => window.document.getElementById(`chunk-${target.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  }, [chunks, immutablePinState.mode, pinnedTargetId, requestedChunkId, requestedHeading, requestedPage]);

  async function reindex() {
    const result = await api.reindexDocument(documentId);
    setMessage(result.message);
    await load();
  }

  async function remove() {
    const result = await api.deleteDocument(documentId);
    setMessage(result.message);
    setConfirmDelete(false);
  }

  return (
    <div className="page">
      <PageHeader eyebrow="文档详情" title={document?.title || document?.original_filename || "文档"} description="查看文档结构、知识片段、处理任务和索引兼容信息。" action={document && <Link className="button" href={`/chat?space_id=${document.space_id}`}><MessageSquare size={17} />基于它提问</Link>} />
      {error && <ErrorState message={error} onRetry={load} />}
      {!document ? <LoadingSkeleton lines={6} /> : (
        <>
          {message && <span className="pill">{message}</span>}
          {resolvedPin?.ok && (
            <div className="error-state" data-testid="immutable-evidence-banner" role="status">
              <strong>{resolvedPin.historical ? "历史固定证据" : "固定证据"} · Revision {resolvedPin.revision.id} / Chunk {resolvedPin.chunk.id}</strong>
              <span>canonical chunk 与 SHA-256 已校验；即使 active revision 变化，也不会回退到当前文档片段。</span>
            </div>
          )}
          {immutableError && (
            <ErrorState
              impact="未展示任何 current/latest 文档片段，避免把其他版本冒充为引用依据。"
              message="固定文档证据校验失败"
              reason={immutableError}
            />
          )}
          <section className="grid cols-3">
            <article className="card"><h3>处理状态</h3><StatusBadge status={document.processing_status || document.status} /><div className="progress"><span style={{ width: `${document.processing_progress}%` }} /></div></article>
            <article className="card"><h3>文件信息</h3><p>{formatFileSize(document.file_size)} · {document.file_type.toUpperCase()}</p><p className="muted">{formatDate(document.created_at)}</p></article>
            <article className="card"><h3>索引信息</h3><p>{document.chunk_count} 个片段</p><p className="muted">{document.index_version || "未建立索引"}</p></article>
          </section>
          <section className="panel stack">
            <div className="row between"><h2>概览</h2><div className="row"><button className="button secondary small" onClick={reindex} type="button"><RefreshCw size={14} />重建索引</button><button className="button danger small" onClick={() => setConfirmDelete(true)} type="button"><Trash2 size={14} />删除</button></div></div>
            {confirmDelete && <div className="error-state"><strong>确认删除这份文档？</strong><span>会同时删除原文件、chunks 和 Qdrant points。</span><div className="row"><button className="button danger small" onClick={remove} type="button">确认删除</button><button className="button secondary small" onClick={() => setConfirmDelete(false)} type="button">取消</button></div></div>}
            <p className="lead">{document.summary || "暂无摘要。"}</p>
            {document.error_message && <span className="pill rose">{document.error_message}</span>}
            <TechnicalDetails>
              <p>Embedding: {document.embedding_provider || "未记录"} / {document.embedding_model || "未记录"} / {document.embedding_dimensions || "-"} 维</p>
              <p>Fingerprint: {document.embedding_fingerprint || "未记录"}</p>
            </TechnicalDetails>
          </section>
          <section className="grid cols-2">
            <div className="panel">
              <h2>内容结构</h2>
              <div className="list">
                {immutablePinState.mode === "pinned"
                  ? resolvedPin?.ok && resolvedPin.revision.chunks.slice(0, 12).map((chunk) => (
                      <div className="list-item" key={chunk.id}>
                        <strong>{chunk.page_number ? `第 ${chunk.page_number} 页` : `canonical chunk ${chunk.chunk_index}`}</strong>
                        <span className="muted">Revision {resolvedPin.revision.id} · chunk #{chunk.chunk_index}</span>
                      </div>
                    ))
                  : chunks.filter((chunk) => chunk.heading_path || chunk.page_number).slice(0, 12).map((chunk) => (
                      <div className="list-item" key={chunk.id}><strong>{chunk.heading_path || `第 ${chunk.page_number} 页`}</strong><span className="muted">chunk #{chunk.chunk_index}</span></div>
                    ))}
              </div>
            </div>
            <div className="panel">
              <h2>处理记录</h2>
              <div className="list">
                {jobs.map((job) => <div className="list-item" key={job.id}><div className="row between"><strong>任务 #{job.id}</strong><StatusBadge status={job.status} /></div><span className="muted">{job.message || job.error_message}</span></div>)}
              </div>
            </div>
          </section>
          <section className="panel">
            <h2>{immutablePinState.mode === "pinned" ? "固定 canonical 片段" : "知识片段"}</h2>
            {immutablePinState.mode === "pinned" ? (
              resolvedPin?.ok ? (
                <div className="list">
                  {resolvedPin.revision.chunks.map((chunk) => (
                    <article
                      className={`list-item ${chunk.id === resolvedPin.chunk.id ? "citation-target" : ""}`}
                      id={`canonical-chunk-${chunk.id}`}
                      key={chunk.id}
                    >
                      <div className="row between">
                        <strong>canonical chunk #{chunk.chunk_index}</strong>
                        <span className="muted">Revision {resolvedPin.revision.id}{chunk.page_number ? ` · 第 ${chunk.page_number} 页` : ""}</span>
                      </div>
                      <p className="pre-wrap">{chunk.content_text}</p>
                      <span className="muted">SHA-256 {chunk.content_hash}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState title="固定证据不可用" description="校验失败后不会显示 legacy active chunks。" />
              )
            ) : chunks.length === 0 ? <EmptyState title="暂无片段" description="文档处理完成后会在这里展示切分结果。" /> : (
              <div className="list">
                {chunks.map((chunk) => (
                  <article className={`list-item ${chunk.id === requestedChunkId ? "citation-target" : ""}`} id={`chunk-${chunk.id}`} key={chunk.id}>
                    <div className="row between"><strong>chunk #{chunk.chunk_index}</strong><span className="muted">{chunk.page_number ? `第 ${chunk.page_number} 页` : chunk.heading_path || ""}</span></div>
                    <p className="pre-wrap">{chunk.content}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
