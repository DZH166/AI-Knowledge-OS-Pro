import { z } from "zod";


const SafeIdSchema = z.string().min(1).max(36).regex(/^[A-Za-z0-9_-]+$/);
const Sha256Schema = z.string().regex(/^[a-fA-F0-9]{64}$/);
const DateTimeSchema = z.iso.datetime();
const NullableDateTimeSchema = DateTimeSchema.nullable();
export const StudyStatusSchema = z.enum(["pending", "running", "completed", "cancelled", "failed"]);
export const TrialStatusSchema = z.enum(["pending", "running", "completing", "completed", "failed", "cancelled"]);
export const StudyObjectiveSchema = z.enum(["quality_first", "balanced", "cost_first"]);
export const OptimizerMetricNameSchema = z.enum([
  "case_pass_rate", "mean_source_recall", "citation_completeness",
  "latency_ms", "retrieval_window", "external_provider_calls"
]);
export const EvaluationCategorySchema = z.enum([
  "cancel_recovery", "cross_modal", "insufficient_evidence", "multi_hop",
  "prompt_injection", "single_hop", "version_conflict"
]);
export const StudyEventTypeSchema = z.enum([
  "study_created", "study_started", "trial_created", "trial_completed",
  "trial_failed", "trial_cancelled", "round_started", "recommendation_updated",
  "study_completed", "study_failed", "study_cancelled", "draft_converted"
]);

const BoundSchema = z.object({ minimum: z.number().int(), maximum: z.number().int() }).strict()
  .refine((value) => value.minimum <= value.maximum, "minimum cannot exceed maximum");

export const SearchSpaceSchema = z.object({
  factual_top_k: BoundSchema,
  comparative_top_k: BoundSchema,
  temporal_top_k: BoundSchema,
  minimum_score_millis: BoundSchema,
  max_hits_per_source: BoundSchema,
  neighbor_before: BoundSchema,
  neighbor_after: BoundSchema
}).strict();

export const ScoreWeightsSchema = z.object({
  quality_weight_permille: z.number().int().min(0).max(1_000),
  cost_weight_permille: z.number().int().min(0).max(1_000)
}).strict().refine(
  (value) => value.quality_weight_permille + value.cost_weight_permille > 0,
  "at least one weight must be positive"
);

const BudgetSchema = z.object({
  max_candidates: z.number().int().min(1).max(64),
  max_evaluations: z.number().int().min(1).max(128),
  deadline_at: DateTimeSchema.nullable().optional()
}).strict();

const BudgetUsageSchema = z.object({
  created_trials: z.number().int().nonnegative(),
  started_evaluations: z.number().int().nonnegative()
}).strict();

export const StudyTemplateSchema = z.object({
  key: z.enum(["quality_first", "balanced", "cost_first"]),
  description: z.string().min(1),
  objective: StudyObjectiveSchema,
  max_candidates: z.number().int().min(1).max(64),
  max_evaluations: z.number().int().min(1).max(128),
  seed: z.number().int().min(0),
  search_space: SearchSpaceSchema,
  weights: ScoreWeightsSchema
}).strict();

export const StudyTemplateCatalogSchema = z.object({ items: z.array(StudyTemplateSchema).length(3) }).strict();

const TemplateOverridesSchema = z.object({
  seed: z.number().int().min(0).max(2_147_483_647).optional(),
  max_candidates: z.number().int().min(1).max(4).optional(),
  max_evaluations: z.number().int().min(1).max(8).optional(),
  warm_start_study_id: SafeIdSchema.optional()
}).strict();

export const CreateStudyFromTemplateInputSchema = z.object({
  schema_version: z.literal(1),
  request_id: z.string().min(1).max(120).regex(/^[A-Za-z0-9_.:@-]+$/),
  label: z.string().trim().min(1).max(120),
  base_policy_id: SafeIdSchema,
  template_key: z.enum(["quality_first", "balanced", "cost_first"]),
  overrides: TemplateOverridesSchema
}).strict();

export const StudySummarySchema = z.object({
  id: SafeIdSchema,
  label: z.string().min(1).max(120),
  objective: StudyObjectiveSchema,
  status: StudyStatusSchema,
  base_policy_fingerprint: Sha256Schema,
  budget_usage: BudgetUsageSchema,
  created_at: DateTimeSchema
}).strict();

export const StudyCatalogSchema = z.object({ items: z.array(StudySummarySchema).max(100) }).strict();

