import { z } from "zod";

import {
  CommandReceiptSchema,
  RunCommandSchema,
  RunEventSchema,
  RunReceiptSchema,
  StartRunInputSchema,
  type CommandReceipt,
  type RunCommand,
  type RunEvent,
  type RunReceipt,
  type RunView,
  type StartRunInput
} from "./contract";
import type { EvidenceAgent, ObserveOptions } from "./evidence-agent";
import { RECORDING_COMPARISON_SOURCES, RECORDING_FIXTURE, isRecordedComparisonInput } from "./recording-fixture";

const RecordingCommandEntrySchema = z.object({
  command: RunCommandSchema,
  receipt: CommandReceiptSchema
}).strict();

export const RecordingJournalSchema = z.object({
  schema_version: z.literal(1),
  run_id: z.string().min(1),
  bootstrap_receipt: RunReceiptSchema,
  current_receipt: RunReceiptSchema,
  events: z.array(RunEventSchema).min(1),
  commands: z.array(RecordingCommandEntrySchema)
}).strict().superRefine((journal, context) => {
  const runId = journal.run_id;
  if (journal.bootstrap_receipt.run_id !== runId || journal.current_receipt.run_id !== runId) {
    context.addIssue({ code: "custom", message: "Recording receipts must belong to the journal run." });
  }
  if (journal.events.some((event) => event.run_id !== runId)) {
    context.addIssue({ code: "custom", message: "Recording events must belong to the journal run." });
  }
  if (journal.commands.some((entry) => entry.receipt.run_id !== runId)) {
    context.addIssue({ code: "custom", message: "Recording command receipts must belong to the journal run." });
  }
  const first = journal.events[0];
  const last = journal.events.at(-1);
  if (first?.cursor !== journal.bootstrap_receipt.cursor || last?.cursor !== journal.current_receipt.cursor) {
    context.addIssue({ code: "custom", message: "Recording receipt cursors must bound the event journal." });
  }
});

export type RecordingJournal = z.infer<typeof RecordingJournalSchema>;

type RecordingAdapterOptions = {
  createRunId?: () => string;
  journal?: unknown;
  onJournalChange?: (journal: RecordingJournal) => void;
  scenario?: "minimal" | "portfolio-demo";
};

const EMPTY_USAGE = {
  steps: 0,
  tool_calls: 0,
  model_calls: 0,
  model_input_tokens: 0,
  model_output_tokens: 0,
  cost_micros: 0,
  active_ms: 0,
  no_new_evidence_rounds: 0
};

const STATUS_BY_SIGNAL: Record<RunCommand["signal"], RunView["status"]> = {
  provide_input: "queued",
  approve: "queued",
  reject: "insufficient_evidence",
  modify: "awaiting_approval",
  pause: "paused",
  resume: "queued",
  cancel: "cancelled"
};

export class RecordingEvidenceAgentAdapter implements EvidenceAgent {
  private readonly createRunId: () => string;
  private readonly onJournalChange: ((journal: RecordingJournal) => void) | undefined;
  private readonly scenario: "minimal" | "portfolio-demo";
  private readonly eventsByRun = new Map<string, RunEvent[]>();
  private readonly bootstrapReceiptsByRun = new Map<string, RunReceipt>();
  private readonly currentReceiptsByRun = new Map<string, RunReceipt>();
  private readonly commandsByRun = new Map<string, RecordingJournal["commands"]>();
  private readonly receiptsByRun = new Map<string, Map<string, CommandReceipt>>();

  constructor(options: RecordingAdapterOptions = {}) {
    this.createRunId = options.createRunId ?? (() => crypto.randomUUID());
    this.onJournalChange = options.onJournalChange;
    this.scenario = options.scenario ?? "minimal";
    if (options.journal !== undefined) this.restoreJournal(options.journal);
  }

