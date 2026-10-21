import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { StudyOverview, StudySummary, StudyTemplate } from "@/modules/optimizer/contract";
import { OptimizerLabContent } from "./OptimizerLab";
import { OptimizerStudyContent } from "./OptimizerStudyView";


const template: StudyTemplate = {
  key: "balanced", description: "Balance quality and latency.", objective: "balanced",
  max_candidates: 4, max_evaluations: 8, seed: 42,
  search_space: {
    factual_top_k: { minimum: 4, maximum: 16 }, comparative_top_k: { minimum: 6, maximum: 20 },
    temporal_top_k: { minimum: 4, maximum: 18 }, minimum_score_millis: { minimum: 0, maximum: 200 },
    max_hits_per_source: { minimum: 1, maximum: 6 }, neighbor_before: { minimum: 0, maximum: 2 },
    neighbor_after: { minimum: 0, maximum: 2 }
  },
  weights: { quality_weight_permille: 700, cost_weight_permille: 300 }
};

const study: StudySummary = {
  id: "study-1", label: "Balanced study", objective: "balanced", status: "completed",
  base_policy_fingerprint: "a".repeat(64), budget_usage: { created_trials: 3, started_evaluations: 3 },
  created_at: "2026-09-01T00:00:00Z"
};

const overview: StudyOverview = {
  study: {
    id: study.id, request_id: "request-1", label: study.label, objective: "balanced", status: "completed",
    base_policy_id: "policy-1", base_policy_fingerprint: "a".repeat(64), search_space: template.search_space,
    weights: template.weights, budget: { max_candidates: 4, max_evaluations: 8 },
    budget_usage: study.budget_usage, seed: 42, algorithm_version: "v5_6_bayesian_1",
    created_at: study.created_at, started_at: study.created_at, finished_at: study.created_at,
    cancelled_at: null, round_no: 1, warm_start_study_id: null, next_round_request_id: null
  },
  rounds: [{ round_no: 1, total: 3, completed: 3, failed: 0, cancelled: 0, best_score_millis: 820 }],
  trials: [{
    id: "trial-1", ordinal: 1, round_no: 1, status: "completed", score_millis: 820,
    draft_policy_id: null, recommendation_rank: 1, failure_code: null, eligible: true,
    metrics: {
      case_pass_rate: 1, mean_source_recall: 0.95, citation_completeness: 1,
      latency_ms: 123, retrieval_window: 24, external_provider_calls: 0
    }
  }],
  frontier: [{ trial_id: "trial-1", ordinal: 1 }],
  recommendation: [{
    rank: 1, trial_id: "trial-1", score_millis: 820, converted: false, draft_policy_id: null,
    rationale_first_line: "Quality improved without extra provider calls."
  }],
  actions: [
    { action: "next-round", available: true, reason: "budget remains" },
    { action: "convert-draft", available: true, reason: "recommendation available" }
  ]
};

describe("optimizer product views", () => {
  it("renders templates, active policy context, and Study history", () => {
    const markup = renderToStaticMarkup(createElement(OptimizerLabContent, {
      activePolicy: { id: "policy-1", label: "Balanced policy", version: 1, configSha256: "a".repeat(64) },
      templates: [template], studies: [study], selectedTemplate: "balanced", label: "New Study",
      maxCandidates: 4, maxEvaluations: 8, seed: 42, busy: false,
      onCreate: () => undefined, onLabelChange: () => undefined, onLimitChange: () => undefined,
      onSeedChange: () => undefined, onTemplateChange: () => undefined
    }));

    expect(markup).toContain("离线检索优化器");
    expect(markup).toContain("Balanced policy");
    expect(markup).toContain("Balanced study");
    expect(markup).toContain("创建优化实验");
  });

  it("renders server actions, recommendation rationale, trials, and event evidence", () => {
    const markup = renderToStaticMarkup(createElement(OptimizerStudyContent, {
      overview,
      events: [{ id: "event-1", event_type: "study_completed", round_no: 1, payload: {}, created_at: study.created_at }],
      selectedTrialIds: ["trial-1"], comparisonMarkdown: "# Comparison", busyAction: "", error: "",
      onAction: () => undefined, onCompare: () => undefined, onSelectionChange: () => undefined
    }));

    expect(markup).toContain("Quality improved without extra provider calls.");
    expect(markup).toContain("下一轮");
    expect(markup).toContain("转为草稿");
    expect(markup).toContain("study_completed");
    expect(markup).toContain("Comparison");
    expect(markup).toContain("95.0%");
    expect(markup).toContain("123 ms");
  });
});
