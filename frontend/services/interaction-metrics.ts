export type InteractionStatus = "running" | "completed" | "failed";

export type InteractionMetric = {
  id: string;
  label: string;
  status: InteractionStatus;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  error_code: string | null;
  message: string | null;
};

export type InteractionMetricsSnapshot = {
  running: number;
  completed: number;
  failed: number;
  slow_actions: number;
  recent: InteractionMetric[];
};

const recentActions: InteractionMetric[] = [];

export function startInteractionMetric(label: string) {
  const metric: InteractionMetric = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    label,
    status: "running",
    started_at: new Date().toISOString(),
    completed_at: null,
    duration_ms: null,
    error_code: null,
    message: null
  };
  recentActions.unshift(metric);
  recentActions.splice(80);
  return metric.id;
}

export function finishInteractionMetric(id: string, status: Exclude<InteractionStatus, "running">, error?: unknown) {
  const metric = recentActions.find((item) => item.id === id);
  if (!metric) return;
  const completed = Date.now();
  const started = new Date(metric.started_at).getTime();
  metric.status = status;
  metric.completed_at = new Date(completed).toISOString();
  metric.duration_ms = Math.max(0, completed - started);
  if (error instanceof Error) {
    metric.error_code = error.name || "ERROR";
    metric.message = error.message.slice(0, 160);
  } else if (typeof error === "string") {
    metric.error_code = "ERROR";
    metric.message = error.slice(0, 160);
  }
}

export function getInteractionMetricsSnapshot(): InteractionMetricsSnapshot {
  const completed = recentActions.filter((item) => item.status === "completed").length;
  const failed = recentActions.filter((item) => item.status === "failed").length;
  const running = recentActions.filter((item) => item.status === "running").length;
  const slow_actions = recentActions.filter((item) => (item.duration_ms || 0) >= 3000).length;
  return {
    running,
    completed,
    failed,
    slow_actions,
    recent: [...recentActions.slice(0, 30)]
  };
}
