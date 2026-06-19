"use client";

import { useEffect, useMemo, useState } from "react";
import { Ban, RefreshCw, RotateCcw, TimerReset } from "lucide-react";
import Link from "next/link";

import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, SearchInput, StatusBadge, TechnicalDetails } from "@/components/ui";
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
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      const data = await api.listIngestionJobs();
      setJobs(data);
      if (!selectedJobId && data.length) setSelectedJobId(data[0].id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load tasks.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    try {
      const next = await api.retryIngestionJob(job.id);
      setSelectedJobId(next.id);
      setMessage(`Retry task #${next.id} was created.`);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to retry task.");
    }
  }

  async function cancel(job: IngestionJob) {
    setMessage("");
    try {
      await api.cancelIngestionJob(job.id);
      setMessage(`Cancellation requested for task #${job.id}.`);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to cancel task.");
    }
  }

  return (
    <div className="page">
      <PageHeader
        action={
          <button className="button" onClick={load} type="button">
            <RefreshCw size={17} />
            Refresh
          </button>
        }
        description="Track document parsing, image analysis, audio transcription, video keyframes and video transcription in one durable task center. Failed tasks can be retried, active tasks can be cancelled, and completed tasks link back to their result."
        eyebrow="V3.6 unified task engine"
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
                  <button className="button secondary small" disabled={activeStatuses.has(selectedJob.status)} onClick={() => retry(selectedJob)} type="button">
                    <RotateCcw size={14} />
                    {selectedJob.status === "completed" ? "Process Again" : "Retry"}
                  </button>
                  <button className="button secondary small" disabled={!activeStatuses.has(selectedJob.status)} onClick={() => cancel(selectedJob)} type="button">
                    <Ban size={14} />
                    Cancel
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="list-item">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