  async start(rawInput: StartRunInput): Promise<RunReceipt> {
    const input = StartRunInputSchema.parse(rawInput);
    const runId = this.createRunId();
    const threeSourceComparison = this.scenario === "portfolio-demo" && isRecordedComparisonInput(input);
    const view: RunView = {
      schema_version: 1,
      id: runId,
      space_id: input.space_id,
      goal: input.goal,
      requested_mode: input.mode,
      effective_mode: null,
      status: "queued",
      phase: "route",
      version: 1,
      execution_epoch: 0,
      scope_snapshot: {
        space_id: input.space_id,
        revisions: threeSourceComparison ? RECORDING_COMPARISON_SOURCES.map((source) => ({
          source_id: source.sourceId,
          revision_id: source.revisionId,
          index_revision_id: source.indexRevisionId,
          content_hash: source.revisionContentHash
        })) : []
      },
      budget_limits: input.budget,
      budget_usage: EMPTY_USAGE,
      cost_measurement: "unknown",
      provider_mode: input.provider_mode,
      last_event_cursor: 1,
      final_artifact_id: null,
      termination_reason: null,
      outcome: null
    };
    const event = RunEventSchema.parse({
      schema_version: 1,
      event_id: `${runId}:1`,
      cursor: 1,
      run_id: runId,
      run_version: 1,
      change: { type: "snapshot", reset: false, view }
    });
    const events = this.scenario === "portfolio-demo" ? [event, ...demoResearchEvents(runId, threeSourceComparison)] : [event];
    const receipt = RunReceiptSchema.parse({ schema_version: 1, run_id: runId, cursor: 1, view });
    this.eventsByRun.set(runId, events);
    this.bootstrapReceiptsByRun.set(runId, receipt);
    this.currentReceiptsByRun.set(runId, projectReceipt(receipt, events));
    this.commandsByRun.set(runId, []);
    this.receiptsByRun.set(runId, new Map());
    this.notifyJournalChange(runId);
    return receipt;
  }

  async *observe(runId: string, options: ObserveOptions = {}): AsyncGenerator<RunEvent> {
    const events = this.eventsByRun.get(runId);
    if (!events) throw new Error(`Unknown recorded run: ${runId}`);
    if (options.signal?.aborted) return;

    let replay = events;
    if (options.after !== undefined) {
      const index = events.findIndex((event) => event.cursor === options.after);
      if (index >= 0) replay = events.slice(index + 1);
      else {
        const snapshot = events[0];
        replay = snapshot.change.type === "snapshot"
          ? [RunEventSchema.parse({ ...snapshot, change: { ...snapshot.change, reset: true } }), ...events.slice(1)]
          : events;
      }
    }

    for (const event of replay) {
      if (options.signal?.aborted) return;
      yield RunEventSchema.parse(event);
    }
  }

