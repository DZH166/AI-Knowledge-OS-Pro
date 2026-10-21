import { expect, test, type APIRequestContext } from "@playwright/test";

async function artifact(request: APIRequestContext) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  expect(base).toBeTruthy();
  const spaces = (await (await request.get(`${base}/api/knowledge-spaces`)).json()).data;
  const response = await request.post(`${base}/api/v1/evidence-runs`, { data: {
    schema_version: 1, request_id: `feedback-${crypto.randomUUID()}`, space_id: spaces[0].id,
    goal: "How does the system keep multimodal RAG answers traceable?", scope: { source_ids: [] },
    deliverable: { kind: "answer", title: "Feedback browser source" }, mode: "force_quick",
    permissions: { read_only: true, allow_scope_expansion: false }, provider_mode: "demo"
  } });
  expect(response.status()).toBe(201);
  const runId = (await response.json()).data.run_id;
  await expect.poll(async () => (await (await request.get(`${base}/api/v1/evidence-runs/${runId}`)).json()).data.status,
    { timeout: 120_000 }).toBe("completed");
  const run = (await (await request.get(`${base}/api/v1/evidence-runs/${runId}`)).json()).data;
  return { base, artifactId: run.outcome.artifact_id };
}

test("feedback survives response loss, review failure retry, refresh and a verified sample export", async ({ page, request }) => {
  test.setTimeout(240_000);
  const { artifactId } = await artifact(request);
  let savedId = 0;
  let createAttempts = 0;
  await page.route("**/api/v1/feedback", async route => {
    if (route.request().method() !== "POST") return route.continue();
    createAttempts += 1;
    if (createAttempts === 1) {
      const response = await route.fetch();
      savedId = (await response.json()).data.feedback.id;
      return route.abort("failed");
    }
    return route.continue();
  });
  await page.goto(`/artifacts/${artifactId}`);
  await page.getByRole("button", { name: "反馈这条结论" }).first().click();
  await page.getByLabel("问题说明").fill("This explanation needs a concrete traceability example.");
  await page.getByRole("button", { name: "保存反馈" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("问题说明")).toHaveValue("This explanation needs a concrete traceability example.");
  await page.getByRole("button", { name: "保存反馈" }).click();
  await expect(page.getByTestId("feedback-composer")).toContainText(`反馈 #${savedId} 已保存`);
  expect(createAttempts).toBe(2);
  await page.getByRole("link", { name: "查看并审阅反馈" }).click();
  await expect(page.getByTestId("feedback-workbench")).toBeVisible();
  let reviewAttempts = 0;
  const reviewRequestIds: string[] = [];
  await page.route(`**/api/v1/feedback/${savedId}/review`, async route => {
    reviewAttempts += 1;
    reviewRequestIds.push(route.request().postDataJSON().request_id);
    if (reviewAttempts === 1) return route.fulfill({ status: 503, contentType: "application/json",
      body: JSON.stringify({ success: false, error: { user_message: "暂时无法保存审阅，请重试。" } }) });
    return route.continue();
  });
  await page.getByLabel("审阅理由").fill("Checked source revision and citation identity.");
  await page.getByLabel("人工参考答案").fill("Explain the exact source revision and chunk identity.");
  await page.getByLabel("验收要求").fill("Include the fixed source revision without claiming a model quality benchmark.");
  await page.getByLabel("样例用途").selectOption("holdout");
  await page.getByRole("button", { name: "接受并生成样例" }).click();
  await expect(page.getByTestId("feedback-workbench").getByRole("alert")).toContainText("暂时无法保存审阅");
  await expect(page.getByLabel("审阅理由")).toHaveValue("Checked source revision and citation identity.");
  await page.getByRole("button", { name: "接受并生成样例" }).click();
  await expect(page.getByRole("heading", { name: `反馈 #${savedId} · 已接受` })).toBeVisible();
  expect(reviewAttempts).toBe(2);
  expect(new Set(reviewRequestIds).size).toBe(1);
  await page.reload();
  await expect(page.getByRole("heading", { name: "留出测试样例", exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: `选择样例 #${savedId} · 留出测试样例`, exact: true }).check();
  await page.getByRole("checkbox", { name: /我知道导出包含/ }).check();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出所选样例" }).click();
  expect((await download).suggestedFilename()).toBe("feedback-holdout-demo.json");
  await expect(page.getByText("已校验并导出 1 个留出测试样例。", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});

test("whole-artifact feedback can be rejected with keyboard and never becomes a sample", async ({ page, request }) => {
  test.setTimeout(180_000);
  const { artifactId, base } = await artifact(request);
  await page.goto(`/artifacts/${artifactId}`);
  await page.getByRole("button", { name: "反馈这份成果" }).click();
  await expect(page.getByLabel("问题说明")).toBeFocused();
  await page.keyboard.insertText("A reviewable whole-artifact report.");
  await page.getByRole("button", { name: "保存反馈" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("link", { name: "查看并审阅反馈" }).click();
  await expect(page).toHaveURL(/\/evaluations\/feedback\?id=[1-9]\d*$/);
  const id = Number(new URL(page.url()).searchParams.get("id"));
  await page.getByLabel("审阅决定").selectOption("rejected");
  await page.getByLabel("审阅理由").fill("The original answer is supported by the pinned source.");
  await page.getByRole("button", { name: "确认驳回" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: `反馈 #${id} · 已驳回` })).toBeVisible();
  await page.reload();
  expect((await (await request.get(`${base}/api/v1/feedback/${id}`)).json()).data.sample).toBeNull();
});

test("exporting an accepted sample preserves another feedback's unfinished review", async ({ page, request }) => {
  test.setTimeout(180_000);
  const { artifactId, base } = await artifact(request);
  const create = async (comment: string) => {
    const response = await request.post(`${base}/api/v1/feedback`, { data: {
      request_id: crypto.randomUUID(), artifact_id: artifactId, claim_id: null, issue: "incomplete_answer", comment
    } });
    expect(response.status()).toBe(201);
    return (await response.json()).data.feedback.id;
  };
  const acceptedId = await create("An accepted case for export.");
  const reviewed = await request.post(`${base}/api/v1/feedback/${acceptedId}/review`, { data: {
    request_id: crypto.randomUUID(), expected_version: 1, decision: "accepted", reason: "Reviewed source",
    expected_answer: "Citations should retain revisions.", acceptance_criteria: "Cite source revisions.", split: "tuning", reference_evidence_ids: []
  } });
  expect(reviewed.ok()).toBeTruthy();
  const pendingId = await create("Keep my review while exporting.");
  await page.goto(`/evaluations/feedback?id=${pendingId}`);
  await page.getByLabel("审阅理由").fill("Do not discard this unfinished review.");
  await page.getByLabel("人工参考答案").fill("An unsaved reference answer.");
  await page.getByRole("checkbox", { name: `选择样例 #${acceptedId} · 调参样例`, exact: true }).check();
  await page.getByRole("checkbox", { name: /我知道导出包含/ }).check();
  await page.getByRole("button", { name: "导出所选样例" }).click();
  await expect(page.getByText("已校验并导出 1 个调参样例。", { exact: true })).toBeVisible();
  await expect(page.getByLabel("审阅理由")).toHaveValue("Do not discard this unfinished review.");
  await expect(page.getByLabel("人工参考答案")).toHaveValue("An unsaved reference answer.");
});
