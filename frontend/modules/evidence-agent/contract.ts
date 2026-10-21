import { z } from "zod";

export const SchemaVersionSchema = z.literal(1);
const PositiveIdSchema = z.number().int().positive();
const Sha256Schema = z.string().regex(/^[a-fA-F0-9]{64}$/);

export const EvidenceLocatorSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("page"), page_number: PositiveIdSchema }).passthrough(),
  z
    .object({ kind: z.literal("time"), start_ms: z.number().int().nonnegative(), end_ms: z.number().int().nonnegative().optional() })
    .passthrough()
    .refine((value) => value.end_ms === undefined || value.end_ms >= value.start_ms, { path: ["end_ms"] }),
  z
    .object({ kind: z.literal("code"), file_path: z.string().min(1), line_start: PositiveIdSchema, line_end: PositiveIdSchema.optional() })
    .passthrough()
    .refine((value) => value.line_end === undefined || value.line_end >= value.line_start, { path: ["line_end"] }),
  z.object({ kind: z.literal("region"), region: z.tuple([z.number(), z.number(), z.number(), z.number()]) }).passthrough(),
  z
    .object({
      kind: z.literal("text"),
      start_offset: z.number().int().nonnegative().optional(),
      end_offset: z.number().int().nonnegative().optional()
    })
    .passthrough()
    .refine(
      (value) => value.start_offset === undefined || value.end_offset === undefined || value.end_offset >= value.start_offset,
      { path: ["end_offset"] }
    ),
  z.object({ kind: z.literal("document_page"), page_number: PositiveIdSchema }).passthrough(),
  z.object({ kind: z.literal("document_chunk") }).passthrough(),
  z
    .object({ kind: z.literal("media_time"), start_ms: z.number().int().nonnegative(), end_ms: z.number().int().nonnegative().optional() })
    .passthrough()
    .refine((value) => value.end_ms === undefined || value.end_ms >= value.start_ms, { path: ["end_ms"] }),
  z
    .object({ kind: z.literal("code_range"), file_path: z.string().min(1), line_start: PositiveIdSchema, line_end: PositiveIdSchema.optional() })
    .passthrough()
    .refine((value) => value.line_end === undefined || value.line_end >= value.line_start, { path: ["line_end"] }),
  z.object({ kind: z.literal("image_region") }).passthrough(),
  z
    .object({
      kind: z.literal("pdf_page"),
      page: PositiveIdSchema.optional(),
      page_number: PositiveIdSchema.optional()
    })
    .passthrough()
    .refine((value) => value.page !== undefined || value.page_number !== undefined, { path: ["page"] })
]);

export const EvidenceReferenceSchema = z
  .object({
    source_id: PositiveIdSchema,
    revision_id: PositiveIdSchema,
    index_revision_id: PositiveIdSchema,
    chunk_id: PositiveIdSchema,
    content_hash: Sha256Schema,
    locator: EvidenceLocatorSchema
  })
  .strict();

export const EvidenceRelationSchema = z.enum([
  "candidate",
  "supports",
  "contradicts",
  "contextual",
  "excluded"
]);

export const PlanCreatedPayloadSchema = z
  .object({
    plan_version: z.number().int().positive(),
    strategy: z.string().min(1),
    requirements: z.array(z.string().trim().min(1)).min(1).max(8)
  })
  .strict();

export const EvidenceAddedPayloadSchema = z
  .object({
    evidence_id: z.string().min(1),
    source_title: z.string().min(1),
    excerpt: z.string(),
    relation: EvidenceRelationSchema,
    reference: EvidenceReferenceSchema
  })
  .strict();

export const EvidenceRelationChangedPayloadSchema = z
  .object({
    evidence_id: z.string().min(1),
    requirement_id: z.string().min(1),
    requirement_ordinal: z.number().int().positive(),
    previous_relation: EvidenceRelationSchema,
    relation: EvidenceRelationSchema,
    reason: z.string().min(1),
    method: z.string().min(1)
  })
  .strict();

const ClaimEvidenceReferenceSchema = EvidenceReferenceSchema.extend({
  relation: z.enum(["supports", "contradicts", "contextual", "excluded"])
});

const FactualClaimSchema = z
  .object({
    claim_id: z.string().min(1),
    kind: z.literal("factual"),
    text: z.string().min(1),
    evidence_refs: z.array(ClaimEvidenceReferenceSchema).min(1)
  })
  .strict();

export const EvidenceGapSchema = z
  .object({
    gap_id: z.string().min(1),
    requirement: z.string().min(1),
    reason: z.string().min(1),
    next_queries: z.array(z.string().min(1))
  })
  .strict();

export const ArtifactSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    artifact_id: z.string().min(1),
    producing_run_id: z.string().min(1),
    kind: z.enum(["answer", "research_report", "comparison", "evidence_gap_report"]),
    title: z.string().min(1),
    claims: z.array(FactualClaimSchema),
    gaps: z.array(EvidenceGapSchema),
    created_at: z.iso.datetime()
  })
  .strict();

