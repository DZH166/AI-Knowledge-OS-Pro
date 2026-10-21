import { RunEventSchema, RunReceiptSchema, type CommandReceipt, type RunEvent, type RunReceipt, type RunView } from "./contract";
import type { EvidenceAgent } from "./evidence-agent";

export type RunConnectionState = "idle" | "connecting" | "live" | "closed" | "error";

export type RunControllerSnapshot = Readonly<{
  view: RunView;
  cursor: number;
  events: readonly RunEvent[];
  connection: RunConnectionState;
  error: string | null;
}>;

type RunControllerOptions = {
  createRequestId?: () => string;
  deduplicationWindow?: number;
};

type Listener = () => void;

export class RunController {
  private readonly agent: EvidenceAgent;
  private readonly runId: string;
  private readonly createRequestId: () => string;
  private readonly deduplicationWindow: number;
  private readonly listeners = new Set<Listener>();
  private readonly seenEventIds = new Set<string>();
  private readonly seenEventOrder: string[] = [];
  private snapshot: RunControllerSnapshot;
  private observation: AbortController | undefined;
  private activeConnection: Promise<void> | undefined;

  constructor(agent: EvidenceAgent, rawReceipt: RunReceipt, options: RunControllerOptions = {}) {
    const receipt = RunReceiptSchema.parse(rawReceipt);
    this.agent = agent;
    this.runId = receipt.run_id;
    this.createRequestId = options.createRequestId ?? (() => crypto.randomUUID());
    this.deduplicationWindow = options.deduplicationWindow ?? 2_048;
    this.snapshot = { view: receipt.view, cursor: receipt.cursor, events: [], connection: "idle", error: null };
  }

  readonly getSnapshot = (): RunControllerSnapshot => this.snapshot;

  readonly subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  connect(): Promise<void> {
    if (this.activeConnection) return this.activeConnection;
    const connection = this.consume();
    this.activeConnection = connection;
    return connection.finally(() => {
      if (this.activeConnection === connection) this.activeConnection = undefined;
    });
  }

  disconnect(): void {
    const observation = this.observation;
    this.observation = undefined;
    observation?.abort();
    this.publish({ ...this.snapshot, connection: "idle", error: null });
  }

  async cancel(reason?: string): Promise<CommandReceipt> {
    return this.signal("cancel", reason ? { reason } : {});
  }

  async signal(
    signal: "provide_input" | "approve" | "reject" | "modify" | "pause" | "resume" | "cancel",
    response: Record<string, unknown> = {},
    proposalDigest?: string
  ): Promise<CommandReceipt> {
    return this.agent.act(this.runId, {
      schema_version: 1,
      request_id: this.createRequestId(),
      expected_version: this.snapshot.view.version,
      signal,
      response,
      proposal_digest: proposalDigest
    });
  }

  private async consume(): Promise<void> {
    const observation = new AbortController();
    this.observation = observation;
    this.publish({ ...this.snapshot, connection: "connecting", error: null });
    try {
      for await (const event of this.agent.observe(this.runId, {
        after: this.snapshot.cursor,
        signal: observation.signal
      })) {
        if (observation.signal.aborted) break;
        if (this.snapshot.connection !== "live") this.publish({ ...this.snapshot, connection: "live", error: null });
        this.apply(event);
      }
      if (!observation.signal.aborted) this.publish({ ...this.snapshot, connection: "closed", error: null });
    } catch (error) {
      if (!observation.signal.aborted) {
        this.publish({ ...this.snapshot, connection: "error", error: error instanceof Error ? error.message : String(error) });
        throw error;
      }
    } finally {
      if (this.observation === observation) this.observation = undefined;
    }
  }

  private apply(rawEvent: RunEvent): void {
    const event = RunEventSchema.parse(rawEvent);
    if (event.run_id !== this.runId) throw new Error(`Run event ${event.event_id} belongs to ${event.run_id}, not ${this.runId}.`);
    const isReset = event.change.type === "snapshot" && event.change.reset;
    if (!isReset && (this.seenEventIds.has(event.event_id) || event.cursor <= this.snapshot.cursor)) return;
    if (isReset) this.clearDeduplicationWindow();

    let view: RunView;
    let events = this.snapshot.events;
    if (event.change.type === "snapshot") {
      view = event.change.view;
      if (event.change.reset) events = [];
    } else if (event.change.type === "status_changed") {
      view = {
        ...this.snapshot.view,
        status: event.change.status,
        version: event.run_version,
        last_event_cursor: event.cursor
      };
      events = [...events, event];
    } else {
      view = { ...this.snapshot.view, version: event.run_version, last_event_cursor: event.cursor };
      if (event.change.event_type === "artifact.published") {
        const artifactId = typeof event.change.payload.artifact_id === "string" ? event.change.payload.artifact_id : null;
        if (artifactId) view = { ...view, final_artifact_id: artifactId, outcome: { kind: "artifact", artifact_id: artifactId } };
      }
      events = [...events, event];
    }
    this.remember(event.event_id);
    this.publish({ view, cursor: event.cursor, events, connection: this.snapshot.connection, error: null });
  }

  private remember(eventId: string): void {
    this.seenEventIds.add(eventId);
    this.seenEventOrder.push(eventId);
    if (this.seenEventOrder.length <= this.deduplicationWindow) return;
    const expired = this.seenEventOrder.shift();
    if (expired) this.seenEventIds.delete(expired);
  }

  private clearDeduplicationWindow(): void {
    this.seenEventIds.clear();
    this.seenEventOrder.length = 0;
  }

  private publish(next: RunControllerSnapshot): void {
    this.snapshot = next;
    for (const listener of this.listeners) listener();
  }
}
