"use client";

import Link from "next/link";
import { Activity, Clock3, DatabaseZap, RefreshCcw, TimerReset } from "lucide-react";
import { useEffect, useState } from "react";

import { api, formatDate, statusLabel } from "@/services/api";
import type { ObservabilitySummary } from "@/types/api";
import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, StatusBadge, TechnicalDetails } from "@/components/ui";

function duration(milliseconds: number | null | undefined) {
  if (milliseconds === null || milliseconds === undefined) return "未记录";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

function sourceMix(value: Record<string, number>) {
  const entries = Object.entries(value);
  if (entries.length === 0) return "无来源";
  return entries.map(([key, count]) => `${key}:${count}`).join(" / ");
}

export default function ObservabilityPage() {
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.observability());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载可观测性数据失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <PageHeader
        action={
          <div className="row wrap">
            <button className="button secondary" onClick={load} type="button">
              <RefreshCcw size={17} />
              刷新
            </button>
            <Link className="button" href="/system">
              <TimerReset size={17} />
              模型与服务
            </Link>
          </div>
        }
        description="查看最近请求、任务、检索、Provider 边界和错误分类。主界面隐藏密钥、完整隐私资料和 raw stack trace。"
        eyebrow="系统"
        title="运行时可观测性"
      />

      {loading && <LoadingSkeleton lines={5} />}
      {error && (
        <ErrorState
          impact="可观测性页面暂时无法展示最近运行数据。"
          message={error}
          nextStep="确认后端 API 已启动，然后重试。"
          onRetry={load}
          reason="可能是后端未启动、网络不可达或系统状态接口返回错误。"
        />
      )}

      {summary && (
        <>
          <section className="grid cols-4">
            <article className="card">
              <h3>运行模式</h3>
              <StatusBadge status={summary.runtime_mode} />
              <p className="muted">{summary.demo_mode ? "当前可使用 synthetic demo data。" : "真实模式不会伪造 Provider 输出。"}</p>
            </article>
            <article className="card">
              <h3>最近请求</h3>
              <p>{summary.recent_requests.length} 条</p>
              <p className="muted">request_id / latency_ms</p>
            </article>
            <article className="card">
              <h3>最近任务</h3>
              <p>{summary.recent_tasks.length} 条</p>
              <p className="muted">task_id / stage / duration</p>
            </article>
            <article className="card">
              <h3>错误分类</h3>
              <p>{Object.keys(summary.error_categories).length} 类</p>
              <p className="muted">不展示 stack trace</p>
            </article>
          </section>

          <section className="grid cols-2">
            <article className="panel stack">
              <div className="row">
                <Activity size={18} />
                <h2>最近请求</h2>
              </div>
              {summary.recent_requests.length === 0 ? (
                <EmptyState description="刷新或访问一个 API 后，这里会显示 request_id、路径、状态码和耗时。" title="暂无请求记录" />
              ) : (
                <div className="list">
                  {summary.recent_requests.slice(0, 8).map((request) => (
                    <article className="list-item" key={`${request.request_id}-${request.created_at}`}>
                      <div className="row between">
                        <strong>{request.method} {request.path}</strong>
                        <StatusBadge status={request.status_code >= 400 ? "failed" : "completed"} label={String(request.status_code)} />
                      </div>
                      <p className="muted">request_id: {request.request_id}</p>
                      <p className="muted">latency_ms: {request.latency_ms} / {formatDate(request.created_at)}</p>
                      {request.error_code && <p className="muted">error_code: {request.error_code}</p>}
                    </article>
                  ))}
                </div>
              )}
            </article>

            <article className="panel stack">
              <div className="row">
                <Clock3 size={18} />
                <h2>最近任务</h2>
              </div>
              {summary.recent_tasks.length === 0 ? (
                <EmptyState description="上传或媒体处理任务运行后，这里会展示 task_id、阶段、进度和耗时。" title="暂无任务记录" />
              ) : (
                <div className="list">
                  {summary.recent_tasks.slice(0, 8).map((task) => (
                    <article className="list-item" key={task.task_id}>
                      <div className="row between">
                        <strong>task #{task.task_id} / {task.target_type}</strong>
                        <StatusBadge status={task.status} />
                      </div>
                      <p className="muted">stage: {task.task_stage || "未记录"} / progress: {task.progress}% / duration: {duration(task.task_duration_ms)}</p>
                      {task.latest_event && <p>{task.latest_event}</p>}
                      {task.error_code && <p className="muted">error_code: {task.error_code}</p>}
                    </article>
                  ))}
                </div>
              )}
            </article>
          </section>

          <section className="grid cols-2">
            <article className="panel stack">
              <div className="row">
                <DatabaseZap size={18} />
                <h2>最近检索</h2>
              </div>
              {summary.recent_retrievals.length === 0 ? (
                <EmptyState description="Chat 产生 demo 或真实问答后，这里会显示 retrieval_trace_id、generation_id、引用数量和来源分布。" title="暂无检索记录" />
              ) : (
                <div className="list">
                  {summary.recent_retrievals.slice(0, 8).map((retrieval) => (
                    <article className="list-item" key={retrieval.retrieval_trace_id}>
                      <div className="row between">
                        <strong>{retrieval.retrieval_trace_id}</strong>
                        <StatusBadge status={retrieval.citation_validation_status === "passed" ? "completed" : "review_needed"} label={retrieval.citation_validation_status} />
                      </div>
                      <p className="muted">generation_id: {retrieval.generation_id}</p>
                      <p className="muted">answer_status: {statusLabel(retrieval.answer_status)} / citations: {retrieval.citation_count}</p>
                      <p className="muted">source_mix: {sourceMix(retrieval.retrieval_source_mix)}</p>
                      {retrieval.error_code && <p className="muted">error_code: {retrieval.error_code}</p>}
                    </article>
                  ))}
                </div>
              )}
            </article>

            <article className="panel stack">
              <h2>Provider 边界</h2>
              <div className="list">
                {summary.provider_status.map((provider) => (
                  <article className="list-item" key={provider.provider_name}>
                    <div className="row between">
                      <strong>{provider.provider_name}</strong>
                      <StatusBadge status={provider.provider_status} />
                    </div>
                    <p>{provider.message}</p>
                    {provider.provider_error_code && <p className="muted">provider_error_code: {provider.provider_error_code}</p>}
                  </article>
                ))}
              </div>
            </article>
          </section>

          <section className="panel stack">
            <h2>错误分类与边界说明</h2>
            {Object.keys(summary.error_categories).length === 0 ? (
              <p className="muted">当前没有最近错误分类。</p>
            ) : (
              <div className="row wrap">
                {Object.entries(summary.error_categories).map(([code, count]) => (
                  <span className="pill gray" key={code}>{code}: {count}</span>
                ))}
              </div>
            )}
            <TechnicalDetails title="技术说明">
              <ul>
                {summary.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </TechnicalDetails>
          </section>
        </>
      )}
    </div>
  );
}

