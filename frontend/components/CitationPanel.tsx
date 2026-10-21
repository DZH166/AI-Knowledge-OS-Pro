import { Quote } from "lucide-react";
import Link from "next/link";

import { statusLabel } from "@/services/api";
import type { Citation, RelatedChunk } from "@/types/api";

function timestamp(milliseconds?: number | null) {
  if (milliseconds === null || milliseconds === undefined) return "";
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${String(Math.floor(totalSeconds / 60)).padStart(2, "0")}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

export function CitationPanel({ citations, relatedChunks }: { citations: Citation[]; relatedChunks: RelatedChunk[] }) {
  return (
    <div className="drawer stack">
      <div className="row">
        <Quote size={18} />
        <h2>引用来源</h2>
      </div>
      <div className="list">
        {citations.length === 0 ? (
          <p className="muted">这次回答没有可验证引用。</p>
        ) : (
          citations.map((citation) => (
            <Link className="list-item citation-link" href={citationHref(citation)} key={`${citation.citation_id}-${citation.chunk_id}`}>
              <div className="row between">
                <strong>
                  {citation.citation_id} {citation.document_name}
                </strong>
                <span className="pill">相似度 {citation.score}</span>
              </div>
              <p className="muted">
                chunk #{citation.chunk_index}
                {citation.page_number ? ` · 第 ${citation.page_number} 页` : ""}
                {citation.heading_path ? ` · ${citation.heading_path}` : ""}
                {citation.start_ms !== null && citation.start_ms !== undefined ? ` · ${timestamp(citation.start_ms)}` : ""}
                {citation.source_type ? ` · ${sourceTypeLabel(citation.source_type)}` : ""}
              </p>
              <p className="quote">{citation.content_preview}</p>
              <span className="muted">点击查看并定位来源</span>
            </Link>
          ))
        )}
      </div>
      <section className="stack">
        <h3>相关片段</h3>
        {relatedChunks.slice(0, 3).map((chunk) => (
          <article className="list-item" key={chunk.chunk_id}>
            <div className="row between">
              <strong>{chunk.document_name}</strong>
              <span className="pill gray">{statusLabel("indexed")}</span>
            </div>
            <p className="pre-wrap">{chunk.content}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

function citationHref(citation: Citation) {
  if (citation.source_id) {
    const params = new URLSearchParams();
    if (citation.start_ms !== null && citation.start_ms !== undefined) params.set("t", String(citation.start_ms));
    params.set("chunk", String(citation.chunk_id));
    const query = params.toString();
    return `/media/sources/${citation.source_id}${query ? `?${query}` : ""}`;
  }
  if (citation.document_id) {
    const params = new URLSearchParams();
    if (citation.page_number) params.set("page", String(citation.page_number));
    if (citation.heading_path) params.set("heading", citation.heading_path);
    params.set("chunk", String(citation.chunk_id));
    return `/documents/${citation.document_id}?${params.toString()}`;
  }
  return "/media";
}

function sourceTypeLabel(sourceType: string) {
  const labels: Record<string, string> = {
    image: "图片",
    audio: "音频",
    video: "视频",
    pdf: "PDF",
    markdown: "Markdown",
    text: "文本"
  };
  return labels[sourceType] || sourceType;
}
