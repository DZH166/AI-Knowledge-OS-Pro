import { z } from "zod";


const SchemaVersionSchema = z.literal(1);
const Sha256Schema = z.string().regex(/^[a-fA-F0-9]{64}$/);
export const EvaluationStatusSchema = z.enum(["queued", "running", "passed", "failed"]);

export const StartEvaluationInputSchema = z
  .object({
    schema_version: SchemaVersionSchema.default(1),
    request_id: z.string().trim().min(1).max(120),
    label: z.string().trim().min(1).max(120)
  })
  .strict();

export const EvaluationReceiptSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    evaluation_id: z.string().min(1).max(36).regex(/^[A-Za-z0-9_-]+$/),
    status: EvaluationStatusSchema,
    replayed: z.boolean()
  })
  .strict();

export const FailureTriageSchema = z
  .object({
    category: z.string().min(1),
    summary: z.string().min(1),
    retryable: z.boolean(),
    supporting_facts: z.array(z.string()),
    suggested_action: z.string().min(1)
  })
  .strict();

export const EvaluationSummarySchema = z
  .object({
    id: z.string().min(1).max(36).regex(/^[A-Za-z0-9_-]+$/),
    label: z.string().min(1).max(120),
    status: EvaluationStatusSchema,
    mode: z.literal("deterministic_recording"),
    policy_fingerprint: Sha256Schema,
    dataset_sha256: Sha256Schema.nullable(),
    case_count: z.number().int().nonnegative(),
    case_pass_rate: z.number().min(0).max(1).nullable(),
    external_provider_calls: z.number().int().nonnegative().nullable(),
    failure_case_count: z.number().int().nonnegative(),
    created_at: z.iso.datetime(),
    started_at: z.iso.datetime().nullable(),
    finished_at: z.iso.datetime().nullable()
  })
  .strict();

export const EvaluationCaseSchema = z
  .object({
    case_id: z.string().min(1),
    category: z.string().min(1),
    passed: z.boolean(),
    expected_status: z.string(),
    actual_status: z.string(),
    source_recall: z.number().min(0).max(1),
    supported_claims: z.number().int().nonnegative(),
    latency_ms: z.number().nonnegative(),
    failure_reason: z.string().nullable()
  })
  .strict();

export const EvaluationDetailSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    summary: EvaluationSummarySchema,
    report_schema_version: z.number().int().positive().nullable(),
    evaluator_sha256: Sha256Schema.nullable(),
    dataset_name: z.string().nullable(),
    category_counts: z.record(z.string(), z.number().int().nonnegative()),
    metrics: z.record(z.string(), z.number()),
    hard_gates: z.record(z.string(), z.boolean()),
    cases: z.array(EvaluationCaseSchema).max(60),
    failure_case_ids: z.array(z.string()),
    provider_boundary: z.string().min(1),
    triage: FailureTriageSchema,
    error_code: z.string().nullable(),
    error_message: z.string().nullable()
  })
  .strict()
  .superRefine((detail, context) => {
    const failedCases = detail.cases.filter((item) => !item.passed).map((item) => item.case_id).toSorted();
    const declaredFailures = detail.failure_case_ids.toSorted();
    const caseIds = detail.cases.map((item) => item.case_id);
    if (detail.cases.length !== detail.summary.case_count) {
      context.addIssue({
        code: "custom",
        message: "Evaluation case rows must match the summary case count.",
        path: ["cases"]
      });
    }
    if (failedCases.join("\0") !== declaredFailures.join("\0") || declaredFailures.length !== detail.summary.failure_case_count) {
      context.addIssue({
        code: "custom",
        message: "Evaluation failure counts and ids must agree.",
        path: ["failure_case_ids"]
      });
    }
    if (new Set(caseIds).size !== caseIds.length) {
      context.addIssue({ code: "custom", message: "Evaluation case ids must be unique.", path: ["cases"] });
    }
    const categoryTotal = Object.values(detail.category_counts).reduce((total, count) => total + count, 0);
    if (detail.cases.length > 0 && categoryTotal !== detail.summary.case_count) {
      context.addIssue({
        code: "custom",
        message: "Evaluation category counts must cover every case.",
        path: ["category_counts"]
      });
    }
    const metricPassRate = detail.metrics.case_pass_rate;
    if (
      detail.summary.case_pass_rate !== null &&
      typeof metricPassRate === "number" &&
      Math.abs(detail.summary.case_pass_rate - metricPassRate) > 0.000001
    ) {
      context.addIssue({
        code: "custom",
        message: "Summary and metric case pass rates must agree.",
        path: ["metrics", "case_pass_rate"]
      });
    }
    if (detail.summary.status === "passed" && detail.summary.external_provider_calls !== 0) {
      context.addIssue({
        code: "custom",
        message: "A passed deterministic evaluation must report zero external provider calls.",
        path: ["summary", "external_provider_calls"]
      });
    }
    if (detail.summary.status === "passed" && detail.cases.length !== 60) {
      context.addIssue({
        code: "custom",
        message: "A passed fixed evaluation must contain 60 cases.",
        path: ["cases"]
      });
    }
    if (detail.summary.status === "passed" && (!Object.values(detail.hard_gates).every(Boolean) || detail.error_code !== null)) {
      context.addIssue({
        code: "custom",
        message: "A passed evaluation cannot contain failed gates or an error code.",
        path: ["hard_gates"]
      });
    }
    if (!detail.provider_boundary.toLowerCase().includes("not a real-model quality benchmark")) {
      context.addIssue({
        code: "custom",
        message: "The deterministic provider boundary must reject real-model benchmark claims.",
        path: ["provider_boundary"]
      });
    }
  });

