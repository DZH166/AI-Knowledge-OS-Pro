"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Ban, RefreshCw, RotateCcw, TimerReset } from "lucide-react";
import Link from "next/link";

import { ButtonLoading, EmptyState, ErrorState, LoadingSkeleton, PageHeader, SearchInput, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import type { IngestionJob, JobEvent } from "@/types/api";

const activeStatuses = new Set(["queued", "claimed", "running", "cancelling", "retry_scheduled"]);

export default function TasksPage() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [events, setEvents] = useState<Record<number, JobEvent[]>>({});
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [targetType, setTargetType] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pendingJobId, setPendingJobId] = useState<number | null>(null);
  const [pendingAction, setPendingAction] = useState<"retry" | "cancel" | null>(null);

  const load = useCallback(async (showRefresh = false) => {
    setError("");
    if (showRefresh) setRefreshing(true);
    try {
      const data = await api.listIngestionJobs();
      setJobs(data);
      setSelectedJobId((current) => current || data[0]?.id || null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load tasks.");
    } finally {
      setLoading(false);
      if (showRefresh) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => load(), 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!selectedJobId) return;
    api
      .getIngestionJobEvents(selectedJobId)
      .then((data) => setEvents((old) => ({ ...old, [selectedJobId]: data })))
      .catch(() => undefined);
  }, [selectedJobId, jobs]);

  const filtered = useMemo(
    () =>
      jobs.filter((job) => {
        const haystack = [job.id, job.document_id, job.source_id, operationLabel(job.job_type), job.status, job.current_step, job.message, job.error_message]
          .join(" ")
          .toLowerCase();
        return haystack.includes(query.toLowerCase()) && (status ? job.status === status : true) && (targetType ? job.target_type === targetType : true);
      }),
    [jobs, query, status, targetType]
  );

  const selectedJob = jobs.find((job) => job.id === selectedJobId) || filtered[0] || null;
  const selectedEvents = selectedJob ? events[selectedJob.id] || [] : [];
  const activeCount = jobs.filter((job) => activeStatuses.has(job.status)).length;
  const failedCount = jobs.filter((job) => ["failed", "interrupted"].includes(job.status)).length;
  const completedCount = jobs.filter((job) => job.status === "completed").length;

  async function retry(job: IngestionJob) {
    setMessage("");
    setPendingJobId(job.id);
    setPendingAction("retry");
    try {
      const next = await api.retryIngestionJob(job.id);
      setSelectedJobId(next.id);
      setMessage(`Retry task #${next.id} was created.`);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to retry task.");
    } finally {
      setPendingJobId(null);
      setPendingAction(null);
    }
  }

  async function cancel(job: IngestionJob) {
    setMessage("");
    setPendingJobId(job.id);
    setPendingAction("cancel");
    try {
      await api.cancelIngestionJob(job.id);
      setMessage(`Cancellation requested for task #${job.id}.`);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to cancel task.");
    } finally {
      setPendingJobId(null);
      setPendingAction(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        action={
          <button className="button" disabled={refreshing} onClick={() => load(true)} type="button">
            {refreshing ? <ButtonLoading label="Refreshing" /> : <><RefreshCw size={17} />Refresh</>}
          </button>
        }
        description="Track document parsing, image analysis, audio transcription, video keyframes and video transcription in one durable task center. Failed tasks can be retried, active tasks can be cancelled, and completed tasks link back to their result."
        eyebrow="V4.7 observable task engine"
        title="Task Center"
      />

      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}

      <section className="grid cols-3">
        <article className="card">
          <span className="muted">Active</span>
          <p className="stat-value">{activeCount}</p>
        </article>
        <article className="card">
          <span className="muted">Completed</span>
          <p className="stat-value">{completedCount}</p>
        </article>
        <article className="card">
          <span className="muted">Needs Attention</span>
          <p className="stat-value">{failedCount}</p>
        </article>
      </section>

      <section className="panel stack">
        <div className="row between wrap">
          <SearchInput onChange={setQuery} placeholder="Search by task, source, step, message or error" value={query} />
          <div className="row wrap">
            <select className="select" onChange={(event) => setTargetType(event.target.value)} style={{ maxWidth: 170 }} value={targetType}>
              <option value="">All targets</option>
              <option value="document">Documents</option>
              <option value="media">Media</option>
            </select>
            <select className="select" onChange={(event) => setStatus(event.target.value)} style={{ maxWidth: 190 }} value={status}>
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="interrupted">Interrupted</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        {loading ? (
          <LoadingSkeleton lines={6} />
        ) : filtered.length === 0 ? (
          <EmptyState description="Upload a source or run a media processing action to create a task." title="No matching tasks" />
        ) : (
          <div className="split">
            <div className="list">
              {filtered.map((job) => (
                <button className={`list-item task-row ${selectedJob?.id === job.id ? "active" : ""}`} key={job.id} onClick={() => setSelectedJobId(job.id)} type="button">
                  <div className="row between">
                    <strong>Task #{job.id}</strong>
                    <StatusBadge status={job.status} />
                  </div>
                  <span className="muted">
                    {targetLabel(job)} / {operationLabel(job.job_type)} / {stepLabel(job.current_step)}
                  </span>
                  <div className="progress" aria-label={`Task progress ${job.progress}%`}>
                    <span style={{ width: `${Math.max(0, Math.min(job.progress, 100))}%` }} />
                  </div>
                  <span className="muted">{job.message || job.error_message || "Waiting for worker update."}</span>
                </button>
              ))}
            </div>

            {selectedJob && (
              <aside className="drawer stack">
                <div className="row between">
                  <div>
                    <h2>Task #{selectedJob.id}</h2>
                    <p className="muted">
                      Queue {selectedJob.queue_name} / attempt {selectedJob.attempt}/{selectedJob.max_attempts}
                    </p>
                  </div>
                  <StatusBadge status={selectedJob.status} />
                </div>
                <div className="progress" aria-label={`Task progress ${selectedJob.progress}%`}>
                  <span style={{ width: `${Math.max(0, Math.min(selectedJob.progress, 100))}%` }} />
                </div>
                <div className="row wrap">
                  <button
                    className="button secondary small"
                    disabled={activeStatuses.has(selectedJob.status) || pendingJobId === selectedJob.id}
                    onClick={() => retry(selectedJob)}
                    type="button"
                  >
                    {pendingJobId === selectedJob.id && pendingAction === "retry" ? (
                      <ButtonLoading label="Scheduling" />
                    ) : (
                      <>
                        <RotateCcw size={14} />
                        {selectedJob.status === "completed" ? "Process Again" : "Retry"}
                      </>
                    )}
                  </button>
                  <button
                    className="button secondary small"
                    disabled={!activeStatuses.has(selectedJob.status) || pendingJobId === selectedJob.id}
                    onClick={() => cancel(selectedJob)}
                    type="button"
                  >
                    {pendingJobId === selectedJob.id && pendingAction === "cancel" ? (
                      <ButtonLoading label="Cancelling" />
                    ) : (
                      <>
                        <Ban size={14} />
                        Cancel
                      </>
                    )}
                  </button>
                  {resultUrl(selectedJob) && (
                    <Link className="button small" href={resultUrl(selectedJob) || "/tasks"}>
                      View Result
                    </Link>
                  )}
                </div>

                <div className="grid cols-2">
                  <Metric label="Target" value={targetLabel(selectedJob)} />
                  <Metric label="Operation" value={operationLabel(selectedJob.job_type)} />
                  <Metric label="Current Step" value={stepLabel(selectedJob.current_step)} />
                  <Metric label="Step Progress" value={`${selectedJob.step_index}/${selectedJob.step_total || 5}`} />
                  <Metric label="Worker" value={selectedJob.worker_id || "not claimed"} />
                  <Metric label="Duration" value={selectedJob.duration_ms ? `${selectedJob.duration_ms} ms` : "not finished"} />
                  <Metric label="Created" value={formatDate(selectedJob.created_at)} />
                  <Metric label="Heartbeat" value={formatDate(selectedJob.heartbeat_at)} />
                </div>

                {selectedJob.error_message && <p className="quote">{selectedJob.error_message}</p>}
                <RecoveryHint job={selectedJob} />

                <section className="stack">
                  <div className="row">
                    <TimerReset size={18} />
                    <h3>Event Timeline</h3>
                  </div>
                  {selectedEvents.length === 0 ? (
                    <EmptyState description="Worker events appear here after the task is queued or starts running." title="No events loaded" />
                  ) : (
                    <div className="timeline">
                      {selectedEvents.map((event) => (
                        <article className="timeline-item" key={event.id}>
                          <div className="row between">
                            <strong>{statusLabel(event.event_type)}</strong>
                            <span className="muted">{formatDate(event.created_at)}</span>
                          </div>
                          <p className="muted">
                            {stepLabel(event.step)} / {event.progress}%
                          </p>
                          {event.message && <p>{event.message}</p>}
                          {event.technical_message && (
                            <TechnicalDetails title="Technical message">
                              <p className="pre-wrap">{event.technical_message}</p>
                            </TechnicalDetails>
                          )}
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              </aside>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function operationLabel(value: string) {
  const labels: Record<string, string> = {
    reparse: "Parse and index document",
    reindex: "Rebuild document index",
    retry: "Retry document processing",
    image_ocr: "Image OCR",
    image_visual_description: "Image visual description",
    image_screenshot_analysis: "Screenshot error analysis",
    image_full_analysis: "Full image analysis",
    audio_transcription: "Audio transcription",
    video_transcription: "Video transcription",
    video_keyframes: "Video keyframes",
    video_keyframe_ocr: "Keyframe OCR",
    video_visual_description: "Keyframe visual description",
    video_full_pipeline: "Full video pipeline"
  };
  return labels[value] || value;
}

function stepLabel(value: string | null) {
  if (!value) return "Waiting";
  const labels: Record<string, string> = {
    queued: "Waiting for worker",
    preflight: "Checking source",
    parsing: "Parsing document",
    chunking: "Splitting content",
    embedding: "Generating embeddings",
    indexing: "Writing index",
    ocr: "Reading text",
    screenshot_analysis: "Analyzing error evidence",
    visual_description: "Analyzing visual content",
    keyframes: "Extracting keyframes",
    keyframe_ocr: "Reading keyframe text",
    transcription: "Transcribing audio",
    completed: "Completed"
  };
  return labels[value] || value;
}

function targetLabel(job: IngestionJob) {
  return job.source_id ? `Media #${job.source_id}` : `Document #${job.document_id || "-"}`;
}

function resultUrl(job: IngestionJob) {
  try {
    const parsed = JSON.parse(job.result_json || "{}") as { detail_url?: string };
    if (parsed.detail_url) return parsed.detail_url;
  } catch {
    return null;
  }
  if (job.source_id) return `/media/sources/${job.source_id}`;
  if (job.document_id) return `/documents/${job.document_id}`;
  return null;
}

function recoveryHint(job: IngestionJob) {
  const haystack = [job.status, job.job_type, job.current_step, job.message, job.error_message].join(" ").toLowerCase();
  if (job.status === "completed") {
    return {
      title: "处理已完成",
      detail: "可以打开结果页检查生成的片段、转写、关键帧或引用来源。",
      action: "查看结果"
    };
  }
  if (activeStatuses.has(job.status)) {
    return {
      title: "任务正在处理中",
      detail: "保持 Worker 和本地服务运行；如果长时间没有心跳，先检查 Redis、Worker 进程和系统状态页。",
      action: "检查系统"
    };
  }
  if (job.status === "cancelled") {
    return {
      title: "任务已取消",
      detail: "源资料仍保留。确认配置或文件无误后，可以重新处理。",
      action: "重新处理"
    };
  }
  if (haystack.includes("transcription_not_configured") || haystack.includes("transcription")) {
    return {
      title: "需要配置转写 Provider",
      detail: "音频/视频转写需要真实 speech-to-text provider。未配置时系统会明确拒绝，不会生成假字幕。",
      action: "配置后重试"
    };
  }
  if (haystack.includes("ocr_not_configured") || haystack.includes("vision") || haystack.includes("ocr")) {
    return {
      title: "需要配置 OCR / Vision Provider",
      detail: "图片 OCR、截图报错识别和关键帧理解需要真实 provider。配置后再重试该任务。",
      action: "配置后重试"
    };
  }
  if (haystack.includes("embedding") || haystack.includes("qdrant") || haystack.includes("index")) {
    return {
      title: "检查检索服务",
      detail: "语义索引依赖 Embedding provider 和 Qdrant。先确认系统状态页，再重试索引任务。",
      action: "检查系统"
    };
  }
  if (job.status === "interrupted") {
    return {
      title: "Worker 中断",
      detail: "任务可能在 Worker 停止或服务断开时中断。恢复 Redis/Worker 后重试即可。",
      action: "恢复后重试"
    };
  }
  return {
    title: "需要人工处理",
    detail: "查看事件时间线里的失败阶段和技术信息，修复配置、服务或文件问题后再重试。",
    action: "查看事件"
  };
}

function RecoveryHint({ job }: { job: IngestionJob }) {
  const hint = recoveryHint(job);
  return (
    <article className="card stack">
      <div className="row between wrap">
        <div>
          <span className="muted">恢复建议</span>
          <h3>{hint.title}</h3>
        </div>
        <span className="pill gray">{hint.action}</span>
      </div>
      <p>{hint.detail}</p>
      {!job.status.includes("completed") && (
        <p className="muted">
          配置类问题先到 <Link href="/system">模型与服务</Link> 页面检查；文件或处理阶段问题可结合事件时间线定位。
        </p>
      )}
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="list-item">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
