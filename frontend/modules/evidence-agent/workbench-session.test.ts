import { afterEach, describe, expect, it, vi } from "vitest";

import { RECORDING_SOURCES, RECORDING_SPACES } from "@/components/evidence-agent/source-presenter";
import { startEvidenceRun } from "@/components/evidence-agent/runtime";
import { EvidenceAgentStartError } from "./http-sse-adapter";
import {
  clearWorkbenchDraft,
  readPendingSubmission,
  readWorkbenchDraft,
  reconcileWorkbenchScope,
  savePendingSubmission,
  saveWorkbenchDraft,
  sourceCanBeSelected,
  submissionMatchesIntent,
  type WorkbenchDraft
} from "./workbench-session";

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); }
  };
}

const now = Date.parse("2026-10-02T09:00:00Z");
const draft: WorkbenchDraft = {
  recording: false, journeyEnabled: true, goal: "保留我的比较问题", dimensions: "成本、风险",
  spaceId: 7, selectedSourceIds: [3, 5, 9], scopeNeedsReview: false, submissionDetached: false,
  budgetProfile: "deep", deliverable: "comparison", mode: "force_agent"
};
const input = {
  request_id: "stable-request", space_id: 7, goal: draft.goal, provider_mode: "real" as const,
  mode: "force_agent" as const, deliverable: { kind: "comparison" as const },
  scope: { source_ids: [3, 5, 9] }, budget: { max_steps: 16 }
};

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("tab-scoped research drafts", () => {
  it("restores the complete intent through a fresh storage read and keeps modes separate", () => {
    const storage = memoryStorage();
    expect(saveWorkbenchDraft(draft, storage, now)).toBe(true);
    expect(readWorkbenchDraft(false, storage, now)).toEqual(draft);
    expect(readWorkbenchDraft(true, storage, now)).toBeNull();
    saveWorkbenchDraft({ ...draft, recording: true, goal: "录制问题" }, storage, now);
    expect(readWorkbenchDraft(false, storage, now)?.goal).toBe(draft.goal);
    expect(readWorkbenchDraft(true, storage, now)?.goal).toBe("录制问题");
  });

  it("ignores malformed, oversized, wrong-version and expired drafts", () => {
    const storage = memoryStorage();
    const key = "evidence-agent:workbench-draft:v1:real";
    for (const value of ["{", "x".repeat(33_000), JSON.stringify({ version: 99, savedAt: now, draft })]) {
      storage.setItem(key, value);
      expect(readWorkbenchDraft(false, storage, now)).toBeNull();
    }
    saveWorkbenchDraft(draft, storage, now);
    expect(readWorkbenchDraft(false, storage, now + 25 * 60 * 60 * 1000)).toBeNull();
    expect(saveWorkbenchDraft({ ...draft, dimensions: "x".repeat(1_001) }, storage, now)).toBe(false);
  });

  it("does not throw when storage access is denied", () => {
    const storage = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); }, removeItem: () => { throw new Error("denied"); } };
    expect(readWorkbenchDraft(false, storage, now)).toBeNull();
    expect(saveWorkbenchDraft(draft, storage, now)).toBe(false);
    expect(clearWorkbenchDraft(false, storage)).toBe(false);
    expect(readPendingSubmission(false, storage, now).blocked).toBe(true);
  });

  it("retains explicit draft detachment after refresh without changing the original pending input", () => {
    const storage = memoryStorage();
    savePendingSubmission({ input }, storage, now);
    clearWorkbenchDraft(false, storage);
    saveWorkbenchDraft({ ...draft, submissionDetached: true }, storage, now);
    expect(readWorkbenchDraft(false, storage, now)?.submissionDetached).toBe(true);
    expect(readPendingSubmission(false, storage, now).pending?.input.request_id).toBe(input.request_id);
  });

  it("removes retired, missing, cross-space and unindexed selections instead of broadening them silently", () => {
    const sources = RECORDING_SOURCES.map((source, index) => index === 1 ? { ...source, status: "retired" } : source);
    const restored = reconcileWorkbenchScope({ ...draft, recording: true, spaceId: 9001,
      selectedSourceIds: sources.map((source) => source.id).concat(123456) }, RECORDING_SPACES, sources);
    expect(restored.spaceId).toBe(9001);
    expect(restored.selectedSourceIds).toEqual([sources[0].id, sources[2].id]);
    expect(restored.removedSourceIds).toEqual([sources[1].id, sources[3].id, 123456]);
    const noIndex = reconcileWorkbenchScope({ ...draft, recording: true, spaceId: 9001,
      selectedSourceIds: [sources[0].id] }, RECORDING_SPACES, [{ ...sources[0], active_index_revision_id: null,
        revisions: sources[0].revisions.map((revision) => ({ ...revision, index_revisions: [] })) }]);
    expect(noIndex.selectedSourceIds).toEqual([]);
  });

  it("keeps a legal legacy selection when its source pointer is absent but the active revision has a usable index", () => {
    const base = RECORDING_SOURCES[0];
    for (const active_index_revision_id of [null, undefined]) {
      const legacy = { ...base, active_index_revision_id };
      expect(sourceCanBeSelected(legacy, 9001, true)).toBe(true);
      expect(reconcileWorkbenchScope({ ...draft, recording: true, spaceId: 9001, selectedSourceIds: [base.id] },
        RECORDING_SPACES, [legacy])).toMatchObject({ selectedSourceIds: [base.id], removedSourceIds: [] });
      for (const index of [
        { ...base.revisions[0].index_revisions![0], status: "pending" },
        { ...base.revisions[0].index_revisions![0], validation_status: "pending" },
        { ...base.revisions[0].index_revisions![0], source_id: 999 },
        { ...base.revisions[0].index_revisions![0], revision_id: 999 }
      ]) {
        expect(sourceCanBeSelected({ ...legacy, revisions: [{ ...base.revisions[0], index_revisions: [index] }] }, 9001, true)).toBe(false);
      }
    }
    expect(sourceCanBeSelected({ ...base, active_index_revision_id: 999 }, 9001, true)).toBe(false);
  });

  it("requires active matching revision/index ownership and passed index validation when provided", () => {
    const base = RECORDING_SOURCES[0];
    const revision = base.revisions[0];
    const index = revision.index_revisions![0];
    const draftForSource = { ...draft, recording: true, spaceId: 9001, selectedSourceIds: [base.id] };
    const variants = [
      { ...base, revisions: [{ ...revision, status: "pending" }] },
      { ...base, revisions: [{ ...revision, source_id: 999 }] },
      { ...base, revisions: [{ ...revision, index_revisions: [{ ...index, revision_id: 999 }] }] },
      { ...base, revisions: [{ ...revision, index_revisions: [{ ...index, source_id: 999 }] }] },
      { ...base, revisions: [{ ...revision, index_revisions: [{ ...index, validation_status: "pending" }] }] }
    ];
    for (const invalid of variants) {
      expect(reconcileWorkbenchScope(draftForSource, RECORDING_SPACES, [invalid]).selectedSourceIds).toEqual([]);
    }
  });
});

