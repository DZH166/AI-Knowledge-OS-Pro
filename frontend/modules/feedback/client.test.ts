import { describe, expect, it, vi } from "vitest";
import { FeedbackClient, FeedbackIntent } from "./client";
import { FeedbackSchema, type Feedback } from "./contract";


describe("reviewed feedback client", () => {
  it("keeps a request identity for the same user intent", () => {
    const identity = new FeedbackIntent(() => "request-1");
    expect(identity.for({ comment: "one" })).toBe("request-1");
    expect(identity.for({ comment: "one" })).toBe("request-1");
    const fresh = new FeedbackIntent(vi.fn().mockReturnValueOnce("first").mockReturnValueOnce("second"));
    expect(fresh.for({ comment: "one" })).toBe("first");
    expect(fresh.for({ comment: "two" })).toBe("second");
  });

  it("surfaces backend errors and never returns a fabricated feedback list", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: false,
      error: { user_message: "反馈快照完整性校验失败。" } }), { status: 409 }));
    const client = new FeedbackClient({ baseUrl: "http://localhost:8000", fetch });
    await expect(client.list({})).rejects.toThrow("反馈快照完整性校验失败");
  });

  it("reads persisted feedback through a no-store typed request", async () => {
    const fetch = vi.fn().mockResolvedValue(success(fixture()));
    const client = new FeedbackClient({ baseUrl: "http://localhost:8000", fetch });
    expect((await client.get(1)).comment).toBe("Missing an explanation");
    expect(fetch.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/feedback/1");
    expect(fetch.mock.calls[0][1].cache).toBe("no-store");
  });

  it("rejects demo-to-real relabeling and accepted state without a sample", () => {
    expect(FeedbackSchema.safeParse({ ...fixture(), provider_mode: "real" }).success).toBe(false);
    expect(FeedbackSchema.safeParse({ ...fixture(), status: "accepted" }).success).toBe(false);
  });

  it("rejects malformed success payloads rather than treating them as empty results", async () => {
    const client = new FeedbackClient({ baseUrl: "http://localhost:8000", fetch: vi.fn().mockResolvedValue(success({ items: [] })) });
    await expect(client.list({})).rejects.toThrow("反馈响应格式无法验证");
  });

  it("validates the exported content fingerprint and rejects a mismatched selection", async () => {
    const item = fixture();
    item.status = "accepted";
    item.version = 2;
    item.review = { decision: "accepted", reason: "Reviewed", reviewer: "local_user", reviewed_at: "2026-09-06T00:00:00Z" };
    item.sample = { id: 1, split: "holdout", expected_answer: "Reference answer", acceptance_criteria: "Cite the source",
      reference_evidence_ids: [], snapshot_sha256: "a".repeat(64), expectation_kind: "human_reviewed_not_automatically_verified" };
    const content = JSON.stringify({ schema_version: 1, format: "human_reviewed_feedback_v1", split: "holdout", provider_mode: "demo",
      claim_boundary: "Human expectations, not model quality evidence", cases: [item] });
    const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(content))), value => value.toString(16).padStart(2, "0")).join("");
    const receipt = { filename: "feedback-holdout-demo.json", content, sha256, count: 1, split: "holdout", provider_mode: "demo" };
    const fetch = vi.fn().mockImplementation(async () => success(receipt));
    const client = new FeedbackClient({ baseUrl: "http://localhost:8000", fetch });
    expect((await client.export([1])).content).toBe(content);
    await expect(client.export([2])).rejects.toThrow("导出内容与所选样例");
    fetch.mockImplementation(async () => success({ ...receipt, sha256: "0".repeat(64) }));
    await expect(client.export([1])).rejects.toThrow("导出内容与所选样例");
  });
});

function success(data: unknown) { return new Response(JSON.stringify({ success: true, data }), { status: 200 }); }
function fixture(): Feedback {
  return { id: 1, artifact_id: "artifact-1", claim_id: null, issue: "incomplete_answer", comment: "Missing an explanation",
    status: "pending", version: 1, provider_mode: "demo", snapshot_sha256: "a".repeat(64), created_at: "2026-09-06T00:00:00Z", review: null, sample: null,
    snapshot: { run_id: "run-1", run_version: 9, space_id: 1, goal: "Explain evidence", provider_mode: "demo", scope: {}, scope_digest: "b".repeat(64),
      policy_id: null, policy_version: null, policy_fingerprint: null, artifact_id: "artifact-1", artifact_title: "Title",
      artifact_body: "Original answer", claim: null, evidence: [] } };
}
