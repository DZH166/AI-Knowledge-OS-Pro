"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AudioLines, Image as ImageIcon, Search, UploadCloud, Video } from "lucide-react";

import { EmptyState, ErrorState, PageHeader, SearchInput, StatusBadge } from "@/components/ui";
import { api, formatDate, formatDuration, formatFileSize } from "@/services/api";
import type { KnowledgeSpace, SourceItem } from "@/types/api";

function readMetadata(source: SourceItem): Record<string, unknown> {
  try {
    const parsed = JSON.parse(source.metadata_json || "{}");
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function metadataText(value: unknown, fallback = "未记录") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export default function MediaLibraryPage() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [query, setQuery] = useState("");
  const [spaceId, setSpaceId] = useState(0);
  const [sourceType, setSourceType] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [sourceData, spaceData] = await Promise.all([
        api.listSources(spaceId || undefined, sourceType || undefined),
        api.listSpaces()
      ]);
      setSources(sourceData);
      setSpaces(spaceData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "媒体资料加载失败");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId, sourceType]);

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return sources;
    return sources.filter((source) =>
      [
        source.title,
        source.original_filename,
        source.source_type,
        source.mime_type,
        metadataText(readMetadata(source).capability_note, "")
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [query, sources]);

  const imageCount = sources.filter((source) => source.source_type === "image").length;
  const audioCount = sources.filter((source) => source.source_type === "audio").length;
  const videoCount = sources.filter((source) => source.source_type === "video").length;
  const totalSize = sources.reduce((sum, source) => sum + source.file_size, 0);

  return (
    <div className="page">
      <PageHeader
        action={
          <Link className="button" href="/upload">
            <UploadCloud size={17} />
            上传资料
          </Link>
        }
        description="统一查看图片、音频、视频等多模态资料来源。视频支持真实元数据、关键帧、播放器和配置真实 provider 后的时间戳转写。"
        eyebrow="知识管理"
        title="媒体资料库"
      />
      {error && <ErrorState message={error} onRetry={load} />}
      <section className="grid cols-4">
        <article className="card">
          <span className="muted">资料来源</span>
          <p className="stat-value">{sources.length}</p>
        </article>
        <article className="card">
          <span className="muted">图片资料</span>
          <p className="stat-value">{imageCount}</p>
        </article>
        <article className="card">
          <span className="muted">音频资料</span>
          <p className="stat-value">{audioCount}</p>
        </article>
        <article className="card">
          <span className="muted">视频资料</span>
          <p className="stat-value">{videoCount}</p>
        </article>
      </section>
      <section className="grid cols-1">
        <article className="card">
          <span className="muted">累计大小</span>
          <p className="stat-value">{formatFileSize(totalSize)}</p>
        </article>
      </section>
      <section className="panel stack">
        <div className="row between wrap">
          <SearchInput onChange={setQuery} placeholder="搜索标题、文件名、类型或能力说明" value={query} />
          <div className="row wrap">
            <select className="select" onChange={(event) => setSpaceId(Number(event.target.value))} style={{ maxWidth: 210 }} value={spaceId}>
              <option value={0}>全部知识库</option>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </select>
            <select className="select" onChange={(event) => setSourceType(event.target.value)} style={{ maxWidth: 160 }} value={sourceType}>
              <option value="">全部类型</option>
              <option value="image">图片</option>
              <option value="audio">音频</option>
              <option value="video">视频</option>
            </select>
          </div>
        </div>
        {filtered.length === 0 ? (
          <EmptyState
            action={
              <Link className="button secondary" href="/upload">
                <Search size={16} />
                去上传资料
              </Link>
            }
            description="上传图片、音频或视频后，这里会展示真实尺寸、时长、文件大小和处理能力边界。"
            title="暂无媒体资料"
          />
        ) : (
          <div className="media-grid">
            {filtered.map((source) => {
              const metadata = readMetadata(source);
              const capability = metadataText(metadata.capability_note, "已保存来源记录。");
              const PreviewIcon = source.source_type === "video" ? Video : source.source_type === "audio" ? AudioLines : ImageIcon;
              return (
                <Link className="media-card" href={`/media/sources/${source.id}`} key={source.id}>
                  <div className="media-card-preview">
                    <PreviewIcon size={34} />
                  </div>
                  <div className="stack">
                    <div className="row between">
                      <strong>{source.title || source.original_filename || `资料 #${source.id}`}</strong>
                      <StatusBadge status={source.status} />
                    </div>
                    <span className="muted">{source.original_filename || "未记录文件名"}</span>
                    <div className="status-line">
                      <span className="pill gray">{source.source_type}</span>
                      {source.width && source.height ? <span className="pill gray">{source.width} x {source.height}</span> : null}
                      {source.duration_ms ? <span className="pill gray">{formatDuration(source.duration_ms)}</span> : null}
                      <span className="pill gray">{formatFileSize(source.file_size)}</span>
                    </div>
                    <p className="muted">{capability}</p>
                    <span className="muted">{formatDate(source.created_at)}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
