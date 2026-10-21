export type PageMetricType = "navigation" | "route_change";

export type PageMetric = {
  id: string;
  route: string;
  metric_type: PageMetricType;
  duration_ms: number;
  source: string;
  created_at: string;
};

export type PageMetricsSnapshot = {
  total: number;
  average_duration_ms: number;
  slow_count: number;
  slow_threshold_ms: number;
  recent: PageMetric[];
};

const recentPageMetrics: PageMetric[] = [];
const slowThresholdMs = 1500;
let navigationRecorded = false;
let pendingRoute: { route: string; startedAt: number } | null = null;

export function markRouteTransitionStart(route: string) {
  if (typeof performance === "undefined") return;
  pendingRoute = { route, startedAt: performance.now() };
}

export function recordRouteReady(route: string) {
  recordInitialNavigation(route);
  if (typeof performance === "undefined" || !pendingRoute) return;
  const duration = Math.round(performance.now() - pendingRoute.startedAt);
  const targetRoute = pendingRoute.route;
  pendingRoute = null;
  recordPageMetric({
    route: targetRoute || route,
    metric_type: "route_change",
    duration_ms: Math.max(0, duration),
    source: "AppShell route transition"
  });
}

export function getPageMetricsSnapshot(): PageMetricsSnapshot {
  const durations = recentPageMetrics.map((item) => item.duration_ms);
  const total = durations.length;
  return {
    total,
    average_duration_ms: total ? Math.round(durations.reduce((sum, item) => sum + item, 0) / total) : 0,
    slow_count: durations.filter((duration) => duration >= slowThresholdMs).length,
    slow_threshold_ms: slowThresholdMs,
    recent: [...recentPageMetrics.slice(0, 20)]
  };
}

function recordInitialNavigation(route: string) {
  if (navigationRecorded || typeof performance === "undefined") return;
  const entries = performance.getEntriesByType?.("navigation") as PerformanceNavigationTiming[] | undefined;
  const navigation = entries?.[0];
  const duration = navigation
    ? Math.round((navigation.loadEventEnd || navigation.domContentLoadedEventEnd || navigation.responseEnd || performance.now()) - navigation.startTime)
    : Math.round(performance.now());
  navigationRecorded = true;
  recordPageMetric({
    route,
    metric_type: "navigation",
    duration_ms: Math.max(0, duration),
    source: "PerformanceNavigationTiming"
  });
}

function recordPageMetric(metric: Omit<PageMetric, "id" | "created_at">) {
  recentPageMetrics.unshift({
    ...metric,
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    created_at: new Date().toISOString()
  });
  recentPageMetrics.splice(40);
}
