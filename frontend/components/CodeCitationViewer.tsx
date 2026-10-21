"use client";

import { AlertTriangle, Code2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { buildCodeExcerpt, buildPinnedCodeExcerpt, type CodeExcerpt } from "@/modules/code-citation";
import type { ImmutableEvidencePin } from "@/modules/evidence-agent/immutable-evidence";
import { api } from "@/services/api";
import styles from "./CodeCitationViewer.module.css";

export function CodeCitationViewer({
  filePath,
  immutablePin,
  immutablePinError,
  lineEnd,
  lineStart,
  sourceId
}: {
  filePath: string;
  immutablePin?: ImmutableEvidencePin;
  immutablePinError?: string;
  lineEnd: number;
  lineStart: number;
  sourceId: number | null;
}) {
  const [excerpt, setExcerpt] = useState<CodeExcerpt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const pinned = immutablePin !== undefined || immutablePinError !== undefined;
  const pinnedSourceId = immutablePin?.sourceId;
  const pinnedRevisionId = immutablePin?.revisionId;
  const pinnedIndexRevisionId = immutablePin?.indexRevisionId;
  const pinnedChunkId = immutablePin?.chunkId;
  const pinnedContentHash = immutablePin?.contentHash;
  const pinnedRevisionContentHash = immutablePin?.revisionContentHash;

  useEffect(() => {
    let active = true;
    setExcerpt(null);
    setError("");
    if (immutablePinError) {
      setLoading(false);
      setError(immutablePinError);
      return () => {
        active = false;
      };
    }
    if (sourceId === null) {
      setLoading(false);
      setError("这条代码引用缺少 source_id，无法读取固定 revision 的真实代码内容。");
      return () => {
        active = false;
      };
    }

    setLoading(true);
    void api.getCodeRepository(sourceId)
      .then((source) => {
        if (!active) return;
        const completePin = pinnedSourceId && pinnedRevisionId && pinnedChunkId && pinnedContentHash
          ? {
              sourceId: pinnedSourceId,
              revisionId: pinnedRevisionId,
              ...(pinnedIndexRevisionId === undefined ? {} : { indexRevisionId: pinnedIndexRevisionId }),
              chunkId: pinnedChunkId,
              contentHash: pinnedContentHash,
              ...(pinnedRevisionContentHash === undefined ? {} : { revisionContentHash: pinnedRevisionContentHash })
            }
          : null;
        const nextExcerpt = pinned
          ? completePin
            ? buildPinnedCodeExcerpt(source, { pin: completePin, filePath, lineStart, lineEnd })
            : null
          : buildCodeExcerpt(source, filePath, lineStart, lineEnd);
        if (!nextExcerpt) {
          setError(pinned
            ? `Source #${sourceId} 的固定 revision/chunk/hash 校验失败；系统拒绝回退到 active 版本。`
            : `Source #${sourceId} 的当前 revision 中不存在 ${filePath}。`);
          return;
        }
        setExcerpt(nextExcerpt);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "无法加载代码来源。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    filePath,
    immutablePinError,
    lineEnd,
    lineStart,
    pinned,
    pinnedChunkId,
    pinnedContentHash,
    pinnedIndexRevisionId,
    pinnedRevisionContentHash,
    pinnedRevisionId,
    pinnedSourceId,
    reload,
    sourceId
  ]);

  useEffect(() => {
    if (!excerpt?.exact) return;
    const target = document.getElementById(`code-citation-line-${lineStart}`);
    target?.focus({ preventScroll: true });
    target?.scrollIntoView({ behavior: "instant", block: "center" });
  }, [excerpt, lineStart]);

  return (
    <section aria-busy={loading} aria-labelledby="code-citation-heading" className={styles.viewer} data-testid="code-citation-viewer">
      <header className={styles.header}>
        <div className={styles.headingIcon} aria-hidden="true"><Code2 size={20} /></div>
        <div>
          <p>{pinned ? "Code Citation · Immutable Revision" : "Code Citation · Current View"}</p>
          <h2 id="code-citation-heading">{filePath}</h2>
        </div>
      </header>

      {loading ? (
        <div aria-live="polite" className={styles.state} role="status">正在从代码 Source 加载引用片段…</div>
      ) : error ? (
        <div className={styles.error} role="alert">
          <AlertTriangle aria-hidden="true" size={20} />
          <div><strong>代码引用无法定位</strong><span>{error}</span></div>
          <button className="button secondary" onClick={() => setReload((value) => value + 1)} type="button">
            <RefreshCw aria-hidden="true" size={15} /> 重试
          </button>
        </div>
      ) : excerpt ? (
        <>
          <div className={styles.meta}>
            <span>{excerpt.sourceTitle}</span>
            <span>Source {excerpt.sourceId}</span>
            <span>Revision {excerpt.revisionId}</span>
            <span>Chunk {excerpt.chunkId}</span>
            <span>{excerpt.language}</span>
            <span>Lines {lineStart}-{lineEnd}</span>
          </div>
          {excerpt.historical && (
            <p className={styles.staleNotice} role="status">历史固定证据：当前 active revision 已变化，此处仍严格展示 Revision {excerpt.revisionId} / Chunk {excerpt.chunkId}。</p>
          )}
          {!excerpt.exact && (
            <p className={styles.staleNotice} role="status">文件存在，但请求行号不属于当前 revision；下方展示首个真实片段，且不会错误高亮。</p>
          )}
          <div className={styles.codeFrame}>
            <ol aria-label={`${excerpt.filePath} 代码引用`} className={styles.codeList}>
              {excerpt.lines.map((line) => (
                <li
                  aria-current={line.highlighted ? "location" : undefined}
                  aria-label={`第 ${line.number} 行${line.highlighted ? "，引用目标" : ""}`}
                  className={styles.codeLine}
                  data-citation-target={line.highlighted ? "true" : "false"}
                  id={`code-citation-line-${line.number}`}
                  key={line.number}
                  tabIndex={line.number === lineStart && line.highlighted ? -1 : undefined}
                >
                  <span aria-hidden="true" className={styles.lineNumber}>{line.number}</span>
                  <code>{line.text || " "}</code>
                  {line.highlighted && <span className={styles.targetLabel}>引用目标</span>}
                </li>
              ))}
            </ol>
          </div>
        </>
      ) : null}
    </section>
  );
}
