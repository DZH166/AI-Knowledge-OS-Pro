import { expect, test } from "@playwright/test";

const respond = (data: unknown) => ({
  contentType: "application/json",
  headers: { "access-control-allow-origin": "*" },
  body: JSON.stringify({ success: true, data, error: null, request_id: "v5-9-browser" })
});

test("comparison needs three selected, usable documents", async ({ page }) => {
  await page.goto("/workbench?demo=1&scenario=compare&space_id=9001");
  await expect(page.getByRole("heading", { name: "用三份资料做一次可核对的对比" })).toBeVisible();
  const start = page.getByRole("button", { name: "开始对比研究" });
  await page.getByRole("checkbox", { name: "选择 Evidence Agent contract.pdf" }).check();
  await page.getByRole("checkbox", { name: "选择 Bounded Agent runtime.md" }).check();
  await expect(page.getByText("已选择 2 份")).toBeVisible();
  await expect(start).toBeDisabled();
  await page.getByRole("checkbox", { name: "选择 Human review workflow.md" }).check();
  await expect(page.getByText("已选择 3 份")).toBeVisible();
  await expect(start).toBeEnabled();
});

test("comparison upload stays in its space and does not show another space's documents", async ({ page }) => {
  const spaces = [7, 8].map((id) => ({ id, name: `空间 ${id}`, description: null,
    created_at: "2026-09-26T00:00:00Z", updated_at: "2026-09-26T00:00:00Z" }));
  await page.route("**/api/knowledge-spaces", (route) => route.fulfill(respond(spaces)));
  await page.route("**/api/documents", (route) => route.fulfill(respond([
    { id: 71, space_id: 7, original_filename: "当前空间资料.pdf", chunk_count: 5, processing_progress: 100 },
    { id: 81, space_id: 8, original_filename: "别的空间资料.pdf", chunk_count: 8, processing_progress: 100 }
  ])));
  await page.route("**/api/media/sources", (route) => route.fulfill(respond([])));
  await page.goto("/upload?space_id=7&scenario=compare");
  await expect(page.getByRole("combobox", { name: "本次研究的知识空间" })).toBeDisabled();
  await expect(page.getByText("当前空间资料.pdf")).toBeVisible();
  await expect(page.getByText("别的空间资料.pdf")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "返回三资料对比" }))
    .toHaveAttribute("href", "/workbench?scenario=compare&space_id=7");
});

test("successful feedback response shows a confirmation without treating it as automatic truth", async ({ page }) => {
  const artifact = {
    schema_version: 1, id: "artifact-v59", producing_run_id: "run-v59", kind: "comparison",
    title: "真实模式成果示例", body_markdown: "比较正文", status: "final",
    claims: [{ id: "claim-v59", ordinal: 1, text: "需要纠正的结论", kind: "factual",
      verification_status: "supported", evidence_ids: ["evidence-v59"] }]
  };
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/v1/artifacts/artifact-v59", (route) => route.fulfill(respond(artifact)));
  await page.route("**/api/v1/feedback", async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    const feedback = {
      id: 59, artifact_id: artifact.id, claim_id: "claim-v59", issue: submitted.issue,
      comment: submitted.comment, status: "pending", version: 1, provider_mode: "real",
      snapshot_sha256: "a".repeat(64), created_at: "2026-09-26T00:00:00Z", review: null, sample: null,
      snapshot: {
        run_id: "run-v59", run_version: 1, space_id: 7, goal: "比较三份资料",
        provider_mode: "real", scope: {}, scope_digest: "b".repeat(64),
        policy_id: null, policy_version: null, policy_fingerprint: null,
        artifact_id: artifact.id, artifact_title: artifact.title, artifact_body: artifact.body_markdown,
        claim: { id: "claim-v59", text: "需要纠正的结论", verification_status: "supported" },
        evidence: []
      }
    };
    await route.fulfill(respond({ feedback, replayed: false }));
  });
  await page.goto("/artifacts/artifact-v59");
  await page.getByRole("button", { name: "反馈这条结论" }).click();
  await page.getByRole("textbox", { name: "问题说明" }).fill("这条结论遗漏了边界条件");
  await page.getByRole("button", { name: "保存反馈" }).click();
  await expect(page.getByTestId("feedback-composer")).toContainText("反馈 #59 已保存");
  await expect(page.getByTestId("feedback-composer")).toContainText("待人工审阅");
  await expect(page.getByRole("link", { name: "查看并审阅反馈" }))
    .toHaveAttribute("href", "/evaluations/feedback?id=59");
  expect(submitted).toMatchObject({ artifact_id: "artifact-v59", claim_id: "claim-v59",
    comment: "这条结论遗漏了边界条件", issue: "incorrect_answer" });
});
