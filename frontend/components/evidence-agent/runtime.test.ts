import { afterEach, describe, expect, it, vi } from "vitest";

import { EvidenceAgentStartError, RunController } from "@/modules/evidence-agent";

import {
  findCompletedRecordingRunForArtifact,
  loadEvidenceRun,
  listStoredRuns,
  recordingArtifactTitle,
  startEvidenceRun
} from "./runtime";
import { ledgerFromEvents, planFromEvents } from "./run-presenter";

const currentView = {
  schema_version: 1,
  id: "run-runtime-bootstrap",
  space_id: 1,
  goal: "Restore the durable evidence ledger.",
  requested_mode: "force_agent",
  effective_mode: "force_agent",
  status: "awaiting_input",
  phase: "assess",
  version: 3,
  execution_epoch: 0,
  scope_snapshot: { space_id: 1, revisions: [] },
  budget_limits: { max_steps: 8 },
  budget_usage: { steps: 2 },
  cost_measurement: "unknown",
  provider_mode: "real",
  last_event_cursor: 5,
  final_artifact_id: null,
  termination_reason: null,
  outcome: null
} as const;

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("production run bootstrap", () => {
  it("retries a known created run by reading its details, without posting a second task", async () => {
    let stored = "[]";
    const calls: string[] = [];
    vi.stubGlobal("window", { localStorage: {
      getItem: () => stored,
      setItem: (_key: string, value: string) => { stored = value; }
    } });
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://evidence.example.test");
    vi.stubGlobal("fetch", async (path: RequestInfo | URL) => {
      const url = String(path);
      calls.push(url);
      if (url.endsWith("/evidence-runs")) {
        return new Response(JSON.stringify({
          success: true,
          data: { schema_version: 1, command_id: "command-1", run_id: currentView.id, run_version: 3, status: "queued", cursor: 5, replayed: false },
          error: null,
          request_id: "http-request"
        }), { status: 201 });
      }
      if (calls.length === 2) return new Response("temporary failure", { status: 503 });
      return new Response(JSON.stringify({ success: true, data: currentView, error: null, request_id: "http-request" }));
    });
    const input = { request_id: "request-keep-1", space_id: 1, goal: currentView.goal };

    let failed: unknown;
    try { await startEvidenceRun(input, false); } catch (reason) { failed = reason; }
    expect(failed).toBeInstanceOf(EvidenceAgentStartError);
    const recovered = await startEvidenceRun(input, false, (failed as EvidenceAgentStartError).runId);

    expect(recovered.receipt.run_id).toBe(currentView.id);
    expect(calls).toEqual([
      "https://evidence.example.test/api/v1/evidence-runs",
      `https://evidence.example.test/api/v1/evidence-runs/${currentView.id}`,
      `https://evidence.example.test/api/v1/evidence-runs/${currentView.id}`
    ]);
    expect(listStoredRuns()).toMatchObject([{ input: { request_id: "request-keep-1" }, receipt: { run_id: currentView.id } }]);
  });
  it("does not reuse a stored latest cursor when the page needs durable event reconstruction", async () => {
    const stored = [{
      mode: "production",
      input: {
        request_id: "request-runtime-bootstrap",
        space_id: 1,
        goal: currentView.goal,
        mode: "force_agent",
        provider_mode: "real"
      },
      receipt: {
        schema_version: 1,
        run_id: currentView.id,
        cursor: 99,
        view: { ...currentView, last_event_cursor: 99 }
      },
      created_at: "2026-08-15T10:00:00.000Z"
    }];
    const requests: string[] = [];
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => JSON.stringify(stored),
        setItem: vi.fn()
      }
    });
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://evidence.example.test");
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      requests.push(String(input));
      const frames = requests.length === 1
        ? [{
            schema_version: 1,
            cursor: 0,
            run_version: currentView.version,
            type: "sync",
            payload: { run: currentView }
          }]
        : [
            {
              schema_version: 1,
              cursor: 1,
              run_version: 1,
              type: "run.opened",
              payload: { goal: currentView.goal }
            },
            {
              schema_version: 1,
              cursor: 4,
              run_version: 2,
              type: "evidence.added",
              payload: { evidence_id: "evidence-bootstrap" }
            },
            {
              schema_version: 1,
              cursor: 5,
              run_version: 3,
              type: "interaction.required",
              payload: { kind: "clarification", gate_id: "gate-bootstrap" }
            }
          ];
      const body = frames
        .map((frame) => `id: ${frame.cursor}\nevent: ${frame.type}\ndata: ${JSON.stringify(frame)}\n\n`)
        .join("");
      return new Response(body, {
        headers: { "content-type": "text/event-stream" }
      });
    });

    const loaded = await loadEvidenceRun(currentView.id, false);
    const controller = new RunController(loaded.agent, loaded.receipt);
    await controller.connect();

    expect(requests).toEqual([
      `https://evidence.example.test/api/v1/evidence-runs/${currentView.id}/stream`,
      `https://evidence.example.test/api/v1/evidence-runs/${currentView.id}/stream?after=0`
    ]);
    expect(loaded.receipt).toMatchObject({
      run_id: currentView.id,
      cursor: 0,
      view: { status: "awaiting_input", last_event_cursor: 5 }
    });
    expect(controller.getSnapshot()).toMatchObject({
      cursor: 5,
      view: { status: "awaiting_input", version: 3 },
      events: [
        { change: { type: "domain_event", event_type: "run.opened" } },
        { change: { type: "domain_event", event_type: "evidence.added" } },
        { change: { type: "domain_event", event_type: "interaction.required" } }
      ]
    });
  });

  it("rebuilds a visible plan and the final supported ledger relation from production SSE replay", async () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => "[]",
        setItem: vi.fn()
      }
    });
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://evidence.example.test");
    let requestCount = 0;
    vi.stubGlobal("fetch", async () => {
      requestCount += 1;
      const frames = requestCount === 1
        ? [{
            schema_version: 1,
            cursor: 0,
            run_version: 4,
            type: "sync",
            payload: { run: { ...currentView, version: 4, status: "completed", last_event_cursor: 4 } }
          }]
        : [
            {
              schema_version: 1,
              cursor: 1,
              run_version: 2,
              type: "plan.created",
              payload: {
                plan_version: 1,
                strategy: "structured_model_plan",
                requirements: ["核验不可变引用"]
              }
            },
            {
              schema_version: 1,
              cursor: 2,
              run_version: 3,
              type: "evidence.added",
              payload: {
                evidence_id: "evidence-production",
                source_title: "Production source",
                excerpt: "candidate production evidence",
                relation: "candidate",
                reference: {
                  source_id: 1,
                  revision_id: 2,
                  index_revision_id: 3,
                  chunk_id: 4,
                  content_hash: "a".repeat(64),
                  locator: { kind: "text", start_offset: 0, end_offset: 29 }
                }
              }
            },
            {
              schema_version: 1,
              cursor: 3,
              run_version: 4,
              type: "evidence.relation_changed",
              payload: {
                evidence_id: "evidence-production",
                requirement_id: "requirement-production",
                requirement_ordinal: 1,
                previous_relation: "candidate",
                relation: "supports",
                reason: "model_selected_support",
                method: "model_assessment"
              }
            },
            {
              schema_version: 1,
              cursor: 4,
              run_version: 4,
              type: "run.completed",
              payload: {}
            }
          ];
      const body = frames
        .map((frame) => `id: ${frame.cursor}\nevent: ${frame.type}\ndata: ${JSON.stringify(frame)}\n\n`)
        .join("");
      return new Response(body, { headers: { "content-type": "text/event-stream" } });
    });

    const loaded = await loadEvidenceRun(currentView.id, false);
    const controller = new RunController(loaded.agent, loaded.receipt);
    await controller.connect();
    const events = controller.getSnapshot().events;

    expect(planFromEvents(events)?.requirements).toEqual(["核验不可变引用"]);
    expect(ledgerFromEvents(events)).toMatchObject([
      { id: "evidence-production", relation: "supports", sourceTitle: "Production source" }
    ]);
  });
});