export const EvaluationCatalogSchema = z
  .object({ schema_version: SchemaVersionSchema, items: z.array(EvaluationSummarySchema).max(100) })
  .strict();

const MetricDeltaSchema = z
  .object({
    metric: z.string().min(1),
    left: z.number(),
    right: z.number(),
    delta: z.number(),
    preferred_direction: z.enum(["higher", "lower"]),
    improved: z.boolean(),
    regressed: z.boolean()
  })
  .strict()
  .refine((item) => !(item.improved && item.regressed), {
    message: "A metric cannot improve and regress simultaneously."
  });

const GateChangeSchema = z.object({ gate: z.string(), left: z.boolean(), right: z.boolean() }).strict();

export const EvaluationComparisonSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    left_id: z.string().min(1),
    right_id: z.string().min(1),
    compatible: z.boolean(),
    incompatibility_reasons: z.array(z.string()),
    verdict: z.enum(["improved", "stable", "regressed", "incomparable"]),
    policy_changed: z.boolean(),
    left_policy_fingerprint: Sha256Schema,
    right_policy_fingerprint: Sha256Schema,
    metric_deltas: z.array(MetricDeltaSchema),
    gate_changes: z.array(GateChangeSchema),
    new_failure_case_ids: z.array(z.string()),
    resolved_failure_case_ids: z.array(z.string())
  })
  .strict()
  .superRefine((comparison, context) => {
    if (!comparison.compatible && comparison.verdict !== "incomparable") {
      context.addIssue({ code: "custom", message: "Incompatible snapshots must be incomparable.", path: ["verdict"] });
    }
    if (comparison.compatible && comparison.verdict === "incomparable") {
      context.addIssue({ code: "custom", message: "Compatible snapshots need a quality verdict.", path: ["verdict"] });
    }
    if (comparison.policy_changed !== (comparison.left_policy_fingerprint !== comparison.right_policy_fingerprint)) {
      context.addIssue({
        code: "custom",
        message: "Policy change disclosure must match the policy fingerprints.",
        path: ["policy_changed"]
      });
    }
    if (!comparison.compatible && (
      comparison.metric_deltas.length > 0 ||
      comparison.gate_changes.length > 0 ||
      comparison.new_failure_case_ids.length > 0 ||
      comparison.resolved_failure_case_ids.length > 0
    )) {
      context.addIssue({
        code: "custom",
        message: "Incompatible snapshots cannot expose misleading quality deltas.",
        path: ["metric_deltas"]
      });
    }
  });

const TraceEventSchema = z
  .object({
    sequence: z.number().int().positive(),
    run_version: z.number().int().positive(),
    event_type: z.string().min(1),
    visibility: z.string().min(1),
    redacted: z.boolean(),
    facts: z.array(z.string()),
    elapsed_ms: z.number().int().nonnegative(),
    delta_ms: z.number().int().nonnegative(),
    step_id: z.string().nullable(),
    tool_call_id: z.string().nullable()
  })
  .strict()
  .superRefine((event, context) => {
    if (event.redacted && event.facts.length > 0) {
      context.addIssue({ code: "custom", message: "Redacted events cannot expose facts.", path: ["facts"] });
    }
    if (event.visibility !== "public" && !event.redacted) {
      context.addIssue({ code: "custom", message: "Non-public events must be redacted.", path: ["redacted"] });
    }
  });

