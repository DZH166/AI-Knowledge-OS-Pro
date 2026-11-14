"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Code2, FolderOpen, ShieldCheck } from "lucide-react";

import { CodeCitationViewer } from "@/components/CodeCitationViewer";
import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { listCodeLocations } from "@/modules/code-citation";
import { parseImmutableEvidencePin } from "@/modules/evidence-agent/immutable-evidence";
import { sourceTypeLabel } from "@/components/evidence-agent/source-presenter";
import { api, formatDate, statusLabel } from "@/services/api";
import type { KnowledgeSpace, SourceItem } from "@/types/api";

function metadata(source: SourceItem) {
  try {
    const parsed = JSON.parse(source.metadata_json || "{}");
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function numberMeta(source: SourceItem, key: string) {
  const value = metadata(source)[key];
  return typeof value === "number" ? value : 0;
}

function CodeRepositoryContent() {
  const searchParams = useSearchParams();
  const citationFile = searchParams.get("file") || "";
  const citationLine = positiveInteger(searchParams.get("line"), 1);
  const citationLineEnd = Math.max(citationLine, positiveInteger(searchParams.get("line_end"), citationLine));
  const citationSource = positiveInteger(searchParams.get("source"), 0) || null;
  const immutablePinState = parseImmutableEvidencePin(searchParams);
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [repositories, setRepositories] = useState<SourceItem[]>([]);
  const [spaceId, setSpaceId] = useState(0);
  const [localPath, setLocalPath] = useState("");
  const [title, setTitle] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [maxFiles, setMaxFiles] = useState(80);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [spaceData, repoData, selectedSource] = await Promise.all([
        api.listSpaces(),
        api.listCodeRepositories(),
        citationSource ? api.getCodeRepository(citationSource) : Promise.resolve(null)
      ]);
      setSpaces(spaceData);
      setRepositories(selectedSource
        ? [selectedSource, ...repoData.filter((repository) => repository.id !== selectedSource.id)]
        : repoData);
      setSpaceId(spaceData[0]?.id || 0);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载代码仓库失败。");
    }
  }, [citationSource]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedRepository = citationSource
    ? repositories.find((repository) => repository.id === citationSource) ?? null
    : null;

  async function ingestRepository() {
    if (!spaceId || !localPath.trim()) {
      setError("请选择知识库并填写本地代码仓库路径。");
      return;
    }
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const result = await api.ingestCodeRepository({
        space_id: spaceId,
        local_path: localPath.trim(),
        title: title.trim() || undefined,
        github_url: githubUrl.trim() || undefined,
        max_files: maxFiles
      });
      setRepositories((old) => [result.source, ...old.filter((repo) => repo.id !== result.source.id)]);
      setMessage(`${result.message} 文件 ${result.file_count}，片段 ${result.chunk_count}，跳过 ${result.skipped_count}。`);
      setTitle("");
      setGithubUrl("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "代码仓库接入失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="知识管理"
        title="代码仓库接入"
        description="读取本地代码仓库，按安全白名单跳过 .env、数据库、媒体、构建产物和依赖目录，生成带 file_path 与行号的可检索代码片段。缺少 Embedding 时返回 EMBEDDING_NOT_CONFIGURED。"
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      {citationFile && (
        <CodeCitationViewer
          filePath={citationFile}
          immutablePin={immutablePinState.mode === "pinned" ? immutablePinState.pin : undefined}
          immutablePinError={immutablePinState.mode === "invalid" ? immutablePinState.error : undefined}
          lineEnd={citationLineEnd}
          lineStart={citationLine}
          sourceId={citationSource}
        />
      )}
      {selectedRepository && !citationFile && <CodeSourceDetail source={selectedRepository} />}

      {spaces.length === 0 ? (
        <EmptyState
          action={<Link className="button" href="/knowledge">创建知识库</Link>}
          description="代码仓库也需要归属到一个知识库空间，才能进入 RAG 和学习系统。"
          title="请先创建知识库"
        />
      ) : (
        <section className="grid cols-2">
          <article className="panel stack">
            <div className="row">
              <FolderOpen size={18} />
              <h2>本地仓库扫描</h2>
            </div>
            <select className="select" onChange={(event) => setSpaceId(Number(event.target.value))} value={spaceId}>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>{space.name}</option>
              ))}
            </select>
            <input className="input" onChange={(event) => setLocalPath(event.target.value)} placeholder="本地仓库绝对路径" value={localPath} />
            <input className="input" onChange={(event) => setTitle(event.target.value)} placeholder="项目标题，可选" value={title} />
            <input className="input" onChange={(event) => setGithubUrl(event.target.value)} placeholder="GitHub URL，可选，仅记录来源" value={githubUrl} />
            <label className="field-label">
              最大文件数
              <input className="input" max={300} min={1} onChange={(event) => setMaxFiles(Number(event.target.value))} type="number" value={maxFiles} />
            </label>
            <button className="button" disabled={busy} onClick={ingestRepository} type="button">
              {busy ? <ButtonLoading label="扫描中" /> : <><Code2 size={17} />接入代码仓库</>}
            </button>
            <p className="quote">当前版本不复制代码文件，只保存安全白名单文本片段、相对路径、行号和索引信息。</p>
          </article>

          <article className="panel stack">
            <div className="row">
              <ShieldCheck size={18} />
              <h2>安全边界</h2>
            </div>
            <div className="list">
              <article className="list-item">跳过 `.env`、数据库、上传目录、日志、缓存、node_modules、.git 和构建产物。</article>
              <article className="list-item">只读取 UTF-8 文本和代码白名单扩展名，过大文件与二进制文件会被跳过。</article>
              <article className="list-item">真实索引依赖 Embedding provider；未配置时不生成假向量。</article>
            </div>
          </article>
        </section>
      )}

      <section className="panel stack">
        <h2>已接入代码仓库</h2>
        <div className="list">
          {repositories.length === 0 ? (
            <EmptyState title="暂无代码仓库" description="接入当前项目或练习项目后，可用于项目复盘、代码问答、简历表达和面试讲解。" />
          ) : (
            repositories.map((repo) => (
              <Link className="list-item" href={`/media/sources/${repo.id}`} key={repo.id}>
                <div className="row between">
                  <strong>{repo.title || repo.original_filename}</strong>
                  <StatusBadge status={repo.status} label={statusLabel(repo.status)} />
                </div>
                <p>文件 {numberMeta(repo, "file_count")} / 片段 {numberMeta(repo, "chunk_count")} / 跳过 {numberMeta(repo, "skipped_count")}</p>
                <span className="muted">{formatDate(repo.created_at)}</span>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

export function CodeSourceDetail({ source }: { source: SourceItem }) {
  const locations = listCodeLocations(source);
  return (
    <section className="panel stack" data-testid="code-source-detail">
      <div className="row between">
        <div>
          <span className="pill">{sourceTypeLabel(source.source_type)}</span>
          <h2>{source.title || source.original_filename || `Source #${source.id}`}</h2>
        </div>
        <StatusBadge label={statusLabel(source.status)} status={source.status} />
      </div>
      <p className="muted">Source {source.id} · Active Revision {source.active_revision_id ?? "—"} · {locations.length} 个可定位代码片段</p>
      {locations.length ? (
        <div className="list">
          {locations.map((location) => {
            const params = new URLSearchParams({
              source: String(source.id),
              file: location.filePath,
              line: String(location.lineStart),
              line_end: String(location.lineEnd)
            });
            return (
              <Link className="list-item" href={`/code?${params.toString()}`} key={`${location.chunkId}:${location.filePath}:${location.lineStart}`}>
                <strong>{location.filePath}</strong>
                <span className="muted">Revision {location.revisionId} · Lines {location.lineStart}-{location.lineEnd} · {location.language}</span>
              </Link>
            );
          })}
        </div>
      ) : (
        <p className="quote">该 active revision 暂无可定位代码片段；系统不会用其他文件替代。</p>
      )}
    </section>
  );
}

function positiveInteger(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export default function CodeRepositoryPage() {
  return (
    <Suspense fallback={<div className="page" />}>
      <CodeRepositoryContent />
    </Suspense>
  );
}
