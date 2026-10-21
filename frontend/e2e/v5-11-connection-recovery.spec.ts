import { expect, test, type Page } from "@playwright/test";

// Controlled transport fixtures exercise the real page and connection adapter.
// These checks do not represent real providers, Docker services, or answer quality.
const runId = "v511-connection-run";
const view = {
  schema_version: 1, id: runId, space_id: 7, goal: "检查短暂断线后的同任务恢复", requested_mode: "force_agent",
  effective_mode: "force_agent", status: "running", phase: "retrieve", version: 2, execution_epoch: 0,
  scope_snapshot: { space_id: 7, revisions: [] }, budget_limits: { max_steps: 8 }, budget_usage: {},
  cost_measurement: "unknown", provider_mode: "real", last_event_cursor: 0, final_artifact_id: null,
  termination_reason: null, outcome: null
};

function frame(cursor: number, type: string, runVersion: number, payload: unknown = {}) {
  return `id: ${cursor}\nevent: ${type}\ndata: ${JSON.stringify({
    schema_version: 1, cursor, run_version: runVersion, type, payload
  })}\n\n`;
}

async function prepare(page: Page, observe: (after: number) => string | null, initialView = view) {
  const observedAfter: number[] = [];
  const writes: string[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: {
      "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET,POST,OPTIONS"
    } });
    if (request.method() !== "GET") writes.push(`${request.method()} ${url.pathname}`);
    if (url.pathname === `/api/v1/evidence-runs/${runId}/stream`) {
      if (!url.searchParams.has("after")) return route.fulfill({ contentType: "text/event-stream",
        body: frame(0, "sync", initialView.version, { run: initialView }) });
      const after = Number(url.searchParams.get("after"));
      observedAfter.push(after);
      const body = observe(after);
      return body === null ? route.abort("failed") : route.fulfill({ contentType: "text/event-stream", body });
    }
    return route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ success: true, data: {}, error: null, request_id: "v511-controlled" }) });
  });
  return { observedAfter, writes };
}

test("temporary stream closure resumes the same run and deduplicates previously received events", async ({ page }) => {
  const transport = await prepare(page, (after) => after === 0
    ? frame(5, "run.running", 2)
    : frame(5, "run.running", 2) + frame(6, "run.completed", 3));
  await page.goto(`/runs/${runId}`);
  const status = page.getByTestId("run-connection-status");
  await expect(status).toContainText("事件已同步");
  await expect(status).toContainText("最后收到事件");
  await expect(page.getByTestId("run-timeline").getByRole("listitem")).toHaveCount(2);
  expect(transport.observedAfter).toEqual([0, 5]);
  expect(transport.writes).toEqual([]);
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}$`));
});

test("exhausted recovery explains stale progress and manual reconnect reads without replaying commands", async ({ page }) => {
  let networkRestored = false;
  const transport = await prepare(page, () => networkRestored ? frame(6, "run.completed", 3) : null);
  await page.goto(`/runs/${runId}`);
  const status = page.getByTestId("run-connection-status");
  await expect.poll(() => transport.observedAfter.length).toBe(4);
  await expect(status).toContainText("连接异常");
  await expect(status).toContainText("尚未收到事件");
  await expect(status).not.toContainText("事件已同步");
  networkRestored = true;
  await status.getByRole("button", { name: "重新连接" }).click();
  await expect(status).toContainText("事件已同步");
  expect(transport.observedAfter).toEqual([0, 0, 0, 0, 0]);
  expect(transport.writes).toEqual([]);
});

test("completed tasks keep a retry until their known final history cursor has been received", async ({ page }) => {
  let historyAvailable = false;
  const transport = await prepare(page, (after) => after === 0
    ? frame(6, "evidence.added", 8, { evidence_id: "historical-evidence" })
    : historyAvailable ? frame(12, "run.completed", 8) : "",
  { ...view, status: "completed", version: 8, last_event_cursor: 12 });
  await page.goto(`/runs/${runId}`);
  const status = page.getByTestId("run-connection-status");
  await expect.poll(() => transport.observedAfter.length).toBe(4);
  await expect(status).toContainText("连接已断开");
  await expect(status).not.toContainText("事件已同步");
  expect(transport.observedAfter).toEqual([0, 6, 6, 6]);
  historyAvailable = true;
  await status.getByRole("button", { name: "重新连接" }).click();
  await expect(status).toContainText("事件已同步");
  await expect(status.getByRole("button", { name: "重新连接" })).toHaveCount(0);
  expect(transport.observedAfter).toEqual([0, 6, 6, 6, 6]);
  expect(transport.writes).toEqual([]);
});

test("leaving the workspace cancels a pending observation retry", async ({ page }) => {
  await page.clock.install();
  const transport = await prepare(page, () => null);
  await page.goto(`/runs/${runId}`);
  await expect(page.getByTestId("run-connection-status")).toContainText("准备第 1 次重连");
  await page.getByRole("main").getByRole("link", { name: "运行记录", exact: true }).click();
  await expect(page).toHaveURL(/\/runs$/);
  // Advance the browser clock past all backoff delays without a real-time sleep.
  const readsAfterLeaving = transport.observedAfter.length;
  await page.clock.runFor(20_000);
  expect(transport.observedAfter).toHaveLength(readsAfterLeaving);
  expect(transport.writes).toEqual([]);
});
