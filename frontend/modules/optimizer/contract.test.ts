import { describe, expect, it } from "vitest";

import {
  CreateStudyFromTemplateInputSchema,
  StudyOverviewSchema,
  StudyTemplateCatalogSchema
} from "./contract";


const bound = { minimum: 1, maximum: 4 };
const searchSpace = {
  factual_top_k: bound,
  comparative_top_k: bound,
  temporal_top_k: bound,
  minimum_score_millis: { minimum: 0, maximum: 100 },
  max_hits_per_source: bound,
  neighbor_before: { minimum: 0, maximum: 2 },
  neighbor_after: { minimum: 0, maximum: 2 }
};

describe("optimizer contracts", () => {
  it("accepts complete template and overview facts", () => {
    expect(StudyTemplateCatalogSchema.parse({
      items: ["quality_first", "balanced", "cost_first"].map((key) => ({
        key,
        description: key,
        objective: key,
        max_candidates: 4,
        max_evaluations: 8,
        seed: 42,
        search_space: searchSpace,
        weights: { quality_weight_permille: 700, cost_weight_permille: 300 }
      }))
    }).items).toHaveLength(3);

    const overview = StudyOverviewSchema.parse({
      study: {
        id: "study-1", request_id: "request-1", label: "Study", objective: "balanced",
        status: "completed", base_policy_id: "policy-1", base_policy_fingerprint: "a".repeat(64),
        search_space: searchSpace, weights: { quality_weight_permille: 700, cost_weight_permille: 300 },
        budget: { max_candidates: 4, max_evaluations: 8 },
        budget_usage: { created_trials: 3, started_evaluations: 3 }, seed: 42,
        algorithm_version: "v5_6_bayesian_1", created_at: "2026-09-01T00:00:00Z",
        started_at: "2026-09-01T00:01:00Z", finished_at: "2026-09-01T00:02:00Z",
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
        rank: 1, trial_id: "trial-1", score_millis: 820, converted: false,
        draft_policy_id: null, rationale_first_line: "Quality improved without extra provider calls."
      }],
      actions: [{ action: "convert-draft", available: true, reason: "recommendation available" }]
    });
    expect(overview.recommendation[0].rationale_first_line).toContain("Quality");
  });

  it("rejects incomplete facts, loose inputs, and executable overrides", () => {
    expect(() => CreateStudyFromTemplateInputSchema.parse({
      schema_version: 1,
      request_id: "request-1",
      label: "Study",
      base_policy_id: "policy-1",
      template_key: "balanced",
      overrides: { provider: "external" }
    })).toThrow();
    expect(() => StudyTemplateCatalogSchema.parse({
      items: [{ key: "balanced", description: "missing facts", objective: "balanced", max_candidates: 4, max_evaluations: 8, seed: 42 }]
    })).toThrow();
  });
});