describe("recording run identity", () => {
  it("does not collide when two runs start in the same millisecond", async () => {
    let stored = "[]";
    vi.spyOn(Date, "now").mockReturnValue(1_766_000_000_000);
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => stored,
        setItem: (_key: string, value: string) => {
          stored = value;
        }
      }
    });

    const first = await startEvidenceRun(
      { request_id: "same-ms-1", space_id: 1, goal: "First recording run" },
      true
    );
    const second = await startEvidenceRun(
      { request_id: "same-ms-2", space_id: 1, goal: "Second recording run" },
      true
    );

    expect(first.receipt.run_id).not.toBe(second.receipt.run_id);
    expect(first.receipt.run_id).toMatch(/^demo-run-[0-9a-f-]{36}$/);
    expect(second.receipt.run_id).toMatch(/^demo-run-[0-9a-f-]{36}$/);
  });

  it("reconstructs a completed run after reload instead of returning to pre-approval", async () => {
    let stored = "[]";
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => stored,
        setItem: (_key: string, value: string) => {
          stored = value;
        }
      }
    });

    const started = await startEvidenceRun(
      { request_id: "recording-refresh", space_id: 9_001, goal: "Persist the completed Recording run." },
      true
    );
    const firstController = new RunController(started.agent, started.receipt, {
      createRequestId: () => "recording-refresh-approval"
    });
    await firstController.connect();
    await firstController.signal("approve", {}, "a".repeat(64));
    await firstController.connect();
    expect(firstController.getSnapshot().view.status).toBe("completed");

    const persisted = listStoredRuns()[0];
    expect(persisted).toMatchObject({
      receipt: {
        run_id: started.receipt.run_id,
        view: {
          status: "completed",
          final_artifact_id: `artifact-${started.receipt.run_id}`
        }
      },
      recording_journal: {
        events: expect.arrayContaining([
          expect.objectContaining({ change: { type: "status_changed", status: "completed" } })
        ]),
        commands: [expect.objectContaining({ command: expect.objectContaining({ signal: "approve" }) })]
      }
    });

    const restored = await loadEvidenceRun(started.receipt.run_id, true);
    const reloadedController = new RunController(restored.agent, restored.receipt);
    await reloadedController.connect();

    expect(reloadedController.getSnapshot()).toMatchObject({
      view: {
        id: started.receipt.run_id,
        status: "completed",
        final_artifact_id: `artifact-${started.receipt.run_id}`
      },
      cursor: 14
    });
    expect(reloadedController.getSnapshot().events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          change: expect.objectContaining({
            type: "domain_event",
            event_type: "evidence.added"
          })
        })
      ])
    );
    const completedRun = findCompletedRecordingRunForArtifact(`artifact-${started.receipt.run_id}`);
    expect(completedRun?.receipt.run_id).toBe(started.receipt.run_id);
    expect(completedRun && recordingArtifactTitle(completedRun)).toBe("Evidence Agent 升级决策简报");
    expect(findCompletedRecordingRunForArtifact("artifact-does-not-exist")).toBeNull();
  });
});
