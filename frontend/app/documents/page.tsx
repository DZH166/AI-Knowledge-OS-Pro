"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RefreshCw, Tags, Trash2, UploadCloud } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, SearchInput, StatusBadge } from "@/components/ui";
import { api, formatDate, formatFileSize, statusLabel } from "@/services/api";
import type { DocumentItem } from "@/types/api";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [tagInput, setTagInput] = useState("");

  async function load() {
    setError("");
    try { setDocuments(await api.listDocuments()); } catch (exc) { setError(exc instanceof Error ? exc.message : "加载失败"); }
  }
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => documents.filter((document) => {
    const matchesQuery = [document.original_filename, document.title, document.summary, document.tags.join(" ")].join(" ").toLowerCase().includes(query.toLowerCase());
    const matchesStatus = status ? document.processing_status === status || document.status === status : true;
    return matchesQuery && matchesStatus;
  }), [documents, query, status]);

  async function bulkDelete() {
    if (selected.length === 0) return;
    const result = await api.bulkDeleteDocuments(selected);
    setMessage(result.message);
    setSelected([]);
    setConfirmingDelete(false);
    await load();
  }

  async function bulkReindex() {
    if (selected.length === 0) return;
    const result = await api.bulkReindexDocuments(selected);
    setMessage(result.message);
    await load();
  }

  async function bulkTags() {
    if (selected.length === 0) return;
    const tags = tagInput.split(",").map((item) => item.trim()).filter(Boolean);
    if (!tags.length) return;
    const result = await api.bulkTags(selected, tags);
    setMessage(result.message);
    setTagInput("");
    await load();
  }

  return (
    <div className="page">
      <PageHeader eyebrow="知识管理" title="文档管理" description="搜索、筛选、批量处理资料，查看每份文档的解析状态和索引状态。" action={<Link className="button" href="/upload"><UploadCloud size={17} />上传资料</Link>} />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      <section className="panel stack">
        <div className="row between wrap">
          <SearchInput onChange={setQuery} placeholder="搜索文件名、摘要或标签" value={query} />
          <select className="select" onChange={(event) => setStatus(event.target.value)} style={{ maxWidth: 180 }} value={status}>
            <option value="">全部状态</option>
            <option value="ready">可以使用</option>
            <option value="queued">等待处理</option>
            <option value="running">处理中</option>
            <option value="failed">处理失败</option>
          </select>
        </div>
        <div className="row wrap">
          <button className="button secondary small" disabled={!selected.length} onClick={bulkReindex} type="button"><RefreshCw size={14} />批量重建索引</button>
          <input className="input" onChange={(event) => setTagInput(event.target.value)} placeholder="标签，用逗号分隔" style={{ maxWidth: 220 }} value={tagInput} />
          <button className="button secondary small" disabled={!selected.length || !tagInput.trim()} onClick={bulkTags} type="button"><Tags size={14} />批量标签</button>
          <button className="button danger small" disabled={!selected.length} onClick={() => setConfirmingDelete(true)} type="button"><Trash2 size={14} />批量删除</button>
        </div>
        {confirmingDelete && (
          <div className="error-state">
            <strong>确认删除 {selected.length} 个文档？</strong>
            <span>该操作会删除原文件、chunks 和 Qdrant points。</span>
            <div className="row"><button className="button danger small" onClick={bulkDelete} type="button">确认删除</button><button className="button secondary small" onClick={() => setConfirmingDelete(false)} type="button">取消</button></div>
          </div>
        )}
        {filtered.length === 0 ? <EmptyState title="没有匹配文档" description="调整筛选条件，或上传新的学习资料。" /> : (
          <table className="table">
            <thead><tr><th></th><th>文档</th><th>状态</th><th>大小</th><th>片段</th><th>时间</th></tr></thead>
            <tbody>
              {filtered.map((document) => (
                <tr key={document.id}>
                  <td><input checked={selected.includes(document.id)} onChange={(event) => setSelected((old) => event.target.checked ? [...old, document.id] : old.filter((id) => id !== document.id))} type="checkbox" /></td>
                  <td><Link href={`/documents/${document.id}`}><strong>{document.title || document.original_filename}</strong><br /><span className="muted">{document.original_filename}</span></Link></td>
                  <td><StatusBadge status={document.processing_status || document.status} label={statusLabel(document.processing_status || document.status)} /></td>
                  <td>{formatFileSize(document.file_size)}</td>
                  <td>{document.chunk_count}</td>
                  <td>{formatDate(document.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
