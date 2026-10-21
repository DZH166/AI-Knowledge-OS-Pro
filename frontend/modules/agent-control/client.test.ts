import { describe, expect, it, vi } from "vitest";

import { AgentControlClient, AgentControlTransportError } from "./client";
import { evaluationDetail, evaluationSummary, runTrace } from "./test-fixtures";


const envelope = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ success: status < 400, data: status < 400 ? data : null, error: status < 400 ? null : data, request_id: "request-test" }), {
    status,
    headers: { "content-type": "application/json" }
  });

describe("AgentControlClient", () => {
  it("uses exact bounded routes and validates every successful payload", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const responses = [
      envelope({ schema_version: 1, evaluation_id: "evaluation-1", status: "queued", replayed: false }, 201),
      envelope({ schema_version: 1, items: [evaluationSummary()] }),
      envelope(evaluationDetail()),
      envelope({
        schema_version: 1,
        left_id: "evaluation-1",
        right_id: "evaluation-2",
        compatible: true,
        incompatibility_reasons: [],
        verdict: "stable",
        policy_changed: false,
        left_policy_fingerprint: "a".repeat(64),
        right_policy_fingerprint: "a".repeat(64),
        metric_deltas: [],
        gate_changes: [],
        new_failure_case_ids: [],
        resolved_failure_case_ids: []
      }),
      envelope(runTrace())
    ];
    const client = new AgentControlClient({
      baseUrl: "http://api.test",
      fetch: async (input, init) => {
        calls.push({ url: String(input), init });
        return responses.shift()!;
      }
    });

    await client.startEvaluation({ request_id: "request-1", label: "Baseline" });
    await client.listEvaluations({ status: "passed", limit: 10 });
    await client.getEvaluation("evaluation-1");
    await client.compareEvaluations("evaluation-1", "evaluation-2");
    await client.getRunTrace("run-1");

    expect(calls.map((item) => item.url)).toEqual([
      "http://api.test/api/v1/agent-evaluations",
      "http://api.test/api/v1/agent-evaluations?status=passed&limit=10",
      "http://api.test/api/v1/agent-evaluations/evaluation-1",
      "http://api.test/api/v1/agent-evaluations/compare?left_id=evaluation-1&right_id=evaluation-2",
      "http://api.test/api/v1/evidence-runs/run-1/trace"
    ]);
    expect(calls[0].init?.method).toBe("POST");
    expect(calls.every((item) => item.init?.cache === "no-store")).toBe(true);
    expect(JSON.parse(String(calls[0].init?.body))).toMatchObject({ schema_version: 1 });
  });

  it("polls sequentially to a terminal snapshot without a timer waterfall", async () => {
    let now = 0;
    const statuses: Array<"queued" | "running" | "passed"> = ["queued", "running", "passed"];
    const fetch = vi.fn(async () => envelope(evaluationDetail(statuses.shift() ?? "passed")));
    const client = new AgentControlClient({
      baseUrl: "http://api.test",
      fetch,
      now: () => now,
      sleep: async (milliseconds) => { now += milliseconds; }
    });
    const detail = await client.waitForEvaluation("evaluation-1", { timeoutMs: 5_000, intervalMs: 100 });
    expect(detail.summary.status).toBe("passed");
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(now).toBe(200);
  });

  it("times out, aborts, and rejects unsafe ids without making extra requests", async () => {
    let now = 0;
    const fetch = vi.fn(async () => envelope(evaluationDetail("running")));
    const client = new AgentControlClient({
      baseUrl: "http://api.test",
      fetch,
      now: () => now,
      sleep: async (milliseconds) => { now += milliseconds; }
    });
    await expect(client.waitForEvaluation("evaluation-1", { timeoutMs: 1_000, intervalMs: 500 })).rejects.toMatchObject({ status: 408 });
    const controller = new AbortController();
    controller.abort(new DOMException("Stopped", "AbortError"));
    await expect(client.waitForEvaluation("evaluation-1", { signal: controller.signal })).rejects.toMatchObject({ name: "AbortError" });
    expect(() => client.getEvaluation("../unsafe/path")).toThrow(RangeError);
  });

  it("never falls back when HTTP or runtime validation fails", async () => {
    const httpClient = new AgentControlClient({
      baseUrl: "http://api.test",
      fetch: async () => envelope({ code: "EVALUATION_NOT_FOUND", demo: evaluationDetail() }, 404)
    });
    await expect(httpClient.getEvaluation("missing")).rejects.toBeInstanceOf(AgentControlTransportError);

    const malformedClient = new AgentControlClient({
      baseUrl: "http://api.test",
      fetch: async () => envelope({
        ...runTrace(),
        events: [{ ...runTrace().events[0], prompt: "private prompt" }]
      })
    });
    await expect(malformedClient.getRunTrace("run-1")).rejects.toThrow();
  });

  it("removes the abort listener after the default polling sleep resolves", async () => {
    const controller = new AbortController();
    const add = vi.spyOn(controller.signal, "addEventListener");
    const remove = vi.spyOn(controller.signal, "removeEventListener");
    const statuses: Array<"queued" | "passed"> = ["queued", "passed"];
    const client = new AgentControlClient({
      baseUrl: "http://api.test",
      fetch: async () => envelope(evaluationDetail(statuses.shift() ?? "passed"))
    });
    await client.waitForEvaluation("evaluation-1", {
      timeoutMs: 1_000,
      intervalMs: 100,
      signal: controller.signal
    });
    expect(add).toHaveBeenCalledTimes(1);
    expect(remove).toHaveBeenCalledTimes(1);
  });
});
