import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EvaluationComparisonSchema, EvaluationDetailSchema } from "@/modules/agent-control/contract";
import { evaluationDetail, evaluationSummary } from "@/modules/agent-control/test-fixtures";
import { EvaluationDetailContent } from "./EvaluationDetailView";
import { EvaluationCatalogView } from "./EvaluationIndex";


describe("evaluation product views", () => {
  it("renders persistent history and an honest regression comparison", () => {
    const comparison = EvaluationComparisonSchema.parse({
      schema_version: 1,
      left_id: "evaluation-1",
      right_id: "evaluation-2",
      compatible: true,
      incompatibility_reasons: [],
      verdict: "regressed",
      policy_changed: true,
      left_policy_fingerprint: "a".repeat(64),
      right_policy_fingerprint: "b".repeat(64),
      metric_deltas: [{
        metric: "case_pass_rate", left: 1, right: 0.9, delta: -0.1,
        preferred_direction: "higher", improved: false, regressed: true
      }],
      gate_changes: [{ gate: "all_cases_pass", left: true, right: false }],
      new_failure_case_ids: ["single-hop-01"],
      resolved_failure_case_ids: []
    });
    const markup = renderToStaticMarkup(createElement(EvaluationCatalogView, {
      comparing: false,
      comparison,
      comparisonItems: [evaluationSummary(), { ...evaluationSummary("failed"), id: "evaluation-2", label: "Regression" }],
      items: [evaluationSummary(), { ...evaluationSummary("failed"), id: "evaluation-2", label: "Regression" }],
      leftId: "evaluation-1",
      rightId: "evaluation-2",
      onCompare: () => undefined,
      onSelect: () => undefined,
      onStatusFilter: () => undefined,
      statusFilter: ""
    }));
    expect(markup).toContain("出现回退");
    expect(markup).toContain("案例通过率");
    expect(markup).toContain("single-hop-01");
    expect(markup).toContain("all_cases_pass");
    expect(markup).toContain("策略指纹");
    expect(markup).toContain("这次对比包含策略改动");
    expect(markup).toContain("按状态筛选");
    expect(markup).toContain("打开评测详情");
  });

  it("renders 60-case provenance and zero-provider disclosure", () => {
    const detail = EvaluationDetailSchema.parse(evaluationDetail());
    const markup = renderToStaticMarkup(createElement(EvaluationDetailContent, {
      detail,
      onRerun: () => undefined,
      rerunning: false
    }));
    expect(markup).toContain("60 个固定案例");
    expect(markup).toContain("外部调用");
    expect(markup).toContain("not a real-model quality benchmark");
    expect(markup).toContain("Policy");
    expect(markup).toContain("没有失败案例");
  });

  it("renders failed case triage and a concrete next action", () => {
    const base = evaluationDetail();
    const cases = base.cases.map((item, index) => index === 0 ? {
      ...item,
      passed: false,
      actual_status: "failed",
      source_recall: 0,
      supported_claims: 0,
      failure_reason: "status_mismatch"
    } : item);
    const detail = EvaluationDetailSchema.parse({
      ...base,
      summary: {
        ...base.summary,
        status: "failed",
        case_pass_rate: 59 / 60,
        failure_case_count: 1
      },
      metrics: { ...base.metrics, case_pass_rate: 59 / 60 },
      hard_gates: { all_cases_pass: false },
      cases,
      failure_case_ids: [cases[0].case_id],
      triage: {
        category: "evaluation_gate_failed",
        summary: "至少一个质量门禁失败。",
        retryable: false,
        supporting_facts: ["hard_gate_failed=true"],
        suggested_action: "打开失败案例和指标差异，修复回退后再评测。"
      },
      error_code: "EVALUATION_GATE_FAILED",
      error_message: "One or more fixed quality gates failed."
    });
    const markup = renderToStaticMarkup(createElement(EvaluationDetailContent, {
      detail,
      onRerun: () => undefined,
      rerunning: false
    }));
    expect(markup).toContain("质量门禁未通过");
    expect(markup).toContain("1 个失败案例");
    expect(markup).toContain("修复回退后再评测");
    expect(markup).toContain("status_mismatch");
  });
});
