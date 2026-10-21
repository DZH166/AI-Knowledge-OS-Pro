import { z } from "zod";

import type { KnowledgeSpace, SourceItem } from "@/types/api";
import { StartRunInputSchema, type StartRunInput } from "./contract";
import { runIntentKey } from "./submission-identity";

const MAX_STORED_LENGTH = 32_000;
const DRAFT_TTL = 24 * 60 * 60 * 1000;
const id = z.number().int().positive();
const draftSchema = z.object({
  recording: z.boolean(), journeyEnabled: z.boolean(), goal: z.string().max(4_000),
  dimensions: z.string().max(1_000), spaceId: z.number().int().nonnegative(),
  selectedSourceIds: z.array(id).max(200), scopeNeedsReview: z.boolean().default(false), submissionDetached: z.boolean().default(false),
  budgetProfile: z.enum(["quick", "standard", "deep"]),
  deliverable: z.enum(["answer", "research_report", "comparison"]),
  mode: z.enum(["auto", "force_quick", "force_agent"])
}).strict();
const pendingSchema = z.object({
  input: StartRunInputSchema.refine((input) => input.scope.source_ids.length <= 200
    && (input.provider_mode === "real" || input.provider_mode === "recording")),
  runId: z.string().min(1).max(200).optional()
}).strict();
const envelope = z.object({
  version: z.literal(1), savedAt: z.number().int().nonnegative(), value: z.unknown()
}).strict();

export type WorkbenchDraft = z.infer<typeof draftSchema>;
export type PendingSubmission = { input: StartRunInput; runId?: string };
type SessionStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function storage(provided?: SessionStorage): SessionStorage {
  if (provided) return provided;
  return window.sessionStorage;
}

function key(kind: "draft" | "pending", recording: boolean) {
  return `evidence-agent:workbench-${kind}:v1:${recording ? "recording" : "real"}`;
}

function parse<T extends z.ZodType>(raw: string, schema: T, now: number, ttl?: number) {
  if (raw.length > MAX_STORED_LENGTH) throw new Error("Stored research exceeds limit");
  const parsed = envelope.parse(JSON.parse(raw));
  if (parsed.savedAt > now + 60_000 || (ttl !== undefined && now - parsed.savedAt > ttl)) throw new Error("Stored research expired");
  return schema.parse(parsed.value);
}

export function readWorkbenchDraft(recording: boolean, provided?: SessionStorage, now = Date.now()): WorkbenchDraft | null {
  try {
    const raw = storage(provided).getItem(key("draft", recording));
    if (raw === null) return null;
    const draft = parse(raw, draftSchema, now, DRAFT_TTL);
    return draft.recording === recording ? draft : null;
  } catch { return null; }
}

export function saveWorkbenchDraft(draft: WorkbenchDraft, provided?: SessionStorage, now = Date.now()): boolean {
  try {
    const value = draftSchema.parse(draft);
    storage(provided).setItem(key("draft", value.recording), JSON.stringify({ version: 1, savedAt: now, value }));
    return true;
  } catch { return false; }
}

export function clearWorkbenchDraft(recording: boolean, provided?: SessionStorage): boolean {
  try { storage(provided).removeItem(key("draft", recording)); return true; } catch { return false; }
}

/** Invalid submission data is a recovery barrier, never permission to rotate its identity. */
export function readPendingSubmission(recording: boolean, provided?: SessionStorage, now = Date.now()): {
  pending: PendingSubmission | null; blocked: boolean;
} {
  try {
    const raw = storage(provided).getItem(key("pending", recording));
    if (raw === null) return { pending: null, blocked: false };
    // Pending submissions have no draft TTL: an old unknown task must retain its identity.
    const pending = parse(raw, pendingSchema, now);
    if ((pending.input.provider_mode === "recording") !== recording) throw new Error("Submission mode mismatch");
    return { pending, blocked: false };
  } catch { return { pending: null, blocked: true }; }
}

export function savePendingSubmission(pending: PendingSubmission, provided?: SessionStorage, now = Date.now()): boolean {
  try {
    const value = pendingSchema.parse(pending);
    storage(provided).setItem(key("pending", value.input.provider_mode === "recording"), JSON.stringify({ version: 1, savedAt: now, value }));
    return true;
  } catch { return false; }
}

export function clearPendingSubmission(recording: boolean, provided?: SessionStorage): boolean {
  try { storage(provided).removeItem(key("pending", recording)); return true; } catch { return false; }
}

function intentKey(input: StartRunInput) {
  const intent = StartRunInputSchema.parse(input);
  return runIntentKey({ schema_version: intent.schema_version, space_id: intent.space_id, goal: intent.goal,
    deliverable: intent.deliverable, mode: intent.mode, budget: intent.budget, permissions: intent.permissions,
    provider_mode: intent.provider_mode, scope: { source_ids: [...new Set(intent.scope.source_ids)].sort((a, b) => a - b) } });
}

export function submissionMatchesIntent(pending: PendingSubmission, intent: Omit<StartRunInput, "request_id">): boolean {
  try { return intentKey(pending.input) === intentKey({ ...intent, request_id: pending.input.request_id }); }
  catch { return false; }
}

export function sourceCanBeSelected(source: SourceItem, spaceId: number, comparison: boolean): boolean {
  if (source.space_id !== spaceId || source.status === "retired" || source.active_revision_id === null
    || (comparison && source.source_type !== "document")) return false;
  const revision = source.revisions.find((item) => item.id === source.active_revision_id);
  if (!revision || revision.source_id !== source.id || revision.status !== "active" || revision.validation_status !== "passed") return false;
  const indexId = source.active_index_revision_id;
  return revision.index_revisions?.some((item) => (indexId === null || indexId === undefined || item.id === indexId) && item.status === "active"
    && item.source_id === source.id && item.revision_id === revision.id
    && (!("validation_status" in item) || item.validation_status === "passed")) === true;
}

export function reconcileWorkbenchScope(draft: WorkbenchDraft, spaces: KnowledgeSpace[], sources: SourceItem[]) {
  const spaceId = spaces.some((space) => space.id === draft.spaceId) ? draft.spaceId : spaces[0]?.id ?? 0;
  const selectedSourceIds = [...new Set(draft.selectedSourceIds)].filter((id) => sources.some((source) =>
    source.id === id && sourceCanBeSelected(source, spaceId, draft.journeyEnabled)));
  return { spaceId, selectedSourceIds, removedSourceIds: draft.selectedSourceIds.filter((id) => !selectedSourceIds.includes(id)) };
}
