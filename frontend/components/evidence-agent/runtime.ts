"use client";

import { z } from "zod";

import {
  HttpSseEvidenceAgentAdapter,
  RecordingEvidenceAgentAdapter,
  RecordingJournalSchema,
  RunReceiptSchema,
  StartRunInputSchema,
  type EvidenceAgent,
  type RecordingJournal,
  type RunReceipt,
  type RunView,
  type StartRunInput
} from "@/modules/evidence-agent";

const STORAGE_KEY = "evidence-agent:runs:v1";
const StoredRunSchema = z.object({
  mode: z.enum(["production", "recording"]),
  input: StartRunInputSchema,
  receipt: RunReceiptSchema,
  recording_journal: RecordingJournalSchema.optional(),
  created_at: z.iso.datetime()
});

export type StoredRun = z.infer<typeof StoredRunSchema>;

export async function startEvidenceRun(rawInput: StartRunInput, recording: boolean, knownRunId?: string) {
  const input = StartRunInputSchema.parse(rawInput);
  const mode = recording ? "recording" : "production";
  let agent: EvidenceAgent;
  let receipt: RunReceipt;
  if (recording) {
    const runId = `demo-run-${crypto.randomUUID()}`;
    const demoAgent = new RecordingEvidenceAgentAdapter({
      createRunId: () => runId,
      onJournalChange: persistRecordingJournal,
      scenario: "portfolio-demo"
    });
    receipt = await demoAgent.start({ ...input, provider_mode: "recording" });
    agent = demoAgent;
    const recordingJournal = demoAgent.exportJournal(runId);
    saveStoredRun({
      mode,
      input,
      receipt: recordingJournal.current_receipt,
      recording_journal: recordingJournal,
      created_at: new Date().toISOString()
    });
  } else {
    const productionAgent = new HttpSseEvidenceAgentAdapter();
    agent = productionAgent;
    receipt = knownRunId ? await productionAgent.resumeStart(knownRunId) : await productionAgent.start(input);
    saveStoredRun({ mode, input, receipt, created_at: new Date().toISOString() });
  }
  return { agent, receipt, mode } as const;
}

export async function loadEvidenceRun(runId: string, recordingHint: boolean) {
  const stored = listStoredRuns().find((item) => item.receipt.run_id === runId);
  const recording = recordingHint || stored?.mode === "recording";
  if (recording) {
    if (!stored) throw new Error("演示记录已过期。请返回研究工作台重新开始。");
    if (!stored.recording_journal) {
      throw new Error("演示记录缺少事件日志。请返回研究工作台重新开始。");
    }
    const journal = RecordingJournalSchema.parse(stored.recording_journal);
    const agent = new RecordingEvidenceAgentAdapter({
      journal,
      onJournalChange: persistRecordingJournal,
      scenario: "portfolio-demo"
    });
    // Rebuild the public plan/Ledger from the durable journal after navigation
    // or refresh. Starting at the current receipt would skip every prior event
    // and leave a correct terminal status with an empty visible projection.
    const receipt = journal.bootstrap_receipt;
    return { agent, receipt, mode: "recording" as const };
  }

  const agent = new HttpSseEvidenceAgentAdapter();
  const receipt = await bootstrapReceipt(agent, runId);
  return { agent, receipt, mode: "production" as const };
}

export function listStoredRuns(): StoredRun[] {
  if (typeof window === "undefined") return [];
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]");
    const parsed = z.array(StoredRunSchema).safeParse(value);
    return parsed.success ? parsed.data : [];
  } catch {
    return [];
  }
}

export function findCompletedRecordingRunForArtifact(artifactId: string): StoredRun | null {
  return listStoredRuns().find((run) =>
    run.mode === "recording" &&
    run.receipt.view.status === "completed" &&
    run.receipt.view.final_artifact_id === artifactId
  ) ?? null;
}

export function recordingArtifactTitle(run: StoredRun): string | undefined {
  const events = run.recording_journal?.events ?? [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const change = events[index]?.change;
    if (change?.type !== "domain_event" || change.event_type !== "artifact.published") continue;
    const title = change.payload.title;
    if (typeof title === "string" && title.trim()) return title.trim();
  }
  return undefined;
}

export function updateStoredRunView(runId: string, view: RunView, cursor: number): void {
  const runs = listStoredRuns();
  const match = runs.find((item) => item.receipt.run_id === runId);
  if (!match) return;
  match.receipt = RunReceiptSchema.parse({ schema_version: 1, run_id: runId, cursor, view });
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(runs));
}

function saveStoredRun(run: StoredRun): void {
  if (typeof window === "undefined") return;
  const remaining = listStoredRuns().filter((item) => item.receipt.run_id !== run.receipt.run_id);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify([run, ...remaining].slice(0, 20)));
}

function persistRecordingJournal(journal: RecordingJournal): void {
  if (typeof window === "undefined") return;
  const runs = listStoredRuns();
  const match = runs.find((item) => item.receipt.run_id === journal.run_id && item.mode === "recording");
  if (!match) return;
  match.receipt = journal.current_receipt;
  match.recording_journal = journal;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(runs));
}

async function bootstrapReceipt(agent: EvidenceAgent, runId: string): Promise<RunReceipt> {
  const abort = new AbortController();
  const iterator = agent.observe(runId, { signal: abort.signal })[Symbol.asyncIterator]();
  try {
    const first = await iterator.next();
    if (first.done || first.value.change.type !== "snapshot") {
      throw new Error("Run stream did not provide an initial projection.");
    }
    return RunReceiptSchema.parse({ schema_version: 1, run_id: runId, cursor: first.value.cursor, view: first.value.change.view });
  } finally {
    abort.abort();
    await iterator.return?.();
  }
}
