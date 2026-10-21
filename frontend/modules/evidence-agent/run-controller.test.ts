import { describe, expect, it, vi } from "vitest";

import { CommandReceiptSchema, RunEventSchema, RunReceiptSchema, type RunEvent, type RunView } from "./contract";
import type { EvidenceAgent, ObserveOptions } from "./evidence-agent";
import { RunController } from "./run-controller";
import { HttpSseEvidenceAgentAdapter } from "./http-sse-adapter";

const baseView: RunView = {
  schema_version: 1,
  id: "run-controller-1",
  space_id: 1,
  goal: "Keep claims traceable.",
  requested_mode: "auto",
  effective_mode: null,
  status: "queued",
  phase: "route",
  version: 1,
  execution_epoch: 0,
  scope_snapshot: { space_id: 1, revisions: [] },
  budget_limits: { max_steps: 8 },
  budget_usage: { steps: 0 },
  cost_measurement: "unknown",
  provider_mode: "recording",
  last_event_cursor: 4,
  final_artifact_id: null,
  termination_reason: null,
  outcome: null
};

const receipt = RunReceiptSchema.parse({ schema_version: 1, run_id: baseView.id, cursor: 4, view: baseView });

function event(values: Partial<RunEvent> & Pick<RunEvent, "event_id" | "cursor" | "run_version" | "change">): RunEvent {
  return RunEventSchema.parse({ schema_version: 1, run_id: baseView.id, ...values });
}

class FakeAgent implements EvidenceAgent {
  readonly observedAfter: Array<number | undefined> = [];
  readonly commands: unknown[] = [];
  eventBatches: RunEvent[][] = [];

  async start() {
    return receipt;
  }

  async *observe(_runId: string, options: ObserveOptions = {}) {
    this.observedAfter.push(options.after);
    for (const item of this.eventBatches.shift() ?? []) yield item;
  }

  async act(runId: string, command: Parameters<EvidenceAgent["act"]>[1]) {
    this.commands.push(command);
    return CommandReceiptSchema.parse({
      schema_version: 1,
      command_id: command.request_id,
      run_id: runId,
      run_version: command.expected_version + 1,
      status: command.signal === "cancel" ? "cancelled" : "queued",
      cursor: 5,
      replayed: false
    });
  }
}

