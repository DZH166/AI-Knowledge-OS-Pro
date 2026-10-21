import { describe, expect, it, vi } from "vitest";

import { AgentRunShareClient } from "./client";


const success = (data: unknown) => new Response(JSON.stringify({
  success: true,
  data,
  error: null,
  request_id: "request-test"
}), { status: 200, headers: { "Content-Type": "application/json" } });

describe("AgentRunShareClient", () => {
  it("owns the bounded create and revoke share operations", async () => {
    const receipt = {
      token: "a".repeat(64),
      url_path: `/api/v1/agent-runs/shared/${"a".repeat(64)}`,
      expires_at: "2026-09-08T00:00:00Z"
    };
    const fetch = vi.fn()
      .mockResolvedValueOnce(success(receipt))
      .mockResolvedValueOnce(success({ success: true, revoked: true }));
    const client = new AgentRunShareClient({ baseUrl: "http://api.test", fetch });

    await expect(client.create("run-1")).resolves.toEqual(receipt);
    await expect(client.revoke("a".repeat(64))).resolves.toEqual({ success: true, revoked: true });
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/agent-runs/run-1/share",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      `http://api.test/api/v1/agent-runs/shared/${"a".repeat(64)}`,
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("rejects unsafe identifiers before a request", async () => {
    const fetch = vi.fn();
    const client = new AgentRunShareClient({ baseUrl: "http://api.test", fetch });
    expect(() => client.create("../run")).toThrow("Unsafe Agent Run identifier");
    expect(() => client.revoke("short")).toThrow("Unsafe share token");
    expect(fetch).not.toHaveBeenCalled();
  });
});
