import { z } from "zod";

const digest = z.string().regex(/^[a-f0-9]{64}$/);
const id = z.string().regex(/^[A-Za-z0-9_-]{1,36}$/);
const requestId = z.string().regex(/^[A-Za-z0-9_-]{1,80}$/);
export const IssueSchema = z.enum(["missing_evidence", "incorrect_answer", "unsupported_citation", "incomplete_answer"]);
export const StatusSchema = z.enum(["pending", "accepted", "rejected"]);
export const ModeSchema = z.enum(["real", "demo", "recording"]);
export const SplitSchema = z.enum(["tuning", "holdout"]);

export const SubmitFeedbackSchema = z.object({
  request_id: requestId, artifact_id: id, claim_id: id.nullable(), issue: IssueSchema,
  comment: z.string().trim().min(1).max(2000)
}).strict();

export const ReviewFeedbackSchema = z.object({
  request_id: requestId, expected_version: z.number().int().positive(), decision: z.enum(["accepted", "rejected"]),
  reason: z.string().trim().min(1).max(2000), expected_answer: z.string().trim().min(1).max(8000).nullable().optional(),
  acceptance_criteria: z.string().trim().min(1).max(2000).nullable().optional(), split: SplitSchema.nullable().optional(),
  reference_evidence_ids: z.array(id).max(200).default([])
}).strict().superRefine((value, context) => {
  if (value.decision === "accepted" && (!value.expected_answer || !value.acceptance_criteria || !value.split)) {
    context.addIssue({ code: "custom", message: "接受反馈需要参考答案、验收要求和用途。" });
  }
  if (value.decision === "rejected" && (value.expected_answer || value.acceptance_criteria || value.split || value.reference_evidence_ids.length)) {
    context.addIssue({ code: "custom", message: "驳回不能包含评测样例字段。" });
  }
});

const EvidenceSchema = z.object({
  id: z.string(), source_id: z.number().int().positive(), revision_id: z.number().int().positive(),
  index_revision_id: z.number().int().positive(), chunk_id: z.number().int().positive(), source_type: z.string(),
  locator: z.record(z.string(), z.json()), revision_content_hash: digest, content_hash: digest, excerpt: z.string()
}).strict();

export const SnapshotSchema = z.object({
  run_id: z.string(), run_version: z.number().int().positive(), space_id: z.number().int().positive(), goal: z.string(),
  provider_mode: ModeSchema, scope: z.record(z.string(), z.json()), scope_digest: digest,
  policy_id: z.string().nullable(), policy_version: z.number().int().nullable(), policy_fingerprint: z.string().nullable(),
  artifact_id: z.string(), artifact_title: z.string(), artifact_body: z.string(),
  claim: z.object({ id: z.string(), text: z.string(), verification_status: z.string() }).strict().nullable(),
  evidence: z.array(EvidenceSchema).max(200)
}).strict();

const ReviewSchema = z.object({ decision: z.enum(["accepted", "rejected"]), reason: z.string(),
  reviewer: z.literal("local_user"), reviewed_at: z.iso.datetime({ offset: true }) }).strict();
const SampleSchema = z.object({ id: z.number().int().positive(), split: SplitSchema, expected_answer: z.string(),
  acceptance_criteria: z.string(), reference_evidence_ids: z.array(z.string()), snapshot_sha256: digest,
  expectation_kind: z.literal("human_reviewed_not_automatically_verified") }).strict();

export const FeedbackSchema = z.object({
  id: z.number().int().positive(), artifact_id: z.string(), claim_id: z.string().nullable(), issue: IssueSchema,
  comment: z.string(), status: StatusSchema, version: z.number().int().positive(), provider_mode: ModeSchema,
  snapshot: SnapshotSchema, snapshot_sha256: digest, created_at: z.iso.datetime({ offset: true }),
  review: ReviewSchema.nullable(), sample: SampleSchema.nullable()
}).strict().superRefine((value, context) => {
  if ((value.status === "accepted") !== (value.sample !== null) || (value.status === "pending") !== (value.review === null)
    || value.provider_mode !== value.snapshot.provider_mode || value.artifact_id !== value.snapshot.artifact_id
    || value.claim_id !== (value.snapshot.claim?.id ?? null)
    || (value.review && value.review.decision !== value.status)
    || (value.sample && (value.sample.id !== value.id || value.sample.snapshot_sha256 !== value.snapshot_sha256))) {
    context.addIssue({ code: "custom", message: "反馈、审阅与样例状态不一致。" });
  }
});
export const ReceiptSchema = z.object({ feedback: FeedbackSchema, replayed: z.boolean() }).strict();
export const PageSchema = z.object({ items: z.array(FeedbackSchema).max(100), next_after: z.number().int().positive().nullable() }).strict();
export const ExportSchema = z.object({ filename: z.string().regex(/^feedback-(tuning|holdout)-(real|demo|recording)\.json$/),
  content: z.string(), sha256: digest, count: z.number().int().min(1).max(100), split: SplitSchema, provider_mode: ModeSchema }).strict();
export const ExportPayloadSchema = z.object({ schema_version: z.literal(1), format: z.literal("human_reviewed_feedback_v1"),
  split: SplitSchema, provider_mode: ModeSchema, claim_boundary: z.string(), cases: z.array(FeedbackSchema).min(1).max(100) }).strict();

export type Feedback = z.infer<typeof FeedbackSchema>;
export type FeedbackPage = z.infer<typeof PageSchema>;
export type SubmitFeedback = z.infer<typeof SubmitFeedbackSchema>;
export type ReviewFeedback = z.infer<typeof ReviewFeedbackSchema>;
export type SampleExport = z.infer<typeof ExportSchema>;
export type Issue = z.infer<typeof IssueSchema>;
export type Status = z.infer<typeof StatusSchema>;
export type Mode = z.infer<typeof ModeSchema>;
export type Split = z.infer<typeof SplitSchema>;

export const issueLabel: Record<Issue, string> = { missing_evidence: "漏找资料", incorrect_answer: "理解错误",
  unsupported_citation: "引用不支持结论", incomplete_answer: "回答不完整" };
export const statusLabel: Record<Status, string> = { pending: "待审阅", accepted: "已接受", rejected: "已驳回" };
export const modeLabel: Record<Mode, string> = { real: "真实模型运行", demo: "后端演示数据", recording: "录制模型数据" };
export const splitLabel: Record<Split, string> = { tuning: "调参样例", holdout: "留出测试样例" };
