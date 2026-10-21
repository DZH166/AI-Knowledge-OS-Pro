import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { evaluationSummary } from "@/modules/agent-control/test-fixtures";
import { policyComparison, policyDetail, policySimulation } from "@/modules/agent-policy/test-fixtures";
import { PolicyDetailContent } from "./PolicyDetailView";
import { PolicyLabContent } from "./PolicyLab";


describe("Agent policy product views", () => {
  it("renders one active policy, immutable history, and bounded draft controls", () => {
    const active = policyDetail();
    const candidate = policyDetail({
      id: "policy-2",
      version: 2,
      label: "Recall candidate",
      status: "draft",
      config_sha256: "b".repeat(64),
      base_policy_id: active.id,
      has_been_active: false,
      activated_at: null
    });
    const markup = renderToStaticMarkup(createElement(PolicyLabContent, {
      active,
      items: [candidate, active],
      draftConfig: candidate.config,
      draftLabel: "New candidate",
      onConfigChange: () => undefined,
      onCreate: () => undefined,
      onLabelChange: () => undefined,
      submitting: false
    }));

    expect(markup).toContain("当前活动策略");
    expect(markup).toContain("Balanced evidence retrieval");
    expect(markup).toContain("Recall candidate");
    expect(markup).toContain("事实型 Top-K");
    expect(markup).toContain("创建不可变草稿");
    expect(markup).not.toContain("arbitrary_python");
  });

  it("renders comparison, counterfactual boundary, matching evaluation, activation, and rollback actions", () => {
    const active = policyDetail();
    const detail = policyDetail({
      id: "policy-2",
      version: 2,
      label: "Evaluated candidate",
      status: "draft",
      config_sha256: "b".repeat(64),
      base_policy_id: active.id,
      has_been_active: false,
      activated_at: null,
      config: { ...active.config, factual_top_k: 12 }
    });
    const evaluation = {
      ...evaluationSummary(),
      id: "evaluation-policy-2",
      policy_fingerprint: detail.config_sha256,
      policy_version_id: detail.id
    };
    const markup = renderToStaticMarkup(createElement(PolicyDetailContent, {
      active,
      busyAction: "",
      comparison: policyComparison(),
      detail,
      evaluations: [evaluation],
      onActivate: () => undefined,
      onEvaluate: () => undefined,
      onRollback: () => undefined,
      onRunChange: () => undefined,
      onSimulate: () => undefined,
      runs: [{ id: "run-1", goal: "Compare evidence", status: "completed" }],
      selectedRunId: "run-1",
      simulation: policySimulation()
    }));

    expect(markup).toContain("策略字段差异");
    expect(markup).toContain("反事实模拟");
    expect(markup).toContain("不重新调用模型、检索或工具");
    expect(markup).toContain("evaluation-policy-2");
    expect(markup).toContain("启用已通过评测的策略");
    expect(markup).toContain("运行固定 60 场景评测");
  });

  it("shows rollback only for a previously active retired version", () => {
    const active = policyDetail({ id: "policy-2", version: 2, config_sha256: "b".repeat(64) });
    const retired = policyDetail({
      status: "retired",
      retired_at: "2026-08-28T12:00:00Z",
      has_been_active: true
    });
    const markup = renderToStaticMarkup(createElement(PolicyDetailContent, {
      active,
      busyAction: "",
      comparison: policyComparison(),
      detail: retired,
      evaluations: [],
      onActivate: () => undefined,
      onEvaluate: () => undefined,
      onRollback: () => undefined,
      onRunChange: () => undefined,
      onSimulate: () => undefined,
      runs: [],
      selectedRunId: "",
      simulation: null
    }));
    expect(markup).toContain("回滚到这个历史策略");
    expect(markup).not.toContain("启用已通过评测的策略");
  });
});