  async act(runId: string, rawCommand: RunCommand): Promise<CommandReceipt> {
    const command = RunCommandSchema.parse(rawCommand);
    const events = this.eventsByRun.get(runId);
    if (!events) throw new Error(`Unknown recorded run: ${runId}`);
    const receipts = this.receiptsByRun.get(runId);
    if (!receipts) throw new Error(`Missing command journal for recorded run: ${runId}`);
    const priorReceipt = receipts.get(command.request_id);
    if (priorReceipt) return priorReceipt;

    const currentVersion = events.at(-1)?.run_version ?? 1;
    if (command.expected_version !== currentVersion) {
      throw new Error(`Stale recorded run version: expected ${command.expected_version}, actual ${currentVersion}`);
    }
    if (
      this.scenario === "portfolio-demo" &&
      (command.signal === "approve" || command.signal === "reject" || command.signal === "modify")
    ) {
      const expectedDigest = currentProposalDigest(events);
      if (!expectedDigest || command.proposal_digest !== expectedDigest) {
        throw new Error("Proposal Digest 已失效。请使用当前待审批提案的指纹重试。");
      }
    }
    const runVersion = currentVersion + 1;
    const cursor = events.length + 1;
    const status = STATUS_BY_SIGNAL[command.signal];
    events.push(
      RunEventSchema.parse({
        schema_version: 1,
        event_id: `${runId}:${cursor}`,
        cursor,
        run_id: runId,
        run_version: runVersion,
        change: { type: "status_changed", status }
      })
    );

    const receipt = CommandReceiptSchema.parse({
      schema_version: 1,
      command_id: command.request_id,
      run_id: runId,
      run_version: runVersion,
      status,
      cursor,
      replayed: false
    });
    if (this.scenario === "portfolio-demo" && command.signal === "approve") {
      appendDemoCompletion(events, runId, runVersion, latestModifiedArtifactTitle(events));
    }
    if (this.scenario === "portfolio-demo" && command.signal === "modify") {
      appendDemoModification(
        events,
        runId,
        runVersion,
        command.response.title,
        nextProposalDigest(events)
      );
    }
    const bootstrapReceipt = this.bootstrapReceiptsByRun.get(runId);
    if (!bootstrapReceipt) throw new Error(`Missing bootstrap receipt for recorded run: ${runId}`);
    this.currentReceiptsByRun.set(runId, projectReceipt(bootstrapReceipt, events));
    this.commandsByRun.get(runId)?.push({ command, receipt });
    receipts.set(command.request_id, receipt);
    this.notifyJournalChange(runId);
    return receipt;
  }

  exportJournal(runId: string): RecordingJournal {
    const bootstrapReceipt = this.bootstrapReceiptsByRun.get(runId);
    const currentReceipt = this.currentReceiptsByRun.get(runId);
    const events = this.eventsByRun.get(runId);
    const commands = this.commandsByRun.get(runId);
    if (!bootstrapReceipt || !currentReceipt || !events || !commands) {
      throw new Error(`Unknown recorded run: ${runId}`);
    }
    return RecordingJournalSchema.parse({
      schema_version: 1,
      run_id: runId,
      bootstrap_receipt: bootstrapReceipt,
      current_receipt: currentReceipt,
      events,
      commands
    });
  }

  private notifyJournalChange(runId: string): void {
    this.onJournalChange?.(this.exportJournal(runId));
  }

  private restoreJournal(rawJournal: unknown): void {
    const journal = RecordingJournalSchema.parse(rawJournal);
    const commands = journal.commands.map((entry) => ({ command: entry.command, receipt: entry.receipt }));
    this.eventsByRun.set(journal.run_id, journal.events.map((event) => RunEventSchema.parse(event)));
    this.bootstrapReceiptsByRun.set(journal.run_id, RunReceiptSchema.parse(journal.bootstrap_receipt));
    this.currentReceiptsByRun.set(journal.run_id, RunReceiptSchema.parse(journal.current_receipt));
    this.commandsByRun.set(journal.run_id, commands);
    this.receiptsByRun.set(
      journal.run_id,
      new Map(commands.map((entry) => [entry.command.request_id, CommandReceiptSchema.parse(entry.receipt)]))
    );
  }
}

export function recordingArtifactId(runId: string): string {
  return `artifact-${runId}`;
}

