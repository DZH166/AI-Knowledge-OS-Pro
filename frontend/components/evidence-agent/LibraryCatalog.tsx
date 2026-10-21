"use client";

import {
  AlertTriangle,
  ArrowRight,
  AudioLines,
  Code2,
  Database,
  FileText,
  Image as ImageIcon,
  RefreshCw,
  Search,
  ShieldAlert,
  UploadCloud,
  Video
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, formatDate, formatFileSize, statusLabel } from "@/services/api";
import type { KnowledgeSpace, SourceItem } from "@/types/api";
import { sourceArtifactCatalogHref } from "@/modules/evidence-agent/catalog-client";
import { catalogSourceHref } from "@/modules/evidence-agent/source-locator";
import styles from "./EvidenceAgent.module.css";
import { ProductTermHelp } from "./ProductTermHelp";
import {
  RECORDING_SOURCES,
  RECORDING_SPACES,
  activeSourceRevision,
  sourceIndexSummary,
  sourceTitle,
  sourceTypeLabel
} from "./source-presenter";

export function LibraryCatalog() {
  const requestVersion = useRef(0);
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [spaceId, setSpaceId] = useState(0);
  const [sourceType, setSourceType] = useState("");
  const [query, setQuery] = useState("");
  const [recording, setRecording] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const request = ++requestVersion.current;
    setLoading(true);
    setError("");
    try {
      const search = new URLSearchParams(window.location.search);
      const useRecording = search.get("demo") === "1";
      const requestedSource = Number(search.get("source"));
      setRecording(useRecording);
      setSelectedSourceId(Number.isSafeInteger(requestedSource) && requestedSource > 0 ? requestedSource : 0);
      const [spaceData, sourceData] = useRecording
        ? [RECORDING_SPACES, RECORDING_SOURCES]
        : await Promise.all([api.listSpaces(), api.listSources()]);
      if (request !== requestVersion.current) return;
      setSpaces(spaceData);
      setSources(sourceData);
    } catch (reason) {
      if (request !== requestVersion.current) return;
      setError(reason instanceof Error ? reason.message : "无法加载统一来源目录。");
    } finally {
      if (request === requestVersion.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    return () => {
      requestVersion.current += 1;
    };
  }, [load]);

  const spacesById = useMemo(() => new Map(spaces.map((space) => [space.id, space.name])), [spaces]);
  const sourceTypes = useMemo(() => [...new Set(sources.map((source) => source.source_type))].sort(), [sources]);
  const filteredSources = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase();
    return sources.filter((source) => {
      if (spaceId && source.space_id !== spaceId) return false;
      if (selectedSourceId && source.id !== selectedSourceId) return false;
      if (sourceType && source.source_type !== sourceType) return false;
      if (!keyword) return true;
      return [sourceTitle(source), source.original_filename ?? "", source.source_type, spacesById.get(source.space_id) ?? ""]
        .join(" ")
        .toLocaleLowerCase()
        .includes(keyword);
    });
  }, [query, selectedSourceId, sourceType, sources, spaceId, spacesById]);

  const activeCount = sources.filter((source) => source.active_revision_id !== null).length;
  const indexedCount = sources.filter((source) => {
    const revision = activeSourceRevision(source);
    return revision !== null && revision.validation_status === "passed" && revision.vector_count > 0;
  }).length;

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>资料库</p>
          <h1>证据资料库</h1>
          <p className={styles.lead}>在这里查看所有空间和资料来源。每次研究都会固定使用启动时的来源版本，不会随后续更新悄悄变化。</p>
        </div>
        <Link className={styles.primaryAction} href={recording ? "/workbench?demo=1" : "/upload"}>
          <UploadCloud aria-hidden="true" size={17} /> {recording ? "返回演示工作台" : "摄取新来源"}
        </Link>
      </header>

      {recording && (
        <div className={styles.demoBanner} role="status">
          <ShieldAlert aria-hidden="true" size={18} />
          <div>
            <strong>演示资料 · 非真实来源</strong>
            <span>当前目录只读取内置示例资料，不访问生产数据。</span>
          </div>
        </div>
      )}

      <ProductTermHelp terms={["rag", "revision", "evidenceLedger"]} />

      {error && (
        <div className={styles.catalogError} role="alert">
          <AlertTriangle aria-hidden="true" size={20} />
          <div><strong>来源目录加载失败</strong><span>{error}</span></div>
          <button className={styles.quietAction} onClick={() => void load()} type="button">重试</button>
        </div>
      )}

      {loading && sources.length === 0 ? (
        <div aria-live="polite" className={styles.loadingState} role="status"><span>正在读取{recording ? "演示" : "真实"}空间、来源与 revision…</span></div>
      ) : spaces.length === 0 && sources.length === 0 && !error ? (
        <section className={styles.emptyCard}>
          <div>
            <Database aria-hidden="true" size={30} />
            <h2>先创建第一个知识空间</h2>
            <p>每个来源都属于明确空间；创建后即可摄取文档、媒体或代码仓库。</p>
            <Link className={styles.primaryAction} href="/knowledge">创建知识空间</Link>
          </div>
        </section>
      ) : (
        <>
          <section aria-label="来源目录摘要" className={styles.libraryStats}>
            <CatalogStat label="全部来源" value={sources.length} />
            <CatalogStat label="可用版本" value={activeCount} />
            <CatalogStat label="已验证索引" value={indexedCount} />
          </section>

          <section aria-labelledby="source-catalog-heading" className={styles.workspacePanel}>
            <div className={styles.sectionHeading}>
              <div><p className={styles.stepLabel}>资料目录</p><h2 id="source-catalog-heading">来源与索引状态</h2></div>
              <button aria-label="刷新统一来源目录" className={styles.quietAction} disabled={loading} onClick={() => void load()} type="button">
                <RefreshCw aria-hidden="true" size={14} /> 刷新
              </button>
            </div>

            <div className={styles.catalogToolbar}>
              <div className={styles.field}>
                <label htmlFor="library-search">搜索来源</label>
                <div className={styles.searchField}>
                  <Search aria-hidden="true" size={16} />
                  <input
                    autoComplete="off"
                    id="library-search"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="标题、文件名、类型或空间…"
                    type="search"
                    value={query}
                  />
                </div>
              </div>
              <div className={styles.field}>
                <label htmlFor="library-space">知识空间</label>
                <select className={styles.select} id="library-space" onChange={(event) => setSpaceId(Number(event.target.value))} value={spaceId}>
                  <option value={0}>全部空间</option>
                  {spaces.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                </select>
              </div>
              <div className={styles.field}>
                <label htmlFor="library-type">来源类型</label>
                <select className={styles.select} id="library-type" onChange={(event) => setSourceType(event.target.value)} value={sourceType}>
                  <option value="">全部类型</option>
                  {sourceTypes.map((type) => <option key={type} value={type}>{sourceTypeLabel(type)}</option>)}
                </select>
              </div>
            </div>

            {filteredSources.length === 0 ? (
              <div className={styles.scopeEmpty}>
                <UploadCloud aria-hidden="true" size={25} />
                <strong>{sources.length === 0 ? "还没有来源" : "没有符合筛选条件的来源"}</strong>
                <span>{sources.length === 0 ? "摄取第一份资料，建立可追踪 revision 与索引。" : "调整空间、类型或搜索关键词。"}</span>
                {sources.length === 0 && <Link className={styles.quietAction} href={spaceId ? `/upload?space_id=${spaceId}` : "/upload"}>摄取来源</Link>}
              </div>
            ) : (
              <div className={styles.sourceCatalog}>
                {filteredSources.map((source) => (
                  <SourceCatalogCard
                    key={source.id}
                    recording={recording}
                    source={source}
                    spaceName={spacesById.get(source.space_id) ?? `Space #${source.space_id}`}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function CatalogStat({ label, value }: { label: string; value: number }) {
  return <article className={styles.catalogStat}><span>{label}</span><strong>{value}</strong></article>;
}

function SourceCatalogCard({
  recording,
  source,
  spaceName
}: {
  recording: boolean;
  source: SourceItem;
  spaceName: string;
}) {
  const activeRevision = activeSourceRevision(source);
  return (
    <article className={styles.sourceCard}>
      <div className={styles.sourceCardHeading}>
        <span aria-hidden="true" className={styles.sourceIcon}><SourceTypeIcon sourceType={source.source_type} /></span>
        <div><h3>{sourceTitle(source)}</h3><p>{spaceName}</p></div>
        <span className={styles.statusBadge}>{statusLabel(source.status)}</span>
      </div>
      <div className={styles.sourceTags}>
        <span>{sourceTypeLabel(source.source_type)}</span>
        <span>{formatFileSize(source.file_size)}</span>
        <span>来源 {source.id}</span>
      </div>
      <dl className={styles.sourceFacts}>
        <dt>当前版本</dt><dd>{source.active_revision_id ? `版本 ${source.active_revision_id}` : "未激活"}</dd>
        <dt>索引</dt><dd>{sourceIndexSummary(source)}</dd>
        <dt>版本状态</dt><dd>{activeRevision ? statusLabel(activeRevision.status) : "—"}</dd>
        <dt>更新时间</dt><dd>{formatDate(source.updated_at)}</dd>
      </dl>
      <div className={styles.indexCardFooter}>
        <span className={styles.count}>{activeRevision ? `${activeRevision.chunk_count} 个片段 · 研究启动后固定` : "暂不可用于新研究"}</span>
        <div className={styles.actionRow}>
          <Link
            aria-label={`查看 ${sourceTitle(source)} 的派生成果`}
            className={styles.quietAction}
            href={sourceArtifactCatalogHref(source.id, recording)}
          >
            派生成果
          </Link>
          <Link
            className={styles.quietAction}
            href={catalogSourceHref({
              demo: recording,
              documentId: source.document_id,
              sourceId: source.id,
              sourceType: source.source_type
            })}
          >
            查看来源详情 <ArrowRight aria-hidden="true" size={14} />
          </Link>
        </div>
      </div>
    </article>
  );
}

function SourceTypeIcon({ sourceType }: { sourceType: string }) {
  if (sourceType === "image") return <ImageIcon size={20} />;
  if (sourceType === "audio") return <AudioLines size={20} />;
  if (sourceType === "video") return <Video size={20} />;
  if (sourceType === "code" || sourceType === "code_repository") return <Code2 size={20} />;
  return <FileText size={20} />;
}
