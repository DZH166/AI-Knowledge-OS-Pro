import type { EvaluationComparison, EvaluationStatus } from "./contract";
import { EVALUATION_METRICS } from "./metric-catalog";


export function evaluationStatusLabel(status: EvaluationStatus): string {
  return {
    queued: "等待后台执行",
    running: "正在运行固定评测",
    passed: "全部质量门禁通过",
    failed: "执行或质量门禁失败"
  }[status];
}

export function comparisonVerdictLabel(verdict: EvaluationComparison["verdict"]): string {
  return {
    improved: "整体提升",
    stable: "表现稳定",
    regressed: "出现回退",
    incomparable: "不可直接比较"
  }[verdict];
}

export function failureCategoryLabel(category: string): string {
  return ({
    none: "没有执行故障",
    dispatch_failed: "任务没有进入队列",
    worker_interrupted: "后台任务进程中断",
    executor_timeout: "评测执行超时",
    executor_failed: "评测执行失败",
    malformed_report: "评测报告不可信",
    evaluation_gate_failed: "质量门禁未通过",
    budget_exhausted: "运行预算耗尽",
    evidence_insufficient: "证据不足",
    tool_failed: "工具调用失败",
    provider_unavailable: "模型提供方不可用",
    user_cancelled: "用户主动取消",
    unknown: "暂时无法归类"
  } as Record<string, string>)[category] ?? category;
}

export function metricLabel(metric: string): string {
  return EVALUATION_METRICS[metric]?.label ?? metric;
}

export function traceEventLabel(eventType: string): string {
  if (eventType.startsWith("run.")) return `运行状态 · ${eventType.slice(4)}`;
  if (eventType.startsWith("model.")) return `模型步骤 · ${eventType.slice(6)}`;
  if (eventType.startsWith("tool.")) return `工具步骤 · ${eventType.slice(5)}`;
  if (eventType.startsWith("evidence.")) return `证据步骤 · ${eventType.slice(9)}`;
  if (eventType.startsWith("interaction.")) return `人工交互 · ${eventType.slice(12)}`;
  return eventType;
}