export const StudyDetailSchema = z.object({
  id: SafeIdSchema,
  request_id: z.string().min(1).max(120),
  label: z.string().min(1).max(120),
  objective: StudyObjectiveSchema,
  status: StudyStatusSchema,
  base_policy_id: SafeIdSchema,
  base_policy_fingerprint: Sha256Schema,
  search_space: SearchSpaceSchema,
  weights: ScoreWeightsSchema,
  budget: BudgetSchema,
  budget_usage: BudgetUsageSchema,
  seed: z.number().int().min(0),
  algorithm_version: z.string().min(1),
  created_at: NullableDateTimeSchema,
  started_at: NullableDateTimeSchema,
  finished_at: NullableDateTimeSchema,
  cancelled_at: NullableDateTimeSchema,
  round_no: z.number().int().positive(),
  warm_start_study_id: SafeIdSchema.nullable(),
  next_round_request_id: z.string().nullable()
}).strict();

export const TrialMetricsSchema = z.object({
  case_pass_rate: z.number().min(0).max(1),
  mean_source_recall: z.number().min(0).max(1),
  citation_completeness: z.number().min(0).max(1),
  latency_ms: z.number().nonnegative(),
  retrieval_window: z.number().int().positive(),
  external_provider_calls: z.literal(0)
}).strict();

export const NormalizedMetricsSchema = z.object({
  case_pass_rate: z.number().min(0).max(1),
  mean_source_recall: z.number().min(0).max(1),
  citation_completeness: z.number().min(0).max(1),
  latency_ms: z.number().min(0).max(1),
  retrieval_window: z.number().min(0).max(1),
  external_provider_calls: z.number().min(0).max(1)
}).strict();

const CaseFactSchema = z.object({
  case_id: z.string().min(1).max(120),
  category: EvaluationCategorySchema,
  passed: z.boolean(),
  source_recall: z.number().min(0).max(1),
  latency_ms: z.number().nonnegative()
}).strict();

const CategoryAggregateSchema = z.object({
  passed: z.number().int().nonnegative(),
  total: z.number().int().positive(),
  mean_source_recall: z.number().min(0).max(1)
}).strict();

export const CategoryStatsSchema = z.object({
  schema_version: z.literal(1),
  categories: z.record(EvaluationCategorySchema, CategoryAggregateSchema),
  cases: z.array(CaseFactSchema).length(60)
}).strict();

export const TrialSummarySchema = z.object({
  id: SafeIdSchema,
  study_id: SafeIdSchema,
  ordinal: z.number().int().positive(),
  status: TrialStatusSchema,
  config_sha256: Sha256Schema,
  is_baseline: z.boolean(),
  evaluation_id: SafeIdSchema.nullable(),
  draft_policy_id: SafeIdSchema.nullable(),
  category_stats: CategoryStatsSchema.nullable(),
  round_no: z.number().int().positive(),
  metrics: TrialMetricsSchema.nullable(),
  normalized_metrics: NormalizedMetricsSchema.nullable(),
  score_millis: z.number().int().min(0).max(1_000).nullable(),
  recommendation_rank: z.number().int().positive().nullable(),
  failure_code: z.string().nullable(),
  attempt: z.number().int().nonnegative(),
  external_provider_calls: z.literal(0).nullable(),
  created_at: NullableDateTimeSchema,
  finished_at: NullableDateTimeSchema
}).strict();

export const TrialCatalogSchema = z.object({ items: z.array(TrialSummarySchema).max(200) }).strict();

const RoundSchema = z.object({
  round_no: z.number().int().positive(), total: z.number().int().nonnegative(),
  completed: z.number().int().nonnegative(), failed: z.number().int().nonnegative(),
  cancelled: z.number().int().nonnegative(), best_score_millis: z.number().int().min(0).max(1_000).nullable()
}).strict();

const OverviewTrialSchema = z.object({
  id: SafeIdSchema, ordinal: z.number().int().positive(), round_no: z.number().int().positive(),
  status: TrialStatusSchema, score_millis: z.number().int().min(0).max(1_000).nullable(),
  draft_policy_id: SafeIdSchema.nullable(), recommendation_rank: z.number().int().positive().nullable(),
  failure_code: z.string().nullable(), eligible: z.boolean(), metrics: TrialMetricsSchema.nullable()
}).strict();

const OverviewRecommendationSchema = z.object({
  rank: z.number().int().positive(), trial_id: SafeIdSchema,
  score_millis: z.number().int().min(0).max(1_000).nullable(), converted: z.boolean(),
  draft_policy_id: SafeIdSchema.nullable(), rationale_first_line: z.string().min(1)
}).strict();

export const OverviewActionSchema = z.object({
  action: z.enum(["start", "next-round", "cancel", "fail", "retry", "convert-draft", "recover"]),
  available: z.boolean(),
  reason: z.string().min(1)
}).strict();