export const ResearchOutcomeSchema = z
  .object({
    kind: z.literal("insufficient_evidence"),
    stop_reason: z.enum(["budget_exhausted", "no_new_evidence", "requirements_uncovered"]),
    artifact: ArtifactSchema
  })
  .strict();

const DEFAULT_BUDGET_LIMITS = {
  max_steps: 8,
  max_tool_calls: 12,
  max_model_calls: 6,
  max_model_input_tokens: 24_000,
  max_model_output_tokens: 6_000,
  max_cost_micros: 1_000_000,
  max_active_ms: 180_000,
  max_no_new_evidence_rounds: 2,
  max_query_rewrites: 3,
  max_evidence_records: 40,
  max_context_tokens: 16_000
};

export const BudgetLimitsSchema = z
  .object({
    max_steps: z.number().int().min(1).max(64).default(8),
    max_tool_calls: z.number().int().min(1).max(128).default(12),
    max_model_calls: z.number().int().min(1).max(32).default(6),
    max_model_input_tokens: z.number().int().min(1).max(1_000_000).default(24_000),
    max_model_output_tokens: z.number().int().min(1).max(128_000).default(6_000),
    max_cost_micros: z.number().int().min(1).max(100_000_000).default(1_000_000),
    max_active_ms: z.number().int().min(1_000).max(3_600_000).default(180_000),
    max_no_new_evidence_rounds: z.number().int().min(1).max(10).default(2),
    max_query_rewrites: z.number().int().min(1).max(20).default(3),
    max_evidence_records: z.number().int().min(1).max(500).default(40),
    max_context_tokens: z.number().int().min(1).max(1_000_000).default(16_000)
  })
  .strict();

export const StartRunInputSchema = z
  .object({
    schema_version: SchemaVersionSchema.default(1),
    request_id: z.string().min(1).max(120),
    space_id: PositiveIdSchema,
    goal: z.string().trim().min(1).max(12_000),
    scope: z.object({ source_ids: z.array(PositiveIdSchema).default([]) }).strict().default({ source_ids: [] }),
    deliverable: z
      .object({
        kind: z.enum(["answer", "research_report", "comparison", "evidence_gap_report"]).default("answer"),
        title: z.string().max(255).nullable().optional()
      })
      .strict()
      .default({ kind: "answer" }),
    mode: z.enum(["auto", "force_quick", "force_agent"]).default("auto"),
    budget: BudgetLimitsSchema.default(DEFAULT_BUDGET_LIMITS),
    permissions: z
      .object({ read_only: z.boolean().default(true), allow_scope_expansion: z.boolean().default(false) })
      .strict()
      .default({ read_only: true, allow_scope_expansion: false }),
    provider_mode: z.enum(["real", "demo", "recording"]).default("real")
  })
  .strict();

export const RunCommandSchema = z
  .object({
    schema_version: SchemaVersionSchema.default(1),
    request_id: z.string().min(1).max(120),
    expected_version: z.number().int().min(1),
    signal: z.enum(["provide_input", "approve", "reject", "modify", "pause", "resume", "cancel"]),
    response: z.record(z.string(), z.unknown()).default({}),
    proposal_digest: Sha256Schema.nullable().optional()
  })
  .strict();

export const RunStatusSchema = z.enum([
  "queued",
  "routing",
  "planned",
  "running",
  "awaiting_input",
  "awaiting_approval",
  "paused",
  "completed",
  "insufficient_evidence",
  "cancelled",
  "failed"
]);

export const RunPhaseSchema = z.enum(["route", "plan", "retrieve", "assess", "synthesize", "verify", "persist_artifact"]);
export const RunModeSchema = z.enum(["auto", "force_quick", "force_agent"]);
export const CostMeasurementSchema = z.enum(["reported", "estimated", "unknown", "partial_unknown"]);

const ScopedRevisionSchema = z
  .object({ source_id: PositiveIdSchema, revision_id: PositiveIdSchema, index_revision_id: PositiveIdSchema, content_hash: Sha256Schema })
  .strict();

const RunOutcomeSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("artifact"), artifact_id: z.string().min(1) }).strict(),
  z.object({ kind: z.literal("insufficient_evidence"), reason: z.string().min(1), gaps: z.array(z.string()) }).strict()
]);

export const RunViewSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    id: z.string().min(1),
    space_id: PositiveIdSchema,
    goal: z.string().min(1),
    requested_mode: RunModeSchema,
    effective_mode: RunModeSchema.nullable(),
    status: RunStatusSchema,
    phase: RunPhaseSchema,
    version: z.number().int().min(1),
    execution_epoch: z.number().int().nonnegative(),
    scope_snapshot: z.object({ space_id: PositiveIdSchema, revisions: z.array(ScopedRevisionSchema) }).strict(),
    budget_limits: z.record(z.string(), z.number().int().nonnegative()),
    budget_usage: z.record(z.string(), z.number().int().nonnegative()),
    cost_measurement: CostMeasurementSchema.default("unknown"),
    provider_mode: z.string().min(1),
    last_event_cursor: z.number().int().nonnegative(),
    final_artifact_id: z.string().min(1).nullable(),
    termination_reason: z.string().min(1).nullable(),
    outcome: RunOutcomeSchema.nullable().default(null)
  })
  .strict();

