import { z } from "zod";


const SchemaVersionSchema = z.literal(1);
const SafeIdSchema = z.string().min(1).max(36).regex(/^[A-Za-z0-9_-]+$/);
const Sha256Schema = z.string().regex(/^[a-fA-F0-9]{64}$/);
export const PolicyStatusSchema = z.enum(["draft", "active", "retired"]);

export const RETRIEVAL_POLICY_FIELD_SPECS = {
  factual_top_k: { min: 1, max: 50, defaultValue: 8 },
  comparative_top_k: { min: 1, max: 50, defaultValue: 14 },
  temporal_top_k: { min: 1, max: 50, defaultValue: 12 },
  minimum_score_millis: { min: 0, max: 1_000, defaultValue: 0 },
  max_hits_per_source: { min: 1, max: 20, defaultValue: 3 },
  neighbor_before: { min: 0, max: 3, defaultValue: 1 },
  neighbor_after: { min: 0, max: 3, defaultValue: 1 }
} as const;

export type RetrievalPolicyConfigField = keyof typeof RETRIEVAL_POLICY_FIELD_SPECS;

export const RETRIEVAL_POLICY_FIELDS = (
  Object.entries(RETRIEVAL_POLICY_FIELD_SPECS) as Array<[
    RetrievalPolicyConfigField,
    { min: number; max: number; defaultValue: number }
  ]>
).map(([name, spec]) => ({ name, ...spec }));

const RetrievalPolicyFieldShape = Object.fromEntries(
  RETRIEVAL_POLICY_FIELDS.map(({ name, min, max, defaultValue }) => [
    name,
    z.number().int().min(min).max(max).default(defaultValue)
  ])
) as Record<RetrievalPolicyConfigField, z.ZodDefault<z.ZodNumber>>;

export const RetrievalPolicyConfigSchema = z
  .object({
    schema_version: SchemaVersionSchema.default(1),
    ...RetrievalPolicyFieldShape
  })
  .strict();

export const CreatePolicyInputSchema = z
  .object({
    schema_version: SchemaVersionSchema.default(1),
    request_id: z.string().trim().min(1).max(120),
    label: z.string().trim().min(1).max(120),
    base_policy_id: SafeIdSchema,
    config: RetrievalPolicyConfigSchema
  })
  .strict();

export const PolicyReceiptSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    command_id: SafeIdSchema,
    policy_id: SafeIdSchema,
    version: z.number().int().positive(),
    status: PolicyStatusSchema,
    active_policy_id: SafeIdSchema,
    replayed: z.boolean()
  })
  .strict();

export const PolicySummarySchema = z
  .object({
    id: SafeIdSchema,
    policy_key: z.string().min(1).max(80),
    version: z.number().int().positive(),
    label: z.string().min(1).max(120),
    status: PolicyStatusSchema,
    config_sha256: Sha256Schema,
    base_policy_id: SafeIdSchema.nullable(),
    has_been_active: z.boolean(),
    created_at: z.iso.datetime(),
    activated_at: z.iso.datetime().nullable(),
    retired_at: z.iso.datetime().nullable()
  })
  .strict();

export const PolicyDetailSchema = PolicySummarySchema.extend({
  config: RetrievalPolicyConfigSchema
}).strict();

export const PolicyCatalogSchema = z
  .object({ schema_version: SchemaVersionSchema, items: z.array(PolicySummarySchema).max(100) })
  .strict();

const PolicyConfigFieldSchema = z.enum(
  RETRIEVAL_POLICY_FIELDS.map((field) => field.name) as [
    RetrievalPolicyConfigField,
    ...RetrievalPolicyConfigField[]
  ]
);

const PolicyConfigChangeSchema = z
  .object({ field: PolicyConfigFieldSchema, left: z.number().int(), right: z.number().int() })
  .strict();

export const PolicyComparisonSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    left_id: SafeIdSchema,
    right_id: SafeIdSchema,
    left_fingerprint: Sha256Schema,
    right_fingerprint: Sha256Schema,
    compatible: z.boolean(),
    incompatibility_reasons: z.array(z.string()),
    changes: z.array(PolicyConfigChangeSchema)
  })
  .strict()
  .superRefine((comparison, context) => {
    if (!comparison.compatible && comparison.changes.length > 0) {
      context.addIssue({
        code: "custom",
        message: "Incompatible policies cannot expose field changes.",
        path: ["changes"]
      });
    }
    if (new Set(comparison.changes.map((item) => item.field)).size !== comparison.changes.length) {
      context.addIssue({ code: "custom", message: "Policy change fields must be unique.", path: ["changes"] });
    }
  });

const PolicySimulationDecisionSchema = z
  .object({
    sequence: z.number().int().positive(),
    tool: z.enum(["search_evidence", "read_neighbors"]),
    changed: z.boolean(),
    recorded_top_k: z.number().int().nullable(),
    candidate_top_k: z.number().int().nullable(),
    recorded_before: z.number().int().nullable(),
    candidate_before: z.number().int().nullable(),
    recorded_after: z.number().int().nullable(),
    candidate_after: z.number().int().nullable()
  })
  .strict();

export const PolicySimulationSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    run_id: SafeIdSchema,
    policy_id: SafeIdSchema,
    policy_version: z.number().int().positive(),
    changed_decision_count: z.number().int().nonnegative(),
    projected_candidate_window_delta: z.number().int(),
    projected_neighbor_context_delta: z.number().int(),
    digest: Sha256Schema,
    boundary: z.string().includes("no model, retrieval, evidence query, tool, provider, or write"),
    decisions: z.array(PolicySimulationDecisionSchema)
  })
  .strict()
  .superRefine((simulation, context) => {
    if (simulation.changed_decision_count !== simulation.decisions.filter((item) => item.changed).length) {
      context.addIssue({ code: "custom", message: "Changed count must match decision rows.", path: ["changed_decision_count"] });
    }
    const sequences = simulation.decisions.map((item) => item.sequence);
    if (sequences.some((sequence, index) => sequence !== index + 1)) {
      context.addIssue({ code: "custom", message: "Simulation decisions must be ordered and contiguous.", path: ["decisions"] });
    }
  });

export type RetrievalPolicyConfig = z.infer<typeof RetrievalPolicyConfigSchema>;
export type CreatePolicyInput = z.input<typeof CreatePolicyInputSchema>;
export type PolicyReceipt = z.infer<typeof PolicyReceiptSchema>;
export type PolicySummary = z.infer<typeof PolicySummarySchema>;
export type PolicyDetail = z.infer<typeof PolicyDetailSchema>;
export type PolicyCatalog = z.infer<typeof PolicyCatalogSchema>;
export type PolicyComparison = z.infer<typeof PolicyComparisonSchema>;
export type PolicySimulation = z.infer<typeof PolicySimulationSchema>;
export type PolicyStatus = z.infer<typeof PolicyStatusSchema>;
