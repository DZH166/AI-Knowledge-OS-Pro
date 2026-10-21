"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { Activity, Gauge, RefreshCcw, ServerCog, TimerReset, Zap } from "lucide-react";

import { EmptyState, ErrorState, LoadingSkeleton, PageHeader, PendingButton, RecentActionsPanel, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api, formatDate, statusLabel } from "@/services/api";
import { getPageMetricsSnapshot } from "@/services/page-metrics";
import type { PageMetricsSnapshot } from "@/services/page-metrics";
import { getRequestCacheSnapshot } from "@/services/request-cache";
import type { RequestCacheSnapshot } from "@/services/request-cache";
import type { PerformanceSnapshot } from "@/types/api";

function duration(value: number | null | undefined) {
  if (value === null || value === undefined) return "未记录";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

export default function PerformancePage() {
  const [snapshot, setSnapshot] = useState<PerformanceSnapshot | null>(null);
  const [cache, setCache] = useState<RequestCacheSnapshot>(() => getRequestCacheSnapshot());
  const [pageMetrics, setPageMetrics] = useState<PageMetricsSnapshot>(() => getPageMetricsSnapshot());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (forceRefresh = false) => {
    setError("");
    setLoading(true);
    try {
      setSnapshot(await api.performance({ forceRefresh }));
      setCache(getRequestCacheSnapshot());
      setPageMetrics(getPageMetricsSnapshot());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载性能数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      setCache(getRequestCacheSnapshot());
      setPageMetrics(getPageMetricsSnapshot());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [load]);

  const slowPaths = useMemo(() => snapshot?.summary.path_stats.slice(0, 6) || [], [snapshot]);

  return (
    <div className="page" data-testid="performance-page">
      <PageHeader
        action={
          <div className="row wrap">
            <PendingButton className="button secondary" metricName="performance_refresh" onClick={() => load(true)} pendingLabel="刷新中">
              <RefreshCcw size={17} />
              刷新
            </PendingButton>
            <Link className="button" href="/system/observability">
              <TimerReset size={17} />
              可观测性
            </Link>
          </div>
        }
        description="查看真实运行时请求耗时、慢请求、重复请求、浏览器缓存命中和最近按钮耗时。这里不展示 API Key、上传文件内容、完整用户输入或 stack trace。"
        eyebrow="系统"
        title="性能与体验"
      />

      {loading && <LoadingSkeleton lines={6} />}
      {error && <ErrorState message={error} onRetry={() => load(true)} />}

      {snapshot && (
        <>
          <section className="grid cols-4">
            <MetricCard icon={<Activity size={18} />} label="最近请求" value={snapshot.summary.total_requests} />
            <MetricCard icon={<Gauge size={18} />} label="慢请求" value={snapshot.summary.slow_request_count} />
            <MetricCard icon={<Zap size={18} />} label="P95 耗时" value={duration(snapshot.summary.p95_latency_ms)} />
            <MetricCard icon={<ServerCog size={18} />} label="重复请求" value={snapshot.summary.duplicate_request_count} />
          </section>

          <section className="grid cols-2">
            <article className="panel stack" data-testid="performance-cache-panel">
              <div className="row between wrap">
                <h2>请求缓存与去重</h2>
                <span className="pill gray">{cache.entries} 个缓存项</span>
              </div>
              <div className="grid cols-4">
                <MetricCard label="命中" value={cache.hits} />
                <MetricCard label="未命中" value={cache.misses} />
                <MetricCard label="去重" value={cache.deduped} />
                <MetricCard label="强刷" value={cache.refreshes} />
              </div>
              {cache.recent.length ? (
                <div className="list">
                  {cache.recent.slice(0, 8).map((item) => (
                    <article className="list-item" key={item.id}>
                      <div className="row between wrap">
                        <strong>{item.method} {item.path}</strong>
                        <StatusBadge status={item.cache_status} label={statusLabel(item.cache_status)} />
                      </div>
                      <p className="muted">duration: {duration(item.duration_ms)} / request_id: {item.request_id || "本地命中"}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState description="访问 Dashboard、System、Learning 或 Portfolio 后，这里会显示浏览器侧缓存命中与请求去重。" title="暂无缓存记录" />
              )}
            </article>

            <article className="panel stack" data-testid="performance-page-load-panel">
              <div className="row between wrap">
                <h2>页面加载与切换</h2>
                <span className="pill gray">阈值 {pageMetrics.slow_threshold_ms} ms</span>
              </div>
              <div className="grid cols-3">
                <MetricCard label="记录数" value={pageMetrics.total} />
                <MetricCard label="平均耗时" value={duration(pageMetrics.average_duration_ms)} />
                <MetricCard label="慢页面" value={pageMetrics.slow_count} />
              </div>
              {pageMetrics.recent.length ? (
                <div className="list">
                  {pageMetrics.recent.slice(0, 6).map((item) => (
                    <article className="list-item" key={item.id}>
                      <div className="row between wrap">
                        <strong>{item.route}</strong>
                        <span className="pill gray">{duration(item.duration_ms)}</span>
                      </div>
                      <p className="muted">{item.metric_type === "navigation" ? "首次页面加载" : "导航切换"} / {item.source} / {formatDate(item.created_at)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState description="首次进入页面和通过主导航切换后，这里会记录浏览器侧页面耗时。" title="暂无页面耗时" />
              )}
            </article>
          </section>

          <section className="grid cols-2">
            <article className="panel stack" data-testid="performance-summary-panel">
              <div className="row between wrap">
                <h2>后端请求概览</h2>
                <span className="pill gray">阈值 {snapshot.summary.slow_threshold_ms} ms</span>
              </div>
              <div className="grid cols-3">
                <MetricCard label="平均耗时" value={duration(snapshot.summary.average_latency_ms)} />
                <MetricCard label="缓存状态" value={Object.keys(snapshot.summary.cache_status_counts).length} />
                <MetricCard label="错误类型" value={Object.keys(snapshot.summary.error_code_counts).length} />
              </div>
              <TechnicalDetails title="边界说明">
                <ul>
                  {snapshot.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </TechnicalDetails>
            </article>
          </section>

          <section className="grid cols-2">
            <article className="panel stack" data-testid="performance-slow-panel">
              <h2>慢请求 Top 10</h2>
              {snapshot.slow_requests.length ? (
                <div className="list">
                  {snapshot.slow_requests.map((request) => (
                    <article className="list-item" key={`${request.request_id}-${request.timestamp}`}>
                      <div className="row between wrap">
                        <strong>{request.method} {request.path}</strong>
                        <span className="pill gold">{duration(request.latency_ms)}</span>
                      </div>
                      <p className="muted">status: {request.status_code} / cache: {request.cache_status || "server"} / {formatDate(request.timestamp)}</p>
                      {request.error_code && <p className="muted">error_code: {request.error_code}</p>}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState description="当请求耗时超过阈值或最近请求数量足够时，这里会显示排序结果。" title="暂无慢请求" />
              )}
            </article>

            <article className="panel stack" data-testid="performance-path-panel">
              <h2>路径耗时分布</h2>
              {slowPaths.length ? (
                <div className="mini-chart">
                  {slowPaths.map((item) => (
                    <div className="task-segment" key={item.path}>
                      <div className="row between">
                        <span>{item.path}</span>
                        <strong>{duration(item.max_latency_ms)}</strong>
                      </div>
                      <div className="progress">
                        <span style={{ width: `${Math.min(100, Math.max(8, item.average_latency_ms / 20))}%` }} />
                      </div>
                      <p className="muted">count: {item.count} / avg: {duration(item.average_latency_ms)} / slow: {item.slow_count}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState description="访问几个 API 后，这里会按路径聚合请求耗时。" title="暂无路径统计" />
              )}
            </article>
          </section>

          <RecentActionsPanel />
        </>
      )}
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon?: ReactNode; label: string; value: string | number }) {
  return (
    <article className="card compact">
      <div className="row">
        {icon}
        <span className="muted">{label}</span>
      </div>
      <strong>{value}</strong>
    </article>
  );
}