export const StudyOverviewSchema = z.object({
  study: StudyDetailSchema,
  rounds: z.array(RoundSchema),
  trials: z.array(OverviewTrialSchema),
  frontier: z.array(z.object({ trial_id: SafeIdSchema, ordinal: z.number().int().positive() }).strict()),
  recommendation: z.array(OverviewRecommendationSchema),
  actions: z.array(OverviewActionSchema)
}).strict();

export const StudyMutationReceiptSchema = z.object({
  study_id: SafeIdSchema,
  status: StudyStatusSchema,
  created: z.number().int().nonnegative().nullable(),
  cancelled: z.boolean().nullable(),
  replayed: z.boolean()
}).strict();

export const StudyEventCatalogSchema = z.object({
  study_id: SafeIdSchema,
  items: z.array(z.object({
    id: SafeIdSchema,
    event_type: StudyEventTypeSchema,
    round_no: z.number().int().positive(),
    payload: z.record(
      z.string(),
      z.union([z.string(), z.number().int(), z.boolean(), z.array(z.string())])
    ),
    created_at: DateTimeSchema
  }).strict()).max(200)
}).strict();

export const DiffReceiptSchema = z.object({
  study_id: SafeIdSchema, trial_id: SafeIdSchema, trial_config_sha256: Sha256Schema,
  active_policy_id: SafeIdSchema, active_policy_version: z.number().int().positive(),
  active_config_sha256: Sha256Schema, compatible: z.boolean(),
  incompatibility_reasons: z.array(z.string()),
  changes: z.array(z.object({ field: z.string(), left: z.number().int(), right: z.number().int() }).strict()),
  trial_summary: z.object({
    eligible: z.boolean(), score_millis: z.number().int().min(0).max(1_000).nullable(),
    case_pass_rate: z.number().min(0).max(1).nullable()
  }).strict()
}).strict();

const CategoryRowSchema = z.object({
  category: EvaluationCategorySchema, case_count: z.number().int().positive(),
  pass_rate_left: z.number().min(0).max(1), pass_rate_right: z.number().min(0).max(1),
  mean_source_recall_left: z.number().min(0).max(1), mean_source_recall_right: z.number().min(0).max(1),
  wins: z.number().int().nonnegative(), ties: z.number().int().nonnegative(), losses: z.number().int().nonnegative(),
  verdict: z.enum(["improved", "regressed", "tied"])
}).strict();

export const CategoryComparisonSchema = z.object({
  study_id: SafeIdSchema, trial_id: SafeIdSchema, baseline_trial_id: SafeIdSchema,
  items: z.array(CategoryRowSchema).length(7)
}).strict();

export const RecommendationBundleSchema = z.object({
  study_id: SafeIdSchema,
  algorithm_version: z.string().min(1),
  candidates: z.array(z.object({
    rank: z.number().int().positive(), trial_id: SafeIdSchema, policy_fingerprint: Sha256Schema,
    policy_snapshot_json: z.string().min(2).max(65_536), evaluation_id: SafeIdSchema,
    evaluation_fingerprint: Sha256Schema, evaluation_report_sha256: Sha256Schema,
    score_millis: z.number().int().min(0).max(1_000), dominates_baseline: z.boolean(),
    improved_metrics: z.array(OptimizerMetricNameSchema), unchanged_metrics: z.array(OptimizerMetricNameSchema),
    regressed_metrics: z.array(OptimizerMetricNameSchema), rationale: z.string().min(1), algorithm_version: z.string().min(1)
  }).strict())
}).strict();

export const ExportComparisonReceiptSchema = z.object({
  study_id: SafeIdSchema,
  markdown: z.string().min(1),
  sha256: Sha256Schema,
  generated_trial_ids: z.array(SafeIdSchema).min(2).max(3)
}).strict();

export const ConvertReceiptSchema = z.object({
  command_id: z.string(), policy_id: SafeIdSchema, policy_version: z.number().int().positive(),
  status: z.enum(["draft", "active", "retired"]), policy_config_sha256: Sha256Schema, replayed: z.boolean()
}).strict();

export type StudyTemplate = z.infer<typeof StudyTemplateSchema>;
export type StudySummary = z.infer<typeof StudySummarySchema>;
export type StudyOverview = z.infer<typeof StudyOverviewSchema>;
export type StudyEventCatalog = z.infer<typeof StudyEventCatalogSchema>;
export type TrialSummary = z.infer<typeof TrialSummarySchema>;
export type DiffReceipt = z.infer<typeof DiffReceiptSchema>;
export type CategoryComparison = z.infer<typeof CategoryComparisonSchema>;
export type RecommendationBundle = z.infer<typeof RecommendationBundleSchema>;
export type ExportComparisonReceipt = z.infer<typeof ExportComparisonReceiptSchema>;
export type CreateStudyFromTemplateInput = z.input<typeof CreateStudyFromTemplateInputSchema>;
