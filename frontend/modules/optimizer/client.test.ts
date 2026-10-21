import { describe, expect, it, vi } from "vitest";

import { OptimizerClient } from "./client";


const success = (data: unknown) => new Response(JSON.stringify({
  success: true,
  data,
  error: null,
  request_id: "request-test"
}), { status: 200, headers: { "Content-Type": "application/json" } });

describe("OptimizerClient", () => {
  it("uses nested template overrides and bounded workbench endpoints", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(success({ study_id: "study-1", status: "pending", created: null, cancelled: null, replayed: false }))
      .mockResolvedValueOnce(success({ study_id: "study-1", status: "running", created: 3, cancelled: null, replayed: false }));
    const client = new OptimizerClient({ baseUrl: "http://api.test", fetch });

    await client.createFromTemplate({
      schema_version: 1,
      request_id: "request-1",
      label: "Study",
      base_policy_id: "policy-1",
      template_key: "balanced",
      overrides: { seed: 7, max_candidates: 4 }
    });
    await client.startStudy("study-1");

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/optimizer/studies/from-template",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          schema_version: 1,
          request_id: "request-1",
          label: "Study",
          base_policy_id: "policy-1",
          template_key: "balanced",
          overrides: { seed: 7, max_candidates: 4 }
        })
      })
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/v1/optimizer/studies/study-1/start",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("never fabricates data after an HTTP failure", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: false }), { status: 503 }));
    const client = new OptimizerClient({ baseUrl: "http://api.test", fetch });

    await expect(client.listStudies()).rejects.toMatchObject({ status: 503 });
  });
});
