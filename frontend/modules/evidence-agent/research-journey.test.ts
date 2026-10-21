import { describe, expect, it } from "vitest";

import { buildComparisonGoal, comparisonRunIntent, researchReadiness, workbenchJourneyHref } from "./research-journey";

describe("three-source research journey", () => {
  it("sends the user's question and chosen dimensions as an explicit comparison goal", () => {
    expect(buildComparisonGoal({
      question: "哪种缓存方案适合我们的服务？",
      dimensions: "延迟、维护成本，故障恢复"
    })).toBe(
      "哪种缓存方案适合我们的服务？\n\n比较维度：延迟、维护成本、故障恢复。\n请逐份资料比较这些维度，逐条给出可回到原文的证据；指出资料间的冲突和证据缺口，不要把缺失的信息写成事实。"
    );
  });

  it("pins three distinct documents in a read-only Agent comparison request", () => {
    const budget = { max_steps: 8, max_tool_calls: 12, max_model_calls: 6, max_active_ms: 180_000 };
    expect(comparisonRunIntent({ spaceId: 7, question: "比较甲乙丙", dimensions: "成本、风险",
      sourceIds: [11, 12, 13], budget, recording: false })).toEqual({
      schema_version: 1, space_id: 7,
      goal: buildComparisonGoal({ question: "比较甲乙丙", dimensions: "成本、风险" }),
      scope: { source_ids: [11, 12, 13] }, deliverable: { kind: "comparison" },
      mode: "force_agent", budget,
      permissions: { read_only: true, allow_scope_expansion: false }, provider_mode: "real"
    });
    expect(() => comparisonRunIntent({ spaceId: 7, question: "比较", dimensions: "成本",
      sourceIds: [11, 11, 12], budget, recording: false })).toThrow("至少三份");
  });

  it("rejects missing dimensions and a composed goal above the backend limit", () => {
    expect(() => buildComparisonGoal({ question: "比较方案", dimensions: "  " }))
      .toThrow("请填写至少一个比较维度。");
    expect(() => buildComparisonGoal({ question: "甲".repeat(3_980), dimensions: "成本" }))
      .toThrow("问题与比较要求合计不能超过 4000 字。");
  });

  it("requires real providers and retrieval services rather than treating demo providers as ready", () => {
    expect(researchReadiness({
      llm: { ok: true, status: "demo" },
      embedding: { ok: false, status: "not_configured" },
      qdrant: { ok: false, status: "unavailable" },
      redis: { ok: true, status: "ready" }
    })).toEqual({ ready: false, missing: ["真实语言模型", "真实向量生成", "向量库"] });
  });

  it("accepts configured providers and ready retrieval services without making a paid call", () => {
    expect(researchReadiness({
      llm: { ok: true, status: "configured" },
      embedding: { ok: true, status: "configured" },
      qdrant: { ok: true, status: "ready" },
      redis: { ok: true, status: "ready" }
    })).toEqual({ ready: true, missing: [] });
  });

  it("returns to the same space and comparison flow after document upload", () => {
    expect(workbenchJourneyHref({ recording: false, comparison: true, spaceId: 7 }))
      .toBe("/workbench?scenario=compare&space_id=7");
    expect(workbenchJourneyHref({ recording: true, comparison: false, spaceId: 0 }))
      .toBe("/workbench?demo=1");
  });
});
