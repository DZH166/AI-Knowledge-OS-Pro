import { expect, test } from "@playwright/test";

test("a failed detail read keeps the question and retries the created run without another POST", async ({ page }) => {
  const respond = (data: unknown, status = 200) => ({
    status,
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify({ success: true, data, error: null, request_id: "browser-test" })
  });
  const posts: Array<{ request_id: string; goal: string }> = [];
  let detailReads = 0;
  await page.route("**/api/knowledge-spaces", (route) => route.fulfill(respond([
    { id: 7, name: "测试空间", description: "", created_at: "2026-09-23T00:00:00Z", updated_at: "2026-09-23T00:00:00Z" }
  ])));
  await page.route("**/api/media/sources", (route) => route.fulfill(respond([{
    id: 3, space_id: 7, source_type: "document", title: "资料.pdf", status: "active",
    active_revision_id: 4, latest_revision_id: 4, revisions: [], media_assets: []
  }])));
  await page.route("**/api/v1/evidence-runs", async (route) => {
    posts.push(route.request().postDataJSON());
    await route.fulfill(respond({
      schema_version: 1, command_id: "command-1", run_id: "run-retry-1",
      run_version: 1, status: "queued", cursor: 1, replayed: false
    }, 201));
  });
  await page.route("**/api/v1/evidence-runs/run-retry-1", async (route) => {
    detailReads += 1;
    if (detailReads === 1) {
      await route.fulfill({
        status: 503, contentType: "application/json", headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({ success: false, error: {
          code: "RUN_TEMPORARY_UNAVAILABLE", user_message: "任务已建成，详情暂时无法读取", retryable: true
        } })
      });
      return;
    }
    await route.fulfill(respond({
      schema_version: 1, id: "run-retry-1", space_id: 7, goal: "我的重要问题", requested_mode: "auto",
      effective_mode: null, status: "queued", phase: "route", version: 1, execution_epoch: 0,
      scope_snapshot: { space_id: 7, revisions: [] }, budget_limits: { max_steps: 8 },
      budget_usage: { steps: 0 }, cost_measurement: "unknown", provider_mode: "real",
      last_event_cursor: 1, final_artifact_id: null, termination_reason: null, outcome: null
    }));
  });

  await page.goto("/workbench");
  await expect(page.getByLabel("研究目标")).toHaveAttribute("maxlength", "4000");
  await page.getByLabel("研究目标").fill("我的重要问题");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("任务已建成，详情暂时无法读取");
  await expect(page.locator("form [role='alert']")).toContainText("RUN_TEMPORARY_UNAVAILABLE；可重试");
  await expect(page.getByLabel("研究目标")).toHaveValue("我的重要问题");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page).toHaveURL(/\/runs\/run-retry-1$/);
  expect(posts).toHaveLength(1);
  expect(posts[0].goal).toBe("我的重要问题");
  expect(detailReads).toBe(2);
});

test("an uncertain create response retries with the same request identity", async ({ page }) => {
  const respond = (data: unknown, status = 200) => ({
    status, contentType: "application/json", headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify({ success: true, data, error: null, request_id: "browser-test" })
  });
  const requestIds: string[] = [];
  await page.route("**/api/knowledge-spaces", (route) => route.fulfill(respond([{
    id: 7, name: "测试空间", created_at: "2026-09-23T00:00:00Z", updated_at: "2026-09-23T00:00:00Z"
  }])));
  await page.route("**/api/media/sources", (route) => route.fulfill(respond([{
    id: 3, space_id: 7, source_type: "document", title: "资料.pdf", status: "active",
    active_revision_id: 4, latest_revision_id: 4, revisions: [], media_assets: []
  }])));
  await page.route("**/api/v1/evidence-runs", async (route) => {
    requestIds.push(route.request().postDataJSON().request_id);
    if (requestIds.length === 1) {
      await route.abort("failed");
      return;
    }
    await route.fulfill(respond({
      schema_version: 1, command_id: "command-1", run_id: "run-retry-2",
      run_version: 1, status: "queued", cursor: 1, replayed: true
    }, 201));
  });
  await page.route("**/api/v1/evidence-runs/run-retry-2", (route) => route.fulfill(respond({
    schema_version: 1, id: "run-retry-2", space_id: 7, goal: "保持相同请求编号", requested_mode: "auto",
    effective_mode: null, status: "queued", phase: "route", version: 1, execution_epoch: 0,
    scope_snapshot: { space_id: 7, revisions: [] }, budget_limits: { max_steps: 8 },
    budget_usage: { steps: 0 }, cost_measurement: "unknown", provider_mode: "real",
    last_event_cursor: 1, final_artifact_id: null, termination_reason: null, outcome: null
  })));

  await page.goto("/workbench");
  await page.getByLabel("研究目标").fill("保持相同请求编号");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("网络连接失败，请检查网络和后端服务后重试。");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page).toHaveURL(/\/runs\/run-retry-2$/);
  expect(requestIds).toHaveLength(2);
  expect(requestIds[0]).toBe(requestIds[1]);
});
