import type { PolicyDetail } from "./contract";


export function policyDetail(overrides: Partial<PolicyDetail> = {}): PolicyDetail {
  return {
    id: "policy-1",
    policy_key: "default-research",
    version: 1,
    label: "Balanced evidence retrieval",
    status: "active",
    config_sha256: "a".repeat(64),
    base_policy_id: null,
    has_been_active: true,
    created_at: "2026-08-28T10:00:00Z",
    activated_at: "2026-08-28T10:00:00Z",
    retired_at: null,
    config: {
      schema_version: 1,
      factual_top_k: 8,
      comparative_top_k: 14,
      temporal_top_k: 12,
      minimum_score_millis: 0,
      max_hits_per_source: 3,
      neighbor_before: 1,
      neighbor_after: 1
    },
    ...overrides
  };
}

export function policyComparison() {
  return {
    schema_version: 1 as const,
    left_id: "policy-1",
    right_id: "policy-2",
    left_fingerprint: "a".repeat(64),
    right_fingerprint: "b".repeat(64),
    compatible: true,
    incompatibility_reasons: [],
    changes: [
      { field: "factual_top_k" as const, left: 8, right: 12 },
      { field: "neighbor_before" as const, left: 1, right: 2 }
    ]
  };
}

export function policySimulation() {
  return {
    schema_version: 1 as const,
    run_id: "run-1",
    policy_id: "policy-2",
    policy_version: 2,
    changed_decision_count: 1,
    projected_candidate_window_delta: 4,
    projected_neighbor_context_delta: 0,
    digest: "c".repeat(64),
    boundary: "Counterfactual policy projection; no model, retrieval, evidence query, tool, provider, or write was executed.",
    decisions: [
      {
        sequence: 1,
        tool: "search_evidence" as const,
        changed: true,
        recorded_top_k: 8,
        candidate_top_k: 12,
        recorded_before: null,
        candidate_before: null,
        recorded_after: null,
        candidate_after: null
      }
    ]
  };
}
