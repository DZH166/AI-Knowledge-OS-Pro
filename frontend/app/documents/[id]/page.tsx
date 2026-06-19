"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MessageSquare, RefreshCw, Trash2 } from "lucide-react";

import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api, formatDate, formatFileSize } from "@/services/api";
import type { Chunk, DocumentItem, IngestionJob } from "@/types/api";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const documentId = Number(params.id);
  const requestedChunkId = Number(searchParams.get("chunk") || 0);
  const requestedPage = Number(searchParams.get("page") || 0);
  const requestedHeading = searchParams.get("heading") || "";
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function load() {
    setError("");
    try {
      const [doc, chunkData, jobData] = await Promise.all([api.getDocument(documentId), api.getDocumentChunks(documentId), api.listIngestionJobs()]);
      setDocument(doc);
      setChunks(chunkData);
      setJobs(jobData.filter((job) => job.document_id === documentId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }
  useEffect(() => { load(); }, [documentId]);

  useEffect(() => {
    if (!chunks.length) return;
    const target = requestedChunkId
      ? chunks.find((chunk) => chunk.id === requestedChunkId)
      : chunks.find((chunk) => (requestedPage && chunk.page_number === requestedPage) || (requestedHeading && chunk.heading_path === requestedHeading));
    if (!target) return;
    window.setTimeout(() => window.document.getElementById(`chunk-${target.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  }, [chunks, requestedChunkId, requestedHeading, requestedPage]);

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
                {chunks.filter((chunk) => chunk.heading_path || chunk.page_number).slice(0, 12).map((chunk) => (
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
            <h2>知识片段</h2>
            {chunks.length === 0 ? <EmptyState title="暂无片段" description="文档处理完成后会在这里展示切分结果。" /> : (
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
