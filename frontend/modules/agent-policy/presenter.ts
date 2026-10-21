import type { PolicyStatus } from "./contract";


export function policyStatusLabel(status: PolicyStatus): string {
  return {
    draft: "待评测草稿",
    active: "当前活动策略",
    retired: "已退役历史策略"
  }[status];
}

export function policyFieldLabel(field: string): string {
  return ({
    factual_top_k: "事实型 Top-K",
    comparative_top_k: "比较型 Top-K",
    temporal_top_k: "时间型 Top-K",
    minimum_score_millis: "最低证据分数",
    max_hits_per_source: "单一来源上限",
    neighbor_before: "向前相邻片段",
    neighbor_after: "向后相邻片段"
  } as Record<string, string>)[field] ?? field;
}

export function policyValue(field: string, value: number): string {
  return field === "minimum_score_millis" ? `${value / 10}%` : String(value);
}
