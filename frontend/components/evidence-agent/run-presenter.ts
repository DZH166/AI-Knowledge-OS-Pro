import { z } from "zod";

import {
  EvidenceAddedPayloadSchema,
  EvidenceRelationChangedPayloadSchema,
  PlanCreatedPayloadSchema,
  type PlanCreatedPayload,
  type RunEvent,
  type RunView
} from "@/modules/evidence-agent";

export type TimelineItem = { id: string; cursor: number; label: string; detail: string | null; tone: "neutral" | "active" | "attention" | "done" };
export type LedgerItem = {
  id: string;
  sourceTitle: string;
  excerpt: string;
  relation: string;
  reason: string | null;
  method: string | null;
  reference: z.infer<typeof EvidenceAddedPayloadSchema>["reference"];
};
export type ResearchPlan = {
  version: number;
  strategy: string;
  requirements: string[];
};
export type RunAttention =
  | { kind: "approval"; summary: string; target: string; riskClass: string; proposalDigest: string }
  | {
      kind: "clarification";
      gateId: string;
      question: string;
      targetRequirementId: string;
      targetRequirementOrdinal: number;
    };

const ApprovalSchema = z.object({
  kind: z.literal("approval"),
  summary: z.string(),
  target: z.string(),
  risk_class: z.string(),
  proposal_digest: z.string().length(64)
});
const ClarificationSchema = z.object({
  gate_id: z.string().min(1),
  kind: z.literal("clarification"),
  question: z.string().min(1),
  target: z.object({
    requirement_id: z.string().min(1),
    requirement_ordinal: z.number().int().positive()
  })
});

const STATUS_LABELS: Record<RunView["status"], string> = {
  queued: "Run 已入队",
  routing: "正在选择执行模式",
  planned: "研究计划已就绪",
  running: "正在执行证据研究",
  awaiting_input: "等待补充信息",
  awaiting_approval: "等待人工审批",
  paused: "Run 已暂停",
  completed: "研究已完成",
  insufficient_evidence: "证据不足，已正常结束",
  cancelled: "Run 已取消",
  failed: "Run 执行失败"
};

export function runStatusLabel(status: RunView["status"]): string {
  return STATUS_LABELS[status];
}

export function timelineFromEvents(events: readonly RunEvent[]): TimelineItem[] {
  return events.map((event) => {
    if (event.change.type === "status_changed") {
      const status = event.change.status;
      return {
        id: event.event_id,
        cursor: event.cursor,
        label: STATUS_LABELS[status],
        detail: null,
        tone: status === "completed" ? "done" : status.startsWith("awaiting_") ? "attention" : "active"
      };
    }
    if (event.change.type === "domain_event") {
      const label = typeof event.change.payload.label === "string" ? event.change.payload.label : domainLabel(event.change.event_type);
      const detail = typeof event.change.payload.detail === "string" ? event.change.payload.detail : null;
      const nextQuery = typeof event.change.payload.next_query === "string" ? event.change.payload.next_query : null;
      return {
        id: event.event_id,
        cursor: event.cursor,
        label,
        detail: detail ?? (nextQuery ? `下一次检索：${nextQuery}` : null),
        tone: event.change.event_type === "artifact.published" ? "done" : "neutral"
      };
    }
    return { id: event.event_id, cursor: event.cursor, label: "投影已同步", detail: null, tone: "neutral" };
  });
}

export function ledgerFromEvents(events: readonly RunEvent[]): LedgerItem[] {
  const ledger = new Map<string, LedgerItem>();
  for (const event of events) {
    if (event.change.type !== "domain_event") continue;
    if (event.change.event_type === "evidence.added") {
      const parsed = EvidenceAddedPayloadSchema.safeParse(event.change.payload);
      if (!parsed.success) continue;
      ledger.set(parsed.data.evidence_id, {
        id: parsed.data.evidence_id,
        sourceTitle: parsed.data.source_title,
        excerpt: parsed.data.excerpt,
        relation: parsed.data.relation,
        reason: parsed.data.relation === "contextual" ? "same_revision_neighbor" : null,
        method: parsed.data.relation === "contextual" ? "bounded_neighbors" : null,
        reference: parsed.data.reference
      });
      continue;
    }
    if (event.change.event_type === "evidence.relation_changed") {
      const parsed = EvidenceRelationChangedPayloadSchema.safeParse(event.change.payload);
      if (!parsed.success) continue;
      const existing = ledger.get(parsed.data.evidence_id);
      if (existing) {
        ledger.set(parsed.data.evidence_id, {
          ...existing,
          relation: parsed.data.relation,
          reason: parsed.data.reason,
          method: parsed.data.method
        });
      }
    }
  }
  return [...ledger.values()];
}

export function planFromEvents(events: readonly RunEvent[]): ResearchPlan | null {
  for (const event of [...events].reverse()) {
    if (event.change.type !== "domain_event" || event.change.event_type !== "plan.created") continue;
    const parsed = PlanCreatedPayloadSchema.safeParse(event.change.payload);
    if (!parsed.success) continue;
    return publicPlan(parsed.data);
  }
  return null;
}

export function attentionFromEvents(events: readonly RunEvent[], status: RunView["status"]): RunAttention | null {
  if (status !== "awaiting_approval" && status !== "awaiting_input") return null;
  for (const event of [...events].reverse()) {
    if (event.change.type !== "domain_event" || event.change.event_type !== "interaction.required") continue;
    if (status === "awaiting_input") {
      const clarification = ClarificationSchema.safeParse(event.change.payload);
      if (clarification.success) {
        return {
          kind: "clarification",
          gateId: clarification.data.gate_id,
          question: clarification.data.question,
          targetRequirementId: clarification.data.target.requirement_id,
          targetRequirementOrdinal: clarification.data.target.requirement_ordinal
        };
      }
      continue;
    }
    const parsed = ApprovalSchema.safeParse(event.change.payload);
    if (parsed.success) {
      return {
        kind: "approval",
        summary: parsed.data.summary,
        target: parsed.data.target,
        riskClass: parsed.data.risk_class,
        proposalDigest: parsed.data.proposal_digest
      };
    }
  }
  return null;
}

function domainLabel(eventType: string): string {
  const labels: Record<string, string> = {
    "plan.created": "研究计划已生成",
    "step.completed": "执行步骤已完成",
    "evidence.added": "证据已加入 Ledger",
    "evidence.opened": "已打开精确证据",
    "evidence.relation_changed": "证据关系已核定",
    "tool.started": "证据工具已启动",
    "tool.completed": "证据工具已完成",
    "interaction.required": "需要人工决策",
    "interaction.resolved": "人工决策已记录",
    "artifact.published": "研究成果已发布"
  };
  return labels[eventType] ?? "运行状态已更新";
}

export function evidenceRelationLabel(relation: string): string {
  return {
    candidate: "候选证据",
    contextual: "上下文证据",
    supports: "支持结论",
    contradicts: "反证或冲突",
    excluded: "已排除"
  }[relation] ?? relation;
}

export function evidenceReasonLabel(reason: string | null): string | null {
  if (!reason) return null;
  return {
    model_not_selected: "模型评估后未选为该需求的支持证据",
    same_revision_neighbor: "来自同一版本的相邻上下文",
    model_selected_support: "模型已选择为支持证据",
    quantitative_conflict: "与同单位的数值证据存在冲突",
    retrieval_match: "检索内容与事实需求直接匹配"
  }[reason] ?? reason;
}

function publicPlan(payload: PlanCreatedPayload): ResearchPlan {
  return {
    version: payload.plan_version,
    strategy: payload.strategy,
    requirements: [...payload.requirements]
  };
}
