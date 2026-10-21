"use client";

import { useCallback, useEffect, useId, useState } from "react";
import Link from "next/link";
import { FileText, RotateCcw, TimerReset, UploadCloud, X } from "lucide-react";

import { ButtonLoading, EmptyState, StatusBadge } from "@/components/ui";
import { ApiRequestError, api, formatFileSize } from "@/services/api";
import type { DocumentItem, IngestionJob, KnowledgeSpace } from "@/types/api";
import { workbenchJourneyHref } from "@/modules/evidence-agent/research-journey";
import styles from "./DocumentUploader.module.css";

type QueueItem = {
  id: string;
  file: File;
  document?: DocumentItem;
  job?: IngestionJob;
  status: "ready" | "uploading" | "processing" | "done" | "failed";
  error?: string;
  pollError?: string;
  existingDocumentId?: number;
};

const steps = [
  { key: "queued", label: "等待处理" }, { key: "parsing", label: "解析内容" },
  { key: "chunking", label: "切分片段" }, { key: "embedding", label: "生成向量" },
  { key: "indexing", label: "写入索引" }, { key: "completed", label: "完成" }
];
const supported = [".txt", ".md", ".pdf"];

export function DocumentUploader({
  spaces,
  defaultSpaceId,
  onUploaded,
  comparisonMode = false
}: {
  spaces: KnowledgeSpace[];
  defaultSpaceId?: number;
  onUploaded: (document: DocumentItem) => void;
  comparisonMode?: boolean;
}) {
  const [spaceId, setSpaceId] = useState<number>(defaultSpaceId || spaces[0]?.id || 0);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const fileInputId = useId();

  useEffect(() => {
    if (comparisonMode && defaultSpaceId && spaces.some((space) => space.id === defaultSpaceId)) {
      setSpaceId(defaultSpaceId);
    }
  }, [comparisonMode, defaultSpaceId, spaces]);

  const applyStatusUpdates = useCallback((updates: Array<UploadStatusUpdate | null>) => {
    setQueue((old) => old.map((item) => {
      const update = updates.find((entry) => entry?.id === item.id && entry.previousJob === item.job);
      if (!update) return item;
      if (!update.job) return { ...item, pollError: update.pollError };
      const done = update.job.status === "completed";
      const failed = ["failed", "cancelled", "interrupted"].includes(update.job.status);
      return { ...item, job: update.job, status: done ? "done" : failed ? "failed" : "processing",
        pollError: undefined, error: failed ? update.job.error_message || update.job.message || "处理失败" : undefined };
    }));
  }, []);

  useEffect(() => {
    const running = queue.filter((item) => item.job && item.status === "processing");
    if (running.length === 0) return;
    let active = true;
    let reading = false;
    const timer = window.setInterval(async () => {
      if (reading) return;
      reading = true;
      try {
        const updates = await Promise.all(running.map(readJobStatus));
        if (active) applyStatusUpdates(updates);
      } finally { reading = false; }
    }, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [queue, applyStatusUpdates]);

  async function refreshStatus(item: QueueItem) {
    setRefreshingId(item.id);
    try { applyStatusUpdates([await readJobStatus(item)]); }
    finally { setRefreshingId(null); }
  }

  function addFiles(files: FileList | File[]) {
    const next = Array.from(files).map((file) => {
      const supportedFile = supported.some((suffix) => file.name.toLowerCase().endsWith(suffix));
      return {
        id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        status: supportedFile ? "ready" : "failed",
        error: supportedFile ? undefined : "暂不支持该格式"
      } satisfies QueueItem;
    });
    setQueue((old) => [...old, ...next]);
  }

  async function uploadAll() {
    if (!spaceId) return;
    setIsUploading(true);
    for (const item of queue) {
      if (item.status !== "ready") continue;
      setQueue((old) => old.map((entry) => (entry.id === item.id ? { ...entry, status: "uploading", error: undefined } : entry)));
      try {
        const result = await api.uploadDocument(spaceId, item.file);
        onUploaded(result.document);
        const job = result.job_id ? createQueuedJob(result.job_id, result.document, result.message) : undefined;
        setQueue((old) =>
          old.map((entry) =>
            entry.id === item.id
              ? {
                  ...entry,
                  document: result.document,
                  job,
                  status: job ? "processing" : "done"
                }
              : entry
          )
        );
      } catch (exc) {
        const duplicate = exc instanceof ApiRequestError && exc.code === "DUPLICATE_DOCUMENT";
        const existingDocumentId = duplicate && typeof exc.details.document_id === "number" ? exc.details.document_id : undefined;
        setQueue((old) =>
          old.map((entry) =>
            entry.id === item.id
              ? {
                  ...entry,
                  status: "failed",
                  error: duplicate ? "该资料已存在，未创建重复记录。请查看原资料状态。" : exc instanceof Error ? exc.message : "上传失败",
                  existingDocumentId
                }
              : entry
          )
        );
      }
    }
    setIsUploading(false);
  }

  async function retry(item: QueueItem) {
    setRetryingId(item.id);
    try {
      if (item.existingDocumentId) {
        const result = await api.reparseDocument(item.existingDocumentId);
        const job = createQueuedJob(result.job_id, result.document, result.message);
        setQueue((old) => old.map((entry) => (entry.id === item.id ? { ...entry, document: result.document, job, existingDocumentId: undefined, status: "processing", error: undefined } : entry)));
      } else if (item.job) {
        const job = await api.retryIngestionJob(item.job.id);
        setQueue((old) => old.map((entry) => (entry.id === item.id ? { ...entry, job, status: "processing", error: undefined } : entry)));
      } else {
        setQueue((old) => old.map((entry) => (entry.id === item.id ? { ...entry, status: "ready", error: undefined } : entry)));
      }
    } catch (exc) {
      setQueue((old) => old.map((entry) => (entry.id === item.id ? { ...entry, error: exc instanceof Error ? exc.message : "重新处理失败" } : entry)));
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <section className="panel stack">
      <div className="row between">
        <h2>资料接入中心</h2>
        <button className="button secondary small" onClick={() => setQueue([])} type="button">
          <X size={14} />
          清空队列
        </button>
      </div>
      <div className="field">
        <label htmlFor="space">{comparisonMode ? "本次研究的知识空间" : "目标知识库"}</label>
        <select className="select" disabled={comparisonMode && Boolean(defaultSpaceId)} id="space" onChange={(event) => setSpaceId(Number(event.target.value))} value={spaceId}>
          {spaces.map((space) => (
            <option key={space.id} value={space.id}>
              {space.name}
            </option>
          ))}
        </select>
        {comparisonMode && defaultSpaceId ? <small className="muted">对比研究会继续使用这个空间，避免资料传入别的知识库。</small> : null}
      </div>
      <label className={`dropzone ${styles.dropZone}`} htmlFor={fileInputId}
        onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; }}
        onDrop={(event) => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
        <UploadCloud aria-hidden="true" size={26} />
        <strong>拖拽或点击选择 txt / md / pdf</strong>
        <span className="muted">{comparisonMode
          ? "上传后还需等待处理和索引完成；只有建立有效版本的资料才能用于研究。扫描版 PDF 需要真实 OCR 服务。"
          : "单文件上限由后端配置控制；扫描版 PDF 暂不做 OCR，V3 会继续扩展多模态解析。"}</span>
        <input accept=".txt,.md,.pdf" aria-label="选择文档文件" className={styles.fileInput} id={fileInputId} multiple
          onChange={(event) => { if (event.currentTarget.files) addFiles(event.currentTarget.files); event.currentTarget.value = ""; }} type="file" />
      </label>
      {queue.length === 0 ? (
        <EmptyState title="队列为空" description="选择一个或多个文件后，系统会逐个创建处理任务并显示进度。" />
      ) : (
        <div className="list">
          {queue.map((item) => (
            <article className="list-item" key={item.id}>
              <div className="row between">
                <div className="row">
                  <FileText size={16} />
                  <strong>{item.file.name}</strong>
                  <span className="muted">{formatFileSize(item.file.size)}</span>
                </div>
                <StatusBadge status={item.job?.status || item.status} />
              </div>
              {item.job && <DocumentUploadProgress job={item.job} pollError={item.pollError}
                refreshing={refreshingId === item.id} onRefresh={() => void refreshStatus(item)} />}
              <progress aria-label={`${item.file.name} 的处理进度`} className={styles.progress} max={100}
                value={item.job ? item.job.status === "completed" ? 100 : Math.max(0, Math.min(100, item.job.progress))
                  : item.status === "uploading" ? undefined : item.status === "done" ? 100 : 0} />
              {item.error && <span className="pill rose">{item.error}</span>}
              <div className="row wrap">
                {item.document && (
                  <Link className="button secondary small" href={`/documents/${item.document.id}`}>
                    查看文档
                  </Link>
                )}
                {item.document && (
                  <Link className="button secondary small" href={comparisonMode
                    ? workbenchJourneyHref({ recording: false, comparison: true, spaceId: item.document.space_id })
                    : `/chat?space_id=${item.document.space_id}`}>
                    {comparisonMode ? "返回对比工作台" : "开始提问"}
                  </Link>
                )}
                {item.existingDocumentId && (
                  <Link className="button secondary small" href={`/documents/${item.existingDocumentId}`}>
                    查看原资料
                  </Link>
                )}
                {item.existingDocumentId && (
                  <button className="button secondary small" disabled={retryingId === item.id} onClick={() => retry(item)} type="button">
                    {retryingId === item.id ? <ButtonLoading label="处理中" /> : <><RotateCcw size={14} />重新处理</>}
                  </button>
                )}
                {item.job && (
                  <Link className="button secondary small" href="/tasks">
                    <TimerReset size={14} />
                    查看任务
                  </Link>
                )}
                {item.status === "failed" && supported.some((suffix) => item.file.name.toLowerCase().endsWith(suffix)) && (
                  <button className="button secondary small" disabled={retryingId === item.id} onClick={() => retry(item)} type="button">
                    {retryingId === item.id ? <ButtonLoading label="处理中" /> : <><RotateCcw size={14} />重试</>}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      <button className="button" disabled={!spaceId || queue.every((item) => item.status !== "ready") || isUploading} onClick={uploadAll} type="button">
        {isUploading ? (
          <ButtonLoading label="上传中" />
        ) : (
          <>
            <UploadCloud size={17} />
            开始上传
          </>
        )}
      </button>
    </section>
  );
}

export function DocumentUploadProgress({ job, pollError, onRefresh, refreshing = false }: {
  job: Pick<IngestionJob, "progress" | "current_step" | "status">;
  pollError?: string; onRefresh?: () => void; refreshing?: boolean;
}) {
  const stage = job.status === "completed" ? "completed" : job.status === "queued" ? "queued" : job.current_step;
  const active = steps.findIndex((step) => step.key === stage);
  return <div>
    <p role="status">处理阶段：{steps[active]?.label ?? "尚未返回"}</p>
    <ol aria-label="文档处理阶段" className={styles.stages}>
      {steps.map((step, index) => <li aria-current={index === active ? "step" : undefined}
        data-done={index < active} key={step.key}>{step.label}</li>)}
    </ol>
    {pollError && <div className={styles.pollError} role="alert">
      <strong>处理进度暂时无法读取</strong>
      <p>{pollError} 保留上次已知进度；这不代表后台处理失败。</p>
      {onRefresh && <button className="button secondary small" disabled={refreshing} onClick={onRefresh} type="button">
        {refreshing ? "正在刷新…" : "刷新处理状态"}
      </button>}
    </div>}
  </div>;
}

type UploadStatusUpdate = { id: string; previousJob: IngestionJob; job?: IngestionJob; pollError?: string };

async function readJobStatus(item: QueueItem): Promise<UploadStatusUpdate | null> {
  const previousJob = item.job;
  if (!previousJob) return null;
  try { return { id: item.id, previousJob, job: await api.getIngestionJob(previousJob.id) }; }
  catch (error) { return { id: item.id, previousJob, pollError: error instanceof Error ? error.message : "请检查网络后重新读取。" }; }
}

function createQueuedJob(jobId: number, document: DocumentItem, message: string): IngestionJob {
  return {
    id: jobId,
    document_id: document.id,
    source_id: null,
    space_id: document.space_id,
    target_type: "document",
    job_type: "reparse",
    status: "queued",
    current_step: "queued",
    step_index: 0,
    step_total: 5,
    progress: 0,
    worker_id: null,
    queue_name: "default",
    priority: 100,
    attempt: 0,
    max_attempts: 3,
    message,
    error_code: null,
    error_message: null,
    error_details_json: "{}",
    result_json: "{}",
    parent_job_id: null,
    retry_count: 0,
    started_at: null,
    heartbeat_at: null,
    finished_at: null,
    cancel_requested_at: null,
    duration_ms: null,
    created_at: document.created_at,
    updated_at: document.updated_at
  };
}
