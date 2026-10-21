import { Quote } from "lucide-react";

import { statusLabel } from "@/services/api";
import type { Citation, RelatedChunk } from "@/types/api";
import { SourceLocatorButton } from "@/components/ui";

function timestamp(milliseconds?: number | null) {
  if (milliseconds === null || milliseconds === undefined) return "";
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${String(Math.floor(totalSeconds / 60)).padStart(2, "0")}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

export function CitationPanel({ citations, relatedChunks }: { citations: Citation[]; relatedChunks: RelatedChunk[] }) {
  return (
    <div className="drawer stack" data-testid="citation-panel">
      <div className="row">
        <Quote size={18} />
        <h2>引用来源</h2>
      </div>
      <div className="list">
        {citations.length === 0 ? (
          <p className="muted">这次回答没有可验证引用。</p>
        ) : (
          citations.map((citation) => {
            const href = citationHref(citation);
            return (
              <article className="list-item citation-link" data-testid="citation-card" key={`${citation.citation_id}-${citation.chunk_id}`}>
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
                  {citation.file_path ? ` · ${citation.file_path}${citation.line_start ? `:${citation.line_start}` : ""}` : ""}
                  {citation.source_type ? ` · ${sourceTypeLabel(citation.source_type)}` : ""}
                </p>
                <p className="quote">{citation.content_preview}</p>
                {href ? (
                  <SourceLocatorButton href={href} label="查看并定位来源" testId="citation-source-link" />
                ) : (
                  <p className="muted">无法定位来源：这条引用缺少 source_id、document_id 或 file_path。</p>
                )}
              </article>
            );
          })
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

export function citationHref(citation: Citation) {
  if (citation.file_path) {
    const params = new URLSearchParams();
    params.set("file", citation.file_path);
    if (citation.line_start) params.set("line", String(citation.line_start));
    if (citation.line_end) params.set("line_end", String(citation.line_end));
    if (citation.source_id) params.set("source", String(citation.source_id));
    return `/code?${params.toString()}`;
  }
  if (citation.document_id && !isMediaCitation(citation.source_type)) {
    return documentCitationHref(citation);
  }
  if (citation.source_id) {
    const params = new URLSearchParams();
    if (citation.start_ms !== null && citation.start_ms !== undefined) params.set("t", String(citation.start_ms));
    params.set("chunk", String(citation.chunk_id));
    const query = params.toString();
    return `/media/sources/${citation.source_id}${query ? `?${query}` : ""}`;
  }
  if (citation.document_id) {
    return documentCitationHref(citation);
  }
  return "";
}

function documentCitationHref(citation: Citation): string {
  const params = new URLSearchParams();
  if (citation.page_number) params.set("page", String(citation.page_number));
  if (citation.heading_path) params.set("heading", citation.heading_path);
  params.set("chunk", String(citation.chunk_id));
  return `/documents/${citation.document_id}?${params.toString()}`;
}

function isMediaCitation(sourceType?: string | null): boolean {
  return sourceType === "image" || sourceType === "audio" || sourceType === "video";
}

function sourceTypeLabel(sourceType: string) {
  const labels: Record<string, string> = {
    image: "图片",
    audio: "音频",
    video: "视频",
    pdf: "PDF",
    markdown: "Markdown",
    text: "文本",
    code_repository: "代码仓库",
    code_file: "代码片段",
  };
  return labels[sourceType] || sourceType;
}

