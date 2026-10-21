import type { ComponentStatus } from "@/types/api";
import type { StartRunInput } from "./contract";

type ResearchReadinessInput = {
  llm: Pick<ComponentStatus, "ok" | "status">;
  embedding: Pick<ComponentStatus, "ok" | "status">;
  qdrant: Pick<ComponentStatus, "ok" | "status">;
  redis: Pick<ComponentStatus, "ok" | "status">;
};

export function buildComparisonGoal({ question, dimensions }: { question: string; dimensions: string }): string {
  const cleanQuestion = question.trim();
  const selectedDimensions = [...new Set(dimensions.split(/[、，,；;\n]+/).map((item) => item.trim()).filter(Boolean))];
  if (!cleanQuestion) throw new Error("请先写下要比较的问题。");
  if (selectedDimensions.length === 0) throw new Error("请填写至少一个比较维度。");
  const goal = `${cleanQuestion}\n\n比较维度：${selectedDimensions.join("、")}。\n请逐份资料比较这些维度，逐条给出可回到原文的证据；指出资料间的冲突和证据缺口，不要把缺失的信息写成事实。`;
  if (goal.length > 4_000) throw new Error("问题与比较要求合计不能超过 4000 字。");
  return goal;
}

export function comparisonRunIntent({
  spaceId, question, dimensions, sourceIds, budget, recording
}: {
  spaceId: number;
  question: string;
  dimensions: string;
  sourceIds: readonly number[];
  budget: NonNullable<StartRunInput["budget"]>;
  recording: boolean;
}): Omit<StartRunInput, "request_id"> {
  if (new Set(sourceIds).size < 3) throw new Error("请先选择至少三份已完成处理的资料。");
  return {
    schema_version: 1,
    space_id: spaceId,
    goal: buildComparisonGoal({ question, dimensions }),
    scope: { source_ids: [...sourceIds] },
    deliverable: { kind: "comparison" },
    mode: "force_agent",
    budget,
    permissions: { read_only: true, allow_scope_expansion: false },
    provider_mode: recording ? "recording" : "real"
  };
}

export function researchReadiness(status: ResearchReadinessInput): { ready: boolean; missing: string[] } {
  const missing: string[] = [];
  if (!status.llm.ok || status.llm.status !== "configured") missing.push("真实语言模型");
  if (!status.embedding.ok || status.embedding.status !== "configured") missing.push("真实向量生成");
  if (!status.qdrant.ok || status.qdrant.status !== "ready") missing.push("向量库");
  if (!status.redis.ok || status.redis.status !== "ready") missing.push("任务队列");
  return { ready: missing.length === 0, missing };
}

export function workbenchJourneyHref({
  recording,
  comparison,
  spaceId
}: { recording: boolean; comparison: boolean; spaceId: number }): string {
  const params = new URLSearchParams();
  if (recording) params.set("demo", "1");
  if (comparison) params.set("scenario", "compare");
  if (spaceId > 0) params.set("space_id", String(spaceId));
  return `/workbench${params.size ? `?${params}` : ""}`;
}