const TraceToolCallSchema = z
  .object({
    id: z.string().min(1),
    tool_name: z.string().min(1),
    tool_version: z.string().min(1),
    effect: z.string().min(1),
    status: z.string().min(1),
    arguments_digest: Sha256Schema,
    error_code: z.string().nullable(),
    duration_ms: z.number().int().nonnegative().nullable()
  })
  .strict();

const TraceModelCallSchema = z
  .object({
    id: z.string().min(1),
    operation: z.string().min(1),
    provider: z.string().min(1),
    model: z.string().min(1),
    status: z.string().min(1),
    input_tokens: z.number().int().nonnegative(),
    output_tokens: z.number().int().nonnegative(),
    cost_micros: z.number().int().nonnegative(),
    latency_ms: z.number().int().nonnegative(),
    retries: z.number().int().nonnegative(),
    usage_estimated: z.boolean(),
    error_code: z.string().nullable()
  })
  .strict();

const PolicyFactSchema = z.object({ policy_id: z.string(), version: z.string(), source: z.string() }).strict();

const ReplayIntegritySchema = z
  .object({
    digest: Sha256Schema,
    sequence_contiguous: z.boolean(),
    trace_id_consistent: z.boolean(),
    stored_terminal_state: z.string(),
    replayed_terminal_state: z.string().nullable(),
    stored_state_matches: z.boolean(),
    event_count: z.number().int().nonnegative(),
    redacted_event_count: z.number().int().nonnegative(),
    checkpoint_count: z.number().int().nonnegative(),
    latest_checkpoint_checksum: Sha256Schema.nullable()
  })
  .strict();

export const RunTraceSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    run_id: z.string().min(1),
    trace_id: z.string().min(1),
    goal: z.string(),
    requested_mode: z.string(),
    effective_mode: z.string().nullable(),
    status: z.string(),
    phase: z.string(),
    provider_mode: z.string(),
    created_at: z.iso.datetime(),
    started_at: z.iso.datetime().nullable(),
    finished_at: z.iso.datetime().nullable(),
    active_elapsed_ms: z.number().int().nonnegative(),
    budget_limits: z.record(z.string(), z.number().int().nonnegative()),
    budget_usage: z.record(z.string(), z.number().int().nonnegative()),
    events: z.array(TraceEventSchema),
    tool_calls: z.array(TraceToolCallSchema),
    model_calls: z.array(TraceModelCallSchema),
    policies: z.array(PolicyFactSchema),
    replay: ReplayIntegritySchema,
    triage: FailureTriageSchema,
    warnings: z.array(z.string())
  })
  .strict()
  .superRefine((trace, context) => {
    const redactedCount = trace.events.filter((event) => event.redacted).length;
    if (trace.replay.event_count !== trace.events.length || trace.replay.redacted_event_count !== redactedCount) {
      context.addIssue({
        code: "custom",
        message: "Replay counts must match the returned trace events.",
        path: ["replay", "event_count"]
      });
    }
    if (trace.replay.sequence_contiguous && trace.events.some((event, index) => event.sequence !== index + 1)) {
      context.addIssue({
        code: "custom",
        message: "A contiguous replay must contain exact 1-based event sequences.",
        path: ["events"]
      });
    }
    const terminal = new Set(["completed", "insufficient_evidence", "cancelled", "failed"]);
    if (
      trace.replay.stored_state_matches &&
      terminal.has(trace.replay.stored_terminal_state) &&
      trace.replay.replayed_terminal_state !== trace.replay.stored_terminal_state
    ) {
      context.addIssue({
        code: "custom",
        message: "A matching terminal replay must agree with stored state.",
        path: ["replay", "stored_state_matches"]
      });
    }
  });

export type EvaluationCatalog = z.infer<typeof EvaluationCatalogSchema>;
export type EvaluationComparison = z.infer<typeof EvaluationComparisonSchema>;
export type EvaluationDetail = z.infer<typeof EvaluationDetailSchema>;
export type EvaluationReceipt = z.infer<typeof EvaluationReceiptSchema>;
export type EvaluationStatus = z.infer<typeof EvaluationStatusSchema>;
export type EvaluationSummary = z.infer<typeof EvaluationSummarySchema>;
export type RunTrace = z.infer<typeof RunTraceSchema>;
export type StartEvaluationInput = z.input<typeof StartEvaluationInputSchema>;
