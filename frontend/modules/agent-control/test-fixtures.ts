export function evaluationSummary(status: "queued" | "running" | "passed" | "failed" = "passed") {
  return {
    id: "evaluation-1",
    label: "Fixed evaluation",
    status,
    mode: "deterministic_recording" as const,
    policy_fingerprint: "a".repeat(64),
    dataset_sha256: status === "queued" ? null : "b".repeat(64),
    case_count: status === "passed" ? 60 : 0,
    case_pass_rate: status === "passed" ? 1 : null,
    external_provider_calls: status === "passed" ? 0 : null,
    failure_case_count: 0,
    created_at: "2026-08-27T10:00:00Z",
    started_at: status === "queued" ? null : "2026-08-27T10:00:01Z",
    finished_at: status === "passed" || status === "failed" ? "2026-08-27T10:00:10Z" : null
  };
}

export function evaluationDetail(status: "queued" | "running" | "passed" | "failed" = "passed") {
  const passed = status === "passed";
  return {
    schema_version: 1,
    summary: evaluationSummary(status),
    report_schema_version: passed ? 2 : null,
    evaluator_sha256: passed ? "c".repeat(64) : null,
    dataset_name: passed ? "v5_fixed_evidence_cases" : null,
    category_counts: passed ? { single_hop: 60 } : {},
    metrics: passed ? { case_pass_rate: 1, unauthorized_action_rate: 0 } : {},
    hard_gates: passed ? { all_cases_pass: true } : {},
    cases: passed
      ? Array.from({ length: 60 }, (_, index) => ({
          case_id: `case-${index + 1}`,
          category: "single_hop",
          passed: true,
          expected_status: "completed",
          actual_status: "completed",
          source_recall: 1,
          supported_claims: 1,
          latency_ms: 10,
          failure_reason: null
        }))
      : [],
    failure_case_ids: [],
    provider_boundary: "Deterministic regression evidence; not a real-model quality benchmark.",
    triage: {
      category: "none",
      summary: "没有执行故障。",
      retryable: false,
      supporting_facts: [`status=${status}`],
      suggested_action: "无需处理。"
    },
    error_code: null,
    error_message: null
  };
}

export function runTrace() {
  return {
    schema_version: 1,
    run_id: "run-1",
    trace_id: "trace-1",
    goal: "Explain trace",
    requested_mode: "force_agent",
    effective_mode: "force_agent",
    status: "completed",
    phase: "persist_artifact",
    provider_mode: "demo",
    created_at: "2026-08-27T10:00:00Z",
    started_at: "2026-08-27T10:00:00Z",
    finished_at: "2026-08-27T10:00:01Z",
    active_elapsed_ms: 1000,
    budget_limits: { max_steps: 8 },
    budget_usage: { steps: 3 },
    events: [
      {
        sequence: 1,
        run_version: 1,
        event_type: "run.completed",
        visibility: "public",
        redacted: false,
        facts: ["status=completed"],
        elapsed_ms: 1000,
        delta_ms: 1000,
        step_id: null,
        tool_call_id: null
      }
    ],
    tool_calls: [],
    model_calls: [],
    policies: [],
    replay: {
      digest: "d".repeat(64),
      sequence_contiguous: true,
      trace_id_consistent: true,
      stored_terminal_state: "completed",
      replayed_terminal_state: "completed",
      stored_state_matches: true,
      event_count: 1,
      redacted_event_count: 0,
      checkpoint_count: 0,
      latest_checkpoint_checksum: null
    },
    triage: {
      category: "none",
      summary: "没有执行故障。",
      retryable: false,
      supporting_facts: ["status=completed"],
      suggested_action: "无需处理。"
    },
    warnings: []
  };
}