function demoResearchEvents(runId: string, includeReview: boolean): RunEvent[] {
  const contractSource = RECORDING_FIXTURE.sources.contract;
  const changes: Array<{ runVersion: number; change: RunEvent["change"] }> = [
    { runVersion: 2, change: { type: "status_changed", status: "routing" } },
    {
      runVersion: 3,
      change: {
        type: "domain_event",
        event_type: "plan.created",
        payload: {
          plan_version: 1,
          strategy: "structured_model_plan",
          requirements: [
            "核验事实结论能否回溯到不可变来源版本",
            "核验检索是否限定在固定 revision 范围内",
            "核验成果写入是否经过明确审批"
          ]
        }
      }
    },
    { runVersion: 4, change: { type: "status_changed", status: "running" } },
    {
      runVersion: 5,
      change: {
        type: "domain_event",
        event_type: "step.completed",
        payload: { label: "混合检索与邻域扩展", detail: "在固定 revision 范围内完成证据召回。" }
      }
    },
    {
      runVersion: 6,
      change: {
        type: "domain_event",
        event_type: "evidence.added",
        payload: {
          evidence_id: "evidence-demo-1",
          source_title: contractSource.title,
          excerpt: contractSource.excerpt,
          relation: "supports",
          reference: {
            source_id: contractSource.sourceId,
            revision_id: contractSource.revisionId,
            index_revision_id: contractSource.indexRevisionId,
            chunk_id: contractSource.chunkId,
            content_hash: contractSource.contentHash,
            locator: contractSource.locator
          }
        }
      }
    },
    { runVersion: 7, change: { type: "status_changed", status: "awaiting_approval" } },
    {
      runVersion: 7,
      change: {
        type: "domain_event",
        event_type: "interaction.required",
        payload: {
          kind: "approval",
          summary: includeReview ? "发布三资料对比录制样例" : "发布决策简报到工作区成果库",
          target: includeReview ? "artifact:comparison" : "artifact:research_report",
          risk_class: "write",
          proposal_digest: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        }
      }
    }
  ];
  if (includeReview) {
    const review = RECORDING_FIXTURE.sources.review;
    changes.splice(5, 0, {
      runVersion: 6,
      change: {
        type: "domain_event",
        event_type: "evidence.added",
        payload: {
          evidence_id: "evidence-demo-3",
          source_title: review.title,
          excerpt: review.excerpt,
          relation: "supports",
          reference: {
            source_id: review.sourceId,
            revision_id: review.revisionId,
            index_revision_id: review.indexRevisionId,
            chunk_id: review.chunkId,
            content_hash: review.contentHash,
            locator: review.locator
          }
        }
      }
    });
  }
  return changes.map((item, index) =>
    RunEventSchema.parse({
      schema_version: 1,
      event_id: `${runId}:${index + 2}`,
      cursor: index + 2,
      run_id: runId,
      run_version: item.runVersion,
      change: item.change
    })
  );
}

function appendDemoCompletion(
  events: RunEvent[],
  runId: string,
  commandVersion: number,
  title: string
): void {
  const runtimeSource = RECORDING_FIXTURE.sources.runtime;
  const changes: Array<{ runVersion: number; change: RunEvent["change"] }> = [
    {
      runVersion: commandVersion,
      change: { type: "domain_event", event_type: "interaction.resolved", payload: { decision: "approve" } }
    },
    { runVersion: commandVersion + 1, change: { type: "status_changed", status: "running" } },
    {
      runVersion: commandVersion + 2,
      change: {
        type: "domain_event",
        event_type: "evidence.added",
        payload: {
          evidence_id: "evidence-demo-2",
          source_title: runtimeSource.title,
          excerpt: runtimeSource.excerpt,
          relation: "supports",
          reference: {
            source_id: runtimeSource.sourceId,
            revision_id: runtimeSource.revisionId,
            index_revision_id: runtimeSource.indexRevisionId,
            chunk_id: runtimeSource.chunkId,
            content_hash: runtimeSource.contentHash,
            locator: runtimeSource.locator
          }
        }
      }
    },
    {
      runVersion: commandVersion + 3,
      change: {
        type: "domain_event",
        event_type: "artifact.published",
        payload: { artifact_id: recordingArtifactId(runId), title }
      }
    },
    { runVersion: commandVersion + 4, change: { type: "status_changed", status: "completed" } }
  ];
  for (const item of changes) {
    const cursor = events.length + 1;
    events.push(
      RunEventSchema.parse({
        schema_version: 1,
        event_id: `${runId}:${cursor}`,
        cursor,
        run_id: runId,
        run_version: item.runVersion,
        change: item.change
      })
    );
  }
}

