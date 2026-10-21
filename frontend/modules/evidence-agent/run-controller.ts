import { RunEventSchema, RunReceiptSchema, type CommandReceipt, type RunEvent, type RunReceipt, type RunView } from "./contract";
import type { EvidenceAgent } from "./evidence-agent";
import { EvidenceAgentTransportError } from "./http-sse-adapter";

export type RunConnectionState = "idle" | "connecting" | "live" | "retrying" | "closed" | "error";

export function isTerminalRunStatus(status: RunView["status"]): boolean {
  return status === "completed" || status === "insufficient_evidence" || status === "cancelled" || status === "failed";
}

export function isTerminalRunSynchronized(view: Pick<RunView, "status" | "last_event_cursor">, cursor: number): boolean {
  return isTerminalRunStatus(view.status) && cursor >= view.last_event_cursor;
}

function canRetryObservation(error: unknown): boolean {
  if (error instanceof EvidenceAgentTransportError) {
    if ([401, 403, 404, 409, 422].includes(error.status)) return false;
    return error.retryable || [0, 408, 429, 500, 502, 503, 504].includes(error.status);
  }
  // Fetch stream read failures are TypeErrors; malformed contracts are not.
  return error instanceof TypeError;
}

export type RunControllerSnapshot = Readonly<{
  view: RunView;
  cursor: number;
  events: readonly RunEvent[];
  connection: RunConnectionState;
  error: string | null;
  lastSyncedAt: number | null;
  reconnectAttempt: number;
}>;

type RunControllerOptions = {
  createRequestId?: () => string;
  deduplicationWindow?: number;
  reconnectDelaysMs?: readonly number[];
};

type Listener = () => void;

export class RunController {
  private readonly agent: EvidenceAgent;
  private readonly runId: string;
  private readonly createRequestId: () => string;
  private readonly deduplicationWindow: number;
  private readonly reconnectDelaysMs: readonly number[];
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
    this.reconnectDelaysMs = [...(options.reconnectDelaysMs ?? [])];
    if (this.reconnectDelaysMs.length > 5 || this.reconnectDelaysMs.some((delay) => !Number.isFinite(delay) || delay < 0 || delay > 60_000)) {
      throw new RangeError("Observation recovery requires at most five delays between 0 and 60000 ms.");
    }
    this.snapshot = { view: receipt.view, cursor: receipt.cursor, events: [], connection: "idle", error: null,
      lastSyncedAt: null, reconnectAttempt: 0 };
  }

  readonly getSnapshot = (): RunControllerSnapshot => this.snapshot;

  readonly subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  connect(): Promise<void> {
    if (this.activeConnection) return this.activeConnection;
    const observation = new AbortController();
    this.observation = observation;
    const connection = this.consumeWithRecovery(observation);
    this.activeConnection = connection;
    return connection.finally(() => {
      if (this.activeConnection === connection) this.activeConnection = undefined;
    });
  }

  disconnect(): void {
    const observation = this.observation;
    this.observation = undefined;
    this.activeConnection = undefined;
    observation?.abort();
    this.publish({ ...this.snapshot, connection: "idle", error: null });
  }

  reconnect(): Promise<void> {
    this.disconnect();
    return this.connect();
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

  private async consumeWithRecovery(observation: AbortController): Promise<void> {
    for (let attempt = 0; !observation.signal.aborted; attempt += 1) {
      this.publish({ ...this.snapshot, reconnectAttempt: attempt });
      if (observation.signal.aborted) return;
      let failure: unknown;
      try {
        await this.consume(observation);
      } catch (error) {
        failure = error;
      }
      if (observation.signal.aborted) return;
      if (isTerminalRunSynchronized(this.snapshot.view, this.snapshot.cursor) || attempt >= this.reconnectDelaysMs.length ||
        (failure !== undefined && !canRetryObservation(failure))) {
        if (failure) throw failure;
        return;
      }
      this.publish({ ...this.snapshot, connection: "retrying", reconnectAttempt: attempt + 1 });
      if (observation.signal.aborted) return;
      await new Promise<void>((resolve) => {
        const finish = () => {
          clearTimeout(timer);
          observation.signal.removeEventListener("abort", finish);
          resolve();
        };
        const timer = setTimeout(finish, this.reconnectDelaysMs[attempt]);
        observation.signal.addEventListener("abort", finish, { once: true });
      });
    }
  }

  private async consume(observation: AbortController): Promise<void> {
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
    } else if (event.run_version < this.snapshot.view.version) {
      // A reset includes the current projection, then replays older public
      // events to rebuild the ledger. History must not rewind action versions.
      view = this.snapshot.view;
      events = [...events, event];
    } else if (event.change.type === "status_changed") {
      view = {
        ...this.snapshot.view,
        status: event.change.status,
        version: event.run_version,
        last_event_cursor: Math.max(this.snapshot.view.last_event_cursor, event.cursor)
      };
      events = [...events, event];
    } else {
      // A historical event may share the projection's version. It must not
      // lower the known end of history and make an incomplete read look done.
      view = { ...this.snapshot.view, version: event.run_version,
        last_event_cursor: Math.max(this.snapshot.view.last_event_cursor, event.cursor) };
      if (event.change.event_type === "artifact.published") {
        const artifactId = typeof event.change.payload.artifact_id === "string" ? event.change.payload.artifact_id : null;
        if (artifactId) view = { ...view, final_artifact_id: artifactId, outcome: { kind: "artifact", artifact_id: artifactId } };
      }
      events = [...events, event];
    }
    this.remember(event.event_id);
    this.publish({ ...this.snapshot, view, cursor: event.cursor, events, error: null, lastSyncedAt: Date.now() });
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