describe("uncertain submission recovery", () => {
  it("persists the original identity before HTTP and restores a known run with only GET after remount", async () => {
    const storage = memoryStorage();
    const calls: string[] = [];
    vi.stubGlobal("window", { localStorage: memoryStorage() });
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://evidence.example.test");
    vi.stubGlobal("fetch", async (path: RequestInfo | URL) => {
      calls.push(String(path));
      expect(readPendingSubmission(false, storage, now).pending?.input.request_id).toBe(input.request_id);
      const data = calls.length === 1
        ? { schema_version: 1, command_id: "command", run_id: "created-run", run_version: 1, status: "queued", cursor: 1, replayed: false }
        : { schema_version: 1, id: "created-run", space_id: 7, goal: draft.goal, requested_mode: "force_agent",
          effective_mode: null, status: "queued", phase: "route", version: 1, execution_epoch: 0,
          scope_snapshot: { space_id: 7, revisions: [] }, budget_limits: { max_steps: 16 }, budget_usage: {},
          cost_measurement: "unknown", provider_mode: "real", last_event_cursor: 1, final_artifact_id: null,
          termination_reason: null, outcome: null };
      if (calls.length === 2) return new Response("unavailable", { status: 503 });
      return new Response(JSON.stringify({ success: true, data, error: null, request_id: "response" }));
    });
    savePendingSubmission({ input }, storage, now);
    let failure: unknown;
    try { await startEvidenceRun(input, false); } catch (reason) { failure = reason; }
    expect(failure).toBeInstanceOf(EvidenceAgentStartError);
    if (!(failure instanceof EvidenceAgentStartError)) throw failure;
    savePendingSubmission({ input, runId: failure.runId }, storage, now);
    clearWorkbenchDraft(false, storage);
    const pending = readPendingSubmission(false, storage, now).pending;
    expect(pending?.input.request_id).toBe("stable-request");
    if (!pending) throw new Error("Missing recovery identity after refresh");
    await startEvidenceRun(pending.input, false, pending.runId);
    expect(calls.map((path) => path.split("/api/")[1])).toEqual([
      "v1/evidence-runs", "v1/evidence-runs/created-run", "v1/evidence-runs/created-run"
    ]);
  });

  it("matches only the same complete intent, including budget, mode and source set", () => {
    expect(submissionMatchesIntent({ input }, input)).toBe(true);
    expect(submissionMatchesIntent({ input }, { ...input, budget: { max_steps: 4 } })).toBe(false);
    expect(submissionMatchesIntent({ input }, { ...input, goal: "另一个问题" })).toBe(false);
    expect(submissionMatchesIntent({ input }, { ...input, provider_mode: "recording" })).toBe(false);
    expect(submissionMatchesIntent({ input }, { ...input, scope: { source_ids: [9, 5, 3] } })).toBe(true);
  });

  it("blocks identity rotation after corrupt or cross-mode data and retains identity beyond draft expiry", () => {
    const storage = memoryStorage();
    const key = "evidence-agent:workbench-pending:v1:real";
    storage.setItem(key, "{");
    expect(readPendingSubmission(false, storage, now)).toEqual({ pending: null, blocked: true });
    savePendingSubmission({ input }, storage, now);
    expect(readPendingSubmission(false, storage, now + 8 * 24 * 60 * 60 * 1000).pending?.input.request_id).toBe("stable-request");
    expect(readPendingSubmission(true, storage, now)).toEqual({ pending: null, blocked: false });
    expect(savePendingSubmission({ input: { ...input, provider_mode: "demo" } }, storage, now)).toBe(false);
  });
});
