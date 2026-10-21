import { describe, expect, it } from "vitest";

import { AgentPolicyClient, AgentPolicyTransportError } from "./client";
import { policyComparison, policyDetail, policySimulation } from "./test-fixtures";


const envelope = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ success: status < 400, data: status < 400 ? data : null, error: status < 400 ? null : data, request_id: "request-test" }), {
    status,
    headers: { "content-type": "application/json" }
  });

describe("AgentPolicyClient", () => {
  it("uses exact bounded routes and validates every response", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const summary = policyDetail();
    delete (summary as { config?: unknown }).config;
    const receipt = {
      schema_version: 1, command_id: "command-1", policy_id: "policy-2", version: 2,
      status: "draft", active_policy_id: "policy-1", replayed: false
    };
    const responses = [
      envelope({ schema_version: 1, items: [summary] }),
      envelope(policyDetail()),
      envelope(policyDetail({ id: "policy-2", version: 2, status: "draft" })),
      envelope(receipt, 201),
      envelope(policyComparison()),
      envelope(policySimulation()),
      envelope({ ...receipt, status: "active", active_policy_id: "policy-2" }),
      envelope({ ...receipt, policy_id: "policy-1", version: 1, status: "active" })
    ];
    const client = new AgentPolicyClient({
      baseUrl: "http://api.test",
      fetch: async (input, init) => {
        calls.push({ url: String(input), init });
        return responses.shift()!;
      }
    });

    await client.listPolicies({ status: "draft", limit: 10 });
    await client.getActivePolicy();
    await client.getPolicy("policy-2");
    await client.createPolicy({ request_id: "create-1", label: "Candidate", base_policy_id: "policy-1", config: policyDetail().config });
    await client.comparePolicies("policy-1", "policy-2");
    await client.simulatePolicy("run-1", "policy-2");
    await client.activatePolicy("policy-2", { request_id: "activate-1", expected_active_policy_id: "policy-1", evaluation_id: "evaluation-1" });
    await client.rollbackPolicy("policy-1", { request_id: "rollback-1", expected_active_policy_id: "policy-2" });

    expect(calls.map((item) => item.url)).toEqual([
      "http://api.test/api/v1/agent-policies?status=draft&limit=10",
      "http://api.test/api/v1/agent-policies/active",
      "http://api.test/api/v1/agent-policies/policy-2",
      "http://api.test/api/v1/agent-policies",
      "http://api.test/api/v1/agent-policies/compare?left_id=policy-1&right_id=policy-2",
      "http://api.test/api/v1/agent-policies/simulate",
      "http://api.test/api/v1/agent-policies/policy-2/activate",
      "http://api.test/api/v1/agent-policies/policy-1/rollback"
    ]);
    expect(calls.every((item) => item.init?.cache === "no-store")).toBe(true);
  });

  it("rejects unsafe ids, invalid limits, HTTP errors, and malformed success payloads", async () => {
    const client = new AgentPolicyClient({
      baseUrl: "http://api.test",
      fetch: async () => envelope({ code: "POLICY_NOT_FOUND" }, 404)
    });
    expect(() => client.getPolicy("../unsafe")).toThrow(RangeError);
    expect(() => client.listPolicies({ limit: 101 })).toThrow(RangeError);
    await expect(client.getPolicy("missing")).rejects.toBeInstanceOf(AgentPolicyTransportError);

    const malformed = new AgentPolicyClient({
      baseUrl: "http://api.test",
      fetch: async () => envelope({ ...policyDetail(), private_prompt: "secret" })
    });
    await expect(malformed.getActivePolicy()).rejects.toThrow();
  });
});