describe("RunController", () => {
  it("does not automatically retry a forbidden or missing run", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn(async () => new Response("not found", { status: 404 }));
    const controller = new RunController(new HttpSseEvidenceAgentAdapter({ fetch }), receipt,
      { reconnectDelaysMs: [100, 200] });
    try {
      const failure = controller.connect().catch((error: unknown) => error);
      await vi.advanceTimersByTimeAsync(1000);
      expect(await failure).toMatchObject({ status: 404 });
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(controller.getSnapshot().connection).toBe("error");
    } finally {
      controller.disconnect();
      vi.useRealTimers();
    }
  });

  it("recovers the same run from its accepted cursor without duplicating events or submitting commands", async () => {
    vi.useFakeTimers();
    const agent = new FakeAgent();
    agent.eventBatches.push([
      event({ event_id: "event-5", cursor: 5, run_version: 2, change: { type: "status_changed", status: "running" } })
    ], [
      event({ event_id: "event-5", cursor: 5, run_version: 2, change: { type: "status_changed", status: "running" } }),
      event({ event_id: "event-6", cursor: 6, run_version: 3, change: { type: "status_changed", status: "completed" } })
    ]);
    const controller = new RunController(agent, receipt, { reconnectDelaysMs: [100, 200] });
    try {
      const connection = controller.connect();
      await vi.advanceTimersByTimeAsync(100);
      await connection;
      expect(agent.observedAfter).toEqual([4, 5]);
      expect(controller.getSnapshot()).toMatchObject({
        cursor: 6, connection: "closed", view: { status: "completed" },
        events: [{ event_id: "event-5" }, { event_id: "event-6" }], lastSyncedAt: expect.any(Number)
      });
      expect(agent.commands).toEqual([]);
      await vi.advanceTimersByTimeAsync(10_000);
      expect(agent.observedAfter).toHaveLength(2);
    } finally {
      controller.disconnect();
      vi.useRealTimers();
    }
  });

  it("resumes from its cursor and ignores duplicate or non-increasing events", async () => {
    const agent = new FakeAgent();
    agent.eventBatches.push([
      event({ event_id: "event-5", cursor: 5, run_version: 2, change: { type: "status_changed", status: "running" } }),
      event({ event_id: "event-5", cursor: 6, run_version: 3, change: { type: "status_changed", status: "cancelled" } }),
      event({ event_id: "event-old", cursor: 5, run_version: 3, change: { type: "status_changed", status: "failed" } })
    ]);
    const controller = new RunController(agent, receipt);

    await controller.connect();

    expect(agent.observedAfter).toEqual([4]);
    expect(controller.getSnapshot()).toMatchObject({ cursor: 5, view: { status: "running", version: 2 }, connection: "closed" });
  });

  it("replaces the projection and de-duplication window on an explicit reset snapshot", async () => {
    const agent = new FakeAgent();
    const resetView = { ...baseView, status: "routing", version: 3, last_event_cursor: 9 } as const;
    agent.eventBatches.push([
      event({
        event_id: "event-reset",
        cursor: 9,
        run_version: 3,
        change: { type: "snapshot", reset: true, view: resetView }
      })
    ]);
    const controller = new RunController(agent, receipt);

    await controller.connect();

    expect(controller.getSnapshot()).toMatchObject({ cursor: 9, view: resetView });
  });

  it("replays historical ledger events without rolling a reset snapshot back to an older run version", async () => {
    const agent = new FakeAgent();
    const currentView = { ...baseView, status: "awaiting_approval", version: 8, last_event_cursor: 12 } as const;
    agent.eventBatches.push([
      event({ event_id: "reset", cursor: 0, run_version: 8, change: { type: "snapshot", reset: true, view: currentView } }),
      event({ event_id: "old-status", cursor: 6, run_version: 2, change: { type: "status_changed", status: "running" } }),
      event({ event_id: "old-evidence", cursor: 7, run_version: 3,
        change: { type: "domain_event", event_type: "evidence.added", payload: { evidence_id: "evidence-1" } } })
    ]);
    const controller = new RunController(agent, receipt);
    await controller.connect();
    expect(controller.getSnapshot()).toMatchObject({
      cursor: 7, view: { status: "awaiting_approval", version: 8 },
      events: [{ event_id: "old-status" }, { event_id: "old-evidence" }]
    });
  });

  it("rebuilds ledger and pending interaction events after a future cursor reset", async () => {
    const agent = new FakeAgent();
    const futureReceipt = RunReceiptSchema.parse({
      schema_version: 1,
      run_id: baseView.id,
      cursor: 99,
      view: baseView
    });
    const resetView = {
      ...baseView,
      status: "awaiting_input",
      version: 3,
      last_event_cursor: 5
    } as const;
    agent.eventBatches.push([
      event({
        event_id: "event-reset-zero",
        cursor: 0,
        run_version: 3,
        change: { type: "snapshot", reset: true, view: resetView }
      }),
      event({
        event_id: "event-evidence-4",
        cursor: 4,
        run_version: 2,
        change: {
          type: "domain_event",
          event_type: "evidence.added",
          payload: { evidence_id: "evidence-bootstrap" }
        }
      }),
      event({
        event_id: "event-interaction-5",
        cursor: 5,
        run_version: 3,
        change: {
          type: "domain_event",
          event_type: "interaction.required",
          payload: { kind: "clarification", gate_id: "gate-bootstrap" }
        }
      })
    ]);
    const controller = new RunController(agent, futureReceipt);

    await controller.connect();

    expect(agent.observedAfter).toEqual([99]);
    expect(controller.getSnapshot()).toMatchObject({
      cursor: 5,
      view: { status: "awaiting_input", version: 3 },
      events: [
        { change: { type: "domain_event", event_type: "evidence.added" } },
        { change: { type: "domain_event", event_type: "interaction.required" } }
      ]
    });
  });

  it("submits cancellation as an idempotent domain command without aborting observation or changing status optimistically", async () => {
    const agent = new FakeAgent();
    const controller = new RunController(agent, receipt, { createRequestId: () => "cancel-request-1" });

    const cancellation = await controller.cancel("User stopped the bounded run.");

    expect(agent.observedAfter).toEqual([]);
    expect(agent.commands).toEqual([
      {
        schema_version: 1,
        request_id: "cancel-request-1",
        expected_version: 1,
        signal: "cancel",
        response: { reason: "User stopped the bounded run." }
      }
    ]);
    expect(cancellation.status).toBe("cancelled");
    expect(controller.getSnapshot()).toMatchObject({ connection: "idle", view: { status: "queued" } });
  });

  it("submits Resume from a paused projection without changing status optimistically", async () => {
    const agent = new FakeAgent();
    const pausedView = { ...baseView, status: "paused", version: 6, last_event_cursor: 9 } as const;
    const pausedReceipt = RunReceiptSchema.parse({
      schema_version: 1,
      run_id: pausedView.id,
      cursor: 9,
      view: pausedView
    });
    const controller = new RunController(agent, pausedReceipt, { createRequestId: () => "resume-request-1" });

    const resumed = await controller.signal("resume");

    expect(agent.commands).toEqual([
      {
        schema_version: 1,
        request_id: "resume-request-1",
        expected_version: 6,
        signal: "resume",
        response: {},
        proposal_digest: undefined
      }
    ]);
    expect(resumed.status).toBe("queued");
    expect(controller.getSnapshot()).toMatchObject({ connection: "idle", view: { status: "paused", version: 6 } });
  });

  it("uses the last accepted cursor when explicitly connected again", async () => {
    const agent = new FakeAgent();
    agent.eventBatches.push([
      event({ event_id: "event-5", cursor: 5, run_version: 2, change: { type: "status_changed", status: "running" } })
    ], []);
    const controller = new RunController(agent, receipt);

    await controller.connect();
    await controller.connect();

    expect(agent.observedAfter).toEqual([4, 5]);
  });

  it("bounds automatic retries and cancels the pending retry when disconnected", async () => {
    vi.useFakeTimers();
    const agent = new FakeAgent();
    const controller = new RunController(agent, receipt, { reconnectDelaysMs: [100, 200] });
    try {
      const connection = controller.connect();
      await vi.advanceTimersByTimeAsync(10_000);
      await connection;
      expect(agent.observedAfter).toEqual([4, 4, 4]);
      expect(controller.getSnapshot()).toMatchObject({ connection: "closed", reconnectAttempt: 2, lastSyncedAt: null });
      const retried = controller.reconnect();
      await vi.advanceTimersByTimeAsync(0);
      expect(controller.getSnapshot().connection).toBe("retrying");
      controller.disconnect();
      await retried;
      await vi.advanceTimersByTimeAsync(10_000);
      expect(agent.observedAfter).toHaveLength(4);
      expect(controller.getSnapshot().connection).toBe("idle");
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      controller.disconnect();
      vi.useRealTimers();
    }
  });

  it.each([2, 8])("finishes reading a terminal snapshot's known history before stopping recovery (history version %i)", async (historyVersion) => {
    const agent = new FakeAgent();
    const terminalReceipt = RunReceiptSchema.parse({ ...receipt, cursor: 0,
      view: { ...baseView, status: "completed", version: 8, last_event_cursor: 12 } });
    agent.eventBatches.push([
      event({ event_id: "history-6", cursor: 6, run_version: historyVersion,
        change: { type: "domain_event", event_type: "evidence.added", payload: { evidence_id: "historical-evidence" } } })
    ], [
      event({ event_id: "history-12", cursor: 12, run_version: 8, change: { type: "status_changed", status: "completed" } })
    ]);
    const controller = new RunController(agent, terminalReceipt, { reconnectDelaysMs: [0, 0] });
    await controller.connect();
    expect(agent.observedAfter).toEqual([0, 6]);
    expect(controller.getSnapshot()).toMatchObject({ cursor: 12, connection: "closed",
      view: { status: "completed", version: 8, last_event_cursor: 12 } });
  });

  it("bounds retries for incomplete terminal history and allows a later manual recovery", async () => {
    const agent = new FakeAgent();
    const terminalReceipt = RunReceiptSchema.parse({ ...receipt, cursor: 0,
      view: { ...baseView, status: "completed", version: 8, last_event_cursor: 12 } });
    agent.eventBatches.push([
      event({ event_id: "partial-6", cursor: 6, run_version: 2, change: { type: "status_changed", status: "running" } })
    ], [], []);
    const controller = new RunController(agent, terminalReceipt, { reconnectDelaysMs: [0, 0] });
    await controller.connect();
    expect(agent.observedAfter).toEqual([0, 6, 6]);
    expect(controller.getSnapshot()).toMatchObject({ cursor: 6, reconnectAttempt: 2,
      view: { status: "completed", last_event_cursor: 12 } });
    agent.eventBatches.push([
      event({ event_id: "complete-12", cursor: 12, run_version: 8, change: { type: "status_changed", status: "completed" } })
    ]);
    await controller.reconnect();
    expect(agent.observedAfter).toEqual([0, 6, 6, 6]);
    expect(controller.getSnapshot().cursor).toBe(12);
    expect(agent.commands).toEqual([]);
  });

  it("ignores events from an aborted observer when a replacement connection is already live", async () => {
    let releaseOld: (() => void) | undefined;
    class DelayedAgent extends FakeAgent {
      async *observe(_runId: string, options: ObserveOptions = {}) {
        this.observedAfter.push(options.after);
        if (this.observedAfter.length === 1) {
          await new Promise<void>((resolve) => { releaseOld = resolve; });
          yield event({ event_id: "stale", cursor: 20, run_version: 20,
            change: { type: "status_changed", status: "failed" } });
        } else {
          yield event({ event_id: "fresh", cursor: 6, run_version: 3,
            change: { type: "status_changed", status: "completed" } });
        }
      }
    }
    const agent = new DelayedAgent();
    const controller = new RunController(agent, receipt);
    const oldConnection = controller.connect();
    const replacement = controller.reconnect();
    await replacement;
    releaseOld?.();
    await oldConnection;
    expect(controller.getSnapshot()).toMatchObject({
      connection: "closed", cursor: 6, view: { status: "completed", version: 3 }, events: [{ event_id: "fresh" }]
    });
  });

  it("does not arm a retry after a subscriber disconnects upon learning about the interrupted connection", async () => {
    vi.useFakeTimers();
    const controller = new RunController(new FakeAgent(), receipt, { reconnectDelaysMs: [1000] });
    const unsubscribe = controller.subscribe(() => {
      if (controller.getSnapshot().connection === "retrying") controller.disconnect();
    });
    try {
      const connection = controller.connect();
      await vi.advanceTimersByTimeAsync(0);
      expect(vi.getTimerCount()).toBe(0);
      await connection;
      expect(controller.getSnapshot().connection).toBe("idle");
    } finally {
      unsubscribe();
      controller.disconnect();
      vi.useRealTimers();
    }
  });
});