function appendDemoModification(
  events: RunEvent[],
  runId: string,
  commandVersion: number,
  rawTitle: unknown,
  proposalDigest: string
): void {
  const title = typeof rawTitle === "string" && rawTitle.trim() ? rawTitle.trim() : "修改后的研究成果";
  const changes: RunEvent["change"][] = [
    {
      type: "domain_event",
      event_type: "interaction.resolved",
      payload: { decision: "modify", response: { title } }
    },
    {
      type: "domain_event",
      event_type: "interaction.required",
      payload: {
        kind: "approval",
        summary: `发布《${title}》`,
        target: recordedApprovalTarget(events),
        risk_class: "write",
        proposal_digest: proposalDigest
      }
    }
  ];
  for (const change of changes) {
    const cursor = events.length + 1;
    events.push(
      RunEventSchema.parse({
        schema_version: 1,
        event_id: `${runId}:${cursor}`,
        cursor,
        run_id: runId,
        run_version: commandVersion,
        change
      })
    );
  }
}

function currentProposalDigest(events: readonly RunEvent[]): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const change = events[index]?.change;
    if (change?.type !== "domain_event" || change.event_type !== "interaction.required") continue;
    if (change.payload.kind !== "approval") continue;
    const digest = change.payload.proposal_digest;
    return typeof digest === "string" ? digest : null;
  }
  return null;
}

function latestModifiedArtifactTitle(events: readonly RunEvent[]): string {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const change = events[index]?.change;
    if (change?.type !== "domain_event" || change.event_type !== "interaction.resolved") continue;
    if (change.payload.decision !== "modify") continue;
    const response = change.payload.response;
    if (!response || typeof response !== "object" || !("title" in response)) continue;
    const title = response.title;
    if (typeof title === "string" && title.trim()) return title.trim();
  }
  return recordedApprovalTarget(events) === "artifact:comparison"
    ? "三资料对比录制样例"
    : "Evidence Agent 升级决策简报";
}

function recordedApprovalTarget(events: readonly RunEvent[]): "artifact:comparison" | "artifact:research_report" {
  return events.some((event) => event.change.type === "domain_event" &&
    event.change.event_type === "interaction.required" &&
    event.change.payload.target === "artifact:comparison")
    ? "artifact:comparison"
    : "artifact:research_report";
}

function nextProposalDigest(events: readonly RunEvent[]): string {
  const proposalCount = events.filter((event) =>
    event.change.type === "domain_event" &&
    event.change.event_type === "interaction.required" &&
    event.change.payload.kind === "approval"
  ).length;
  const digit = ((10 + proposalCount) % 16).toString(16);
  return digit.repeat(64);
}

function projectReceipt(bootstrapReceipt: RunReceipt, events: RunEvent[]): RunReceipt {
  let view: RunView = bootstrapReceipt.view;
  let cursor = bootstrapReceipt.cursor;
  for (const event of events) {
    if (event.cursor <= bootstrapReceipt.cursor) continue;
    cursor = event.cursor;
    if (event.change.type === "snapshot") {
      view = event.change.view;
      continue;
    }
    if (event.change.type === "status_changed") {
      view = {
        ...view,
        status: event.change.status,
        version: event.run_version,
        last_event_cursor: event.cursor
      };
      continue;
    }
    view = { ...view, version: event.run_version, last_event_cursor: event.cursor };
    if (event.change.event_type === "artifact.published") {
      const artifactId = typeof event.change.payload.artifact_id === "string" ? event.change.payload.artifact_id : null;
      if (artifactId) {
        view = {
          ...view,
          final_artifact_id: artifactId,
          outcome: { kind: "artifact", artifact_id: artifactId }
        };
      }
    }
  }
  return RunReceiptSchema.parse({ schema_version: 1, run_id: bootstrapReceipt.run_id, cursor, view });
}