export const RunChangeSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("snapshot"), reset: z.boolean(), view: RunViewSchema }).strict(),
  z.object({ type: z.literal("status_changed"), status: RunStatusSchema }).strict(),
  z.object({ type: z.literal("domain_event"), event_type: z.string().min(1), payload: z.record(z.string(), z.unknown()) }).strict()
]);

export const RunEventSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    event_id: z.string().min(1),
    cursor: z.number().int().nonnegative(),
    run_id: z.string().min(1),
    run_version: z.number().int().min(1),
    change: RunChangeSchema
  })
  .strict();

export const SseFrameSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    cursor: z.number().int().nonnegative(),
    run_version: z.number().int().min(1),
    type: z.string().min(1),
    payload: z.record(z.string(), z.unknown())
  })
  .strict();

export const CommandReceiptSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    command_id: z.string().min(1),
    run_id: z.string().min(1),
    run_version: z.number().int().min(1),
    status: RunStatusSchema,
    cursor: z.number().int().nonnegative(),
    replayed: z.boolean()
  })
  .strict();

export const RunReceiptSchema = z
  .object({ schema_version: SchemaVersionSchema, run_id: z.string().min(1), cursor: z.number().int().nonnegative(), view: RunViewSchema })
  .strict();

export const RunCatalogSchema = z
  .object({ schema_version: SchemaVersionSchema, items: z.array(RunViewSchema) })
  .strict();

export const ArtifactSummarySchema = z
  .object({
    id: z.string().min(1),
    producing_run_id: z.string().min(1),
    kind: z.string().min(1),
    title: z.string().min(1),
    status: z.string().min(1)
  })
  .strict();

export const ArtifactCatalogSchema = z
  .object({ schema_version: SchemaVersionSchema, items: z.array(ArtifactSummarySchema) })
  .strict();

export const ArtifactClaimSchema = z
  .object({
    id: z.string().min(1),
    ordinal: PositiveIdSchema,
    text: z.string().min(1),
    kind: z.string().min(1),
    verification_status: z.string().min(1),
    evidence_ids: z.array(z.string().min(1))
  })
  .strict()
  .refine((claim) => claim.kind !== "factual" || claim.evidence_ids.length > 0, {
    message: "A factual claim must bind at least one evidence id.",
    path: ["evidence_ids"]
  });

export const ArtifactDetailSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    id: z.string().min(1),
    producing_run_id: z.string().min(1),
    kind: z.string().min(1),
    title: z.string().min(1),
    body_markdown: z.string(),
    status: z.string().min(1),
    claims: z.array(ArtifactClaimSchema)
  })
  .strict();

const PersistedEvidenceLocatorSchema = z
  .record(z.string(), z.unknown())
  .refine((locator) => typeof locator.kind === "string" && locator.kind.length > 0, {
    message: "Evidence locator must declare a kind.",
    path: ["kind"]
  });

export const EvidenceDetailSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    id: z.string().min(1),
    run_id: z.string().min(1),
    source_id: PositiveIdSchema,
    revision_id: PositiveIdSchema,
    index_revision_id: PositiveIdSchema,
    chunk_id: PositiveIdSchema,
    source_type: z.string().min(1),
    locator: PersistedEvidenceLocatorSchema,
    revision_content_hash: Sha256Schema,
    content_hash: Sha256Schema,
    excerpt_preview: z.string(),
    claim_ids: z.array(z.string().min(1))
  })
  .strict();

export type Artifact = z.infer<typeof ArtifactSchema>;
export type ArtifactCatalog = z.infer<typeof ArtifactCatalogSchema>;
export type ArtifactClaim = z.infer<typeof ArtifactClaimSchema>;
export type ArtifactDetail = z.infer<typeof ArtifactDetailSchema>;
export type ArtifactSummary = z.infer<typeof ArtifactSummarySchema>;
export type CommandReceipt = z.infer<typeof CommandReceiptSchema>;
export type EvidenceDetail = z.infer<typeof EvidenceDetailSchema>;
export type EvidenceGap = z.infer<typeof EvidenceGapSchema>;
export type EvidenceLocator = z.infer<typeof EvidenceLocatorSchema>;
export type EvidenceReference = z.infer<typeof EvidenceReferenceSchema>;
export type EvidenceRelation = z.infer<typeof EvidenceRelationSchema>;
export type PlanCreatedPayload = z.infer<typeof PlanCreatedPayloadSchema>;
export type ResearchOutcome = z.infer<typeof ResearchOutcomeSchema>;
export type RunChange = z.infer<typeof RunChangeSchema>;
export type RunCatalog = z.infer<typeof RunCatalogSchema>;
export type RunCommand = z.input<typeof RunCommandSchema>;
export type RunEvent = z.infer<typeof RunEventSchema>;
export type RunReceipt = z.infer<typeof RunReceiptSchema>;
export type RunView = z.infer<typeof RunViewSchema>;
export type StartRunInput = z.input<typeof StartRunInputSchema>;
