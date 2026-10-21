import { describe, expect, it, vi } from "vitest";

import { EvidenceAgentStartError, HttpSseEvidenceAgentAdapter } from "./http-sse-adapter";

const runView = {
  schema_version: 1,
  id: "run-http-1",
  space_id: 7,
  goal: "Trace every factual claim.",
  requested_mode: "auto",
  effective_mode: null,
  status: "queued",
  phase: "route",
  version: 1,
  execution_epoch: 0,
  scope_snapshot: { space_id: 7, revisions: [] },
  budget_limits: { max_steps: 8 },
  budget_usage: { steps: 0 },
  cost_measurement: "unknown",
  provider_mode: "recording",
  last_event_cursor: 4,
  final_artifact_id: null,
  termination_reason: null,
  outcome: null
} as const;

const submission = {
  schema_version: 1,
  command_id: "command-http-1",
  run_id: "run-http-1",
  run_version: 1,
  status: "queued",
  cursor: 4,
  replayed: false
} as const;

function jsonEnvelope(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ success: true, data, error: null, request_id: "http-request" }), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("HttpSseEvidenceAgentAdapter", () => {
  it("shows the backend's error code and retryability with its user message", async () => {
    const adapter = new HttpSseEvidenceAgentAdapter({ fetch: async () => new Response(JSON.stringify({
      success: false,
      error: { code: "RUN_BUSY", user_message: "研究队列暂时繁忙，请稍后重试。", retryable: true }
    }), { status: 503 }) });

    await expect(adapter.start({ request_id: "request-busy", space_id: 7, goal: runView.goal }))
      .rejects.toMatchObject({
        message: "研究队列暂时繁忙，请稍后重试。（代码：RUN_BUSY；可重试）",
        status: 503, code: "RUN_BUSY", retryable: true
      });
  });

  it("shows a readable fallback when the backend omits an error message", async () => {
    const adapter = new HttpSseEvidenceAgentAdapter({ fetch: async () => new Response("unavailable", { status: 503 }) });

    await expect(adapter.start({ request_id: "request-unavailable", space_id: 7, goal: runView.goal }))
      .rejects.toMatchObject({
        message: "研究请求失败（HTTP 503），请稍后重试或检查后端服务。",
        status: 503
      });
  });

  it("turns a failed network request into actionable Chinese without losing retryability", async () => {
    const adapter = new HttpSseEvidenceAgentAdapter({ fetch: async () => { throw new TypeError("Failed to fetch"); } });

    await expect(adapter.start({ request_id: "request-offline", space_id: 7, goal: runView.goal }))
      .rejects.toMatchObject({
        message: "网络连接失败，请检查网络和后端服务后重试。",
        status: 0, code: "NETWORK_UNAVAILABLE", retryable: true
      });
  });

  it("keeps a created run ID when the detail request loses network connectivity", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonEnvelope(submission, 201))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const adapter = new HttpSseEvidenceAgentAdapter({ fetch });

    await expect(adapter.start({ request_id: "request-created-offline", space_id: 7, goal: runView.goal }))
      .rejects.toMatchObject({
        runId: "run-http-1",
        message: "研究任务已创建，但详情读取失败。网络连接失败，请检查网络和后端服务后重试。"
      });
  });
  it("recovers a created run after its initial detail read fails without creating another run", async () => {
    const calls: string[] = [];
    const responses = [
      jsonEnvelope(submission, 201),
      new Response(JSON.stringify({ success: false, error: { user_message: "详情暂不可用" } }), { status: 503 }),
      jsonEnvelope(runView)
    ];
    const adapter = new HttpSseEvidenceAgentAdapter({
      fetch: async (input) => {
        calls.push(String(input));
        return responses.shift()!;
      }
    });
    const input = { request_id: "request-recover", space_id: 7, goal: runView.goal };

    let failed: unknown;
    try { await adapter.start(input); } catch (reason) { failed = reason; }
    expect(failed).toBeInstanceOf(EvidenceAgentStartError);
    expect(failed).toMatchObject({ runId: "run-http-1" });
    const receipt = await adapter.resumeStart("run-http-1");

    expect(receipt.run_id).toBe("run-http-1");
    expect(calls).toEqual([
      "/api/v1/evidence-runs",
      "/api/v1/evidence-runs/run-http-1",
      "/api/v1/evidence-runs/run-http-1"
    ]);
  });
  it("starts through the approved endpoint and returns a validated initial projection", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const responses = [jsonEnvelope(submission, 201), jsonEnvelope(runView)];
    const adapter = new HttpSseEvidenceAgentAdapter({
      fetch: async (input, init) => {
        calls.push({ url: String(input), init });
        return responses.shift()!;
      }
    });

    const receipt = await adapter.start({
      request_id: "request-open-1",
      space_id: 7,
      goal: runView.goal,
      provider_mode: "recording"
    });

    expect(calls.map((call) => [call.init?.method, call.url])).toEqual([
      ["POST", "/api/v1/evidence-runs"],
      ["GET", "/api/v1/evidence-runs/run-http-1"]
    ]);
    expect(JSON.parse(String(calls[0].init?.body))).toMatchObject({ schema_version: 1, request_id: "request-open-1" });
    expect(receipt).toEqual({ schema_version: 1, run_id: "run-http-1", cursor: 4, view: runView });
  });

  it("uses the local backend origin by default while injected fetch tests stay relative", async () => {
    const calls: string[] = [];
    const responses = [jsonEnvelope(submission, 201), jsonEnvelope(runView)];
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return responses.shift()!;
    });
    try {
      await new HttpSseEvidenceAgentAdapter().start({
        request_id: "request-default-origin",
        space_id: 7,
        goal: runView.goal
      });
      expect(calls).toEqual([
        "http://localhost:8000/api/v1/evidence-runs",
        "http://localhost:8000/api/v1/evidence-runs/run-http-1"
      ]);
    } finally {
      vi.unstubAllGlobals();
      vi.unstubAllEnvs();
    }
  });

  it("posts commands instead of treating cancellation as a transport abort", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const adapter = new HttpSseEvidenceAgentAdapter({
      fetch: async (input, init) => {
        calls.push({ url: String(input), init });
        return jsonEnvelope({ ...submission, status: "cancelled", run_version: 2, cursor: 5 });
      }
    });

    const receipt = await adapter.act("run/with-slash", {
      request_id: "command-cancel-1",
      expected_version: 1,
      signal: "cancel"
    });

    expect(calls[0]).toMatchObject({ url: "/api/v1/evidence-runs/run%2Fwith-slash/commands", init: { method: "POST" } });
    expect(JSON.parse(String(calls[0].init?.body))).toMatchObject({ signal: "cancel", expected_version: 1 });
    expect(receipt.status).toBe("cancelled");
  });

  it("resumes SSE with a durable cursor and ignores non-durable heartbeat frames", async () => {
    const chunks = [
      `id: 3\nevent: heartbeat\ndata: ${JSON.stringify({
        schema_version: 1,
        cursor: 3,
        run_version: 1,
        type: "heartbeat",
        payload: {}
      })}\n\n`,
      `id: 5\nevent: run.cancelled\ndata: ${JSON.stringify({
        schema_version: 1,
        cursor: 5,
        run_version: 2,
        type: "run.cancelled",
        payload: { signal: "cancel", response: {} }
      })}\n\n`
    ];
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const adapter = new HttpSseEvidenceAgentAdapter({
      fetch: async (input, init) => {
        calls.push({ url: String(input), init });
        return new Response(chunks.join(""), { headers: { "content-type": "text/event-stream" } });
      }
    });

    const events = [];
    for await (const event of adapter.observe("run-http-1", { after: 3 })) events.push(event);

    expect(calls[0].url).toBe("/api/v1/evidence-runs/run-http-1/stream?after=3");
    expect(new Headers(calls[0].init?.headers).get("Last-Event-ID")).toBe("3");
    expect(events).toMatchObject([
      { cursor: 5, change: { type: "status_changed", status: "cancelled" } }
    ]);
  });

  it("normalizes a reset bootstrap followed by durable ledger and interaction events", async () => {
    const bootstrapView = {
      ...runView,
      status: "awaiting_input",
      version: 3,
      last_event_cursor: 5
    } as const;
    const chunks = [
      `id: 0\nevent: sync\ndata: ${JSON.stringify({
        schema_version: 1,
        cursor: 0,
        run_version: 3,
        type: "sync",
        payload: { run: bootstrapView }
      })}\n\n`,
      `id: 4\nevent: evidence.added\ndata: ${JSON.stringify({
        schema_version: 1,
        cursor: 4,
        run_version: 2,
        type: "evidence.added",
        payload: { evidence_id: "evidence-bootstrap" }
      })}\n\n`,
      `id: 5\nevent: interaction.required\ndata: ${JSON.stringify({
        schema_version: 1,
        cursor: 5,
        run_version: 3,
        type: "interaction.required",
        payload: { kind: "clarification", gate_id: "gate-bootstrap" }
      })}\n\n`
    ];
    const adapter = new HttpSseEvidenceAgentAdapter({
      fetch: async () => new Response(chunks.join(""), { headers: { "content-type": "text/event-stream" } })
    });

    const events = [];
    for await (const event of adapter.observe("run-http-1")) events.push(event);

    expect(events).toMatchObject([
      { cursor: 0, change: { type: "snapshot", reset: true, view: { status: "awaiting_input" } } },
      { cursor: 4, change: { type: "domain_event", event_type: "evidence.added" } },
      { cursor: 5, change: { type: "domain_event", event_type: "interaction.required" } }
    ]);
  });

  it("decodes CRLF delimiters split across transport chunks", async () => {
    const encoder = new TextEncoder();
    const frame = JSON.stringify({
      schema_version: 1,
      cursor: 5,
      run_version: 2,
      type: "run.running",
      payload: {}
    });
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of ["id: 5\r", "\nevent: run.running\r\ndata: ", frame, "\r\n\r", "\n"]) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      }
    });
    const adapter = new HttpSseEvidenceAgentAdapter({
      fetch: async () => new Response(body, { headers: { "content-type": "text/event-stream" } })
    });

    const events = [];
    for await (const event of adapter.observe("run-http-1", { after: 4 })) events.push(event);

    expect(events).toMatchObject([{ cursor: 5, change: { type: "status_changed", status: "running" } }]);
  });
});
