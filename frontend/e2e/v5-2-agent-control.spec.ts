import { expect, test, type APIRequestContext } from "@playwright/test";


test.describe("V5.2 Agent evaluation and control center", () => {
  test("runs two fixed evaluations through Redis/RQ, opens detail, and compares stable snapshots", async ({ page, request }) => {
    test.setTimeout(180_000);
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBase, "strict V5.2 E2E must expose the backend origin").toBeTruthy();

    const left = await startAndWaitEvaluation(request, apiBase!, "V5.2 browser baseline");
    const right = await startAndWaitEvaluation(request, apiBase!, "V5.2 browser rerun");
    expect(left.summary.case_count).toBe(60);
    expect(left.summary.external_provider_calls).toBe(0);
    expect(right.summary.case_count).toBe(60);
    expect(right.summary.external_provider_calls).toBe(0);

    await page.goto(`/evaluations/${left.summary.id}`);
    await expect(page.getByTestId("evaluation-detail-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "V5.2 browser baseline" })).toBeVisible();
    await expect(page.getByText("60 个固定案例")).toBeVisible();
    await expect(page.getByText(/not a real-model quality benchmark/i)).toBeVisible();
    await expect(page.getByTestId("evaluation-gates")).toContainText("通过");
    await expect(page.locator("body")).not.toContainText("OPENAI_API_KEY");

    await page.goto("/evaluations");
    await expect(page.getByRole("heading", { name: "每次升级，先证明没有退步" })).toBeVisible();
    await expect(page.locator('.nav-item[aria-current="page"]')).toHaveCount(1);
    await page.getByLabel("基线快照").selectOption(left.summary.id);
    await expect(page).toHaveURL(new RegExp(`left=${left.summary.id}`));
    await page.getByLabel("修改后快照").selectOption(right.summary.id);
    await expect(page).toHaveURL(new RegExp(`right=${right.summary.id}`));
    await page.getByRole("button", { name: "开始比较" }).click();
    await expect(page.getByTestId("evaluation-comparison")).toContainText("表现稳定");
    await expect(page.getByTestId("evaluation-comparison")).toContainText("两个快照可以直接比较");
  });

  test("opens a terminal production Agent trace without replaying tools or exposing private fields", async ({ page, request }) => {
    test.setTimeout(90_000);
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBase).toBeTruthy();
    const spaces = (await (await request.get(`${apiBase}/api/knowledge-spaces`)).json()).data;
    const open = await request.post(`${apiBase}/api/v1/evidence-runs`, {
      data: {
        schema_version: 1,
        request_id: `v52-trace-${crypto.randomUUID()}`,
        space_id: spaces[0].id,
        goal: "Explain how immutable evidence keeps this answer traceable.",
        scope: { source_ids: [] },
        deliverable: { kind: "answer", title: "V5.2 trace evidence" },
        mode: "force_quick",
        permissions: { read_only: true, allow_scope_expansion: false },
        provider_mode: "demo"
      }
    });
    expect(open.status()).toBe(201);
    const runId = (await open.json()).data.run_id;
    let finalStatus = "";
    await expect.poll(async () => {
      const response = await request.get(`${apiBase}/api/v1/evidence-runs/${runId}`);
      if (!response.ok()) return `http-${response.status()}`;
      finalStatus = (await response.json()).data.status;
      return ["completed", "insufficient_evidence"].includes(finalStatus) ? "terminal" : finalStatus;
    }, { timeout: 60_000 }).toBe("terminal");

    const traceResponse = await request.get(`${apiBase}/api/v1/evidence-runs/${runId}/trace`);
    expect(traceResponse.ok()).toBeTruthy();
    const trace = (await traceResponse.json()).data;
    expect(trace.replay).toMatchObject({
      sequence_contiguous: true,
      trace_id_consistent: true,
      stored_state_matches: true,
      stored_terminal_state: finalStatus,
      replayed_terminal_state: finalStatus
    });
    const serialized = JSON.stringify(trace);
    expect(serialized).not.toContain("payload_json");
    expect(serialized).not.toContain("arguments_json");
    expect(serialized).not.toContain("state_json");
    expect(serialized).not.toContain("prompt");

    await page.goto(`/runs/${runId}/trace`);
    await expect(page.getByTestId("run-trace-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "这次研究是怎么跑出来的" })).toBeVisible();
    await expect(page.getByText("重放结果与数据库终态一致")).toBeVisible();
    await expect(page.getByTestId("run-trace-timeline")).toContainText("按顺序发生的事件");
    await expect(page.locator("body")).not.toContainText("private prompt");
  });

  test("keeps redaction, errors, keyboard navigation, and mobile layout honest", async ({ page }) => {
    const trace = mockedTrace();
    await page.route("**/api/v1/evidence-runs/run-mocked/trace", async (route) => route.fulfill(envelope(trace, "trace-mocked")));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/runs/run-mocked/trace");
    await expect(page.getByTestId("redacted-event")).toContainText("私有事件已脱敏");
    await expect(page.locator("body")).not.toContainText("private prompt");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();

    await page.route("**/api/v1/agent-evaluations?limit=100", async (route) => route.fulfill(envelope({ schema_version: 1, items: [] }, "evaluations-empty")));
    await page.route("**/api/v1/agent-evaluations?status=passed&limit=100", async (route) => route.fulfill(envelope({ schema_version: 1, items: [] }, "evaluations-passed-empty")));
    await page.goto("/evaluations");
    await expect(page.getByLabel("这次评测叫什么")).toBeVisible();
    await expect(page.getByRole("button", { name: "运行固定评测" })).toBeEnabled();
    await expect(page.getByLabel("按状态筛选")).toBeVisible();
    await page.getByLabel("按状态筛选").selectOption("passed");
    await expect(page).toHaveURL(/status=passed/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);

    await page.route("**/api/v1/evidence-runs/run-error/trace", async (route) => route.fulfill({
      status: 500,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: false, data: null, error: { code: "TRACE_FAILED", message: "trace unavailable" }, request_id: "trace-error" })
    }));
    await page.goto("/runs/run-error/trace");
    await expect(page.getByRole("heading", { name: "无法打开运行轨迹" })).toBeVisible();
    await expect(page.getByText(/不会用演示轨迹替代生产数据/)).toBeVisible();
    await expect(page.getByText("Mocked trace goal")).toHaveCount(0);
  });
});


async function startAndWaitEvaluation(request: APIRequestContext, apiBase: string, label: string) {
  const response = await request.post(`${apiBase}/api/v1/agent-evaluations`, {
    data: { schema_version: 1, request_id: `v52-evaluation-${crypto.randomUUID()}`, label }
  });
  expect(response.status()).toBe(201);
  const evaluationId = (await response.json()).data.evaluation_id;
  let detail: {
    summary: {
      id: string;
      status: string;
      case_count: number;
      external_provider_calls: number;
      failure_case_count: number;
    };
  } | undefined;
  await expect.poll(async () => {
    const current = await request.get(`${apiBase}/api/v1/agent-evaluations/${evaluationId}`);
    if (!current.ok()) return `http-${current.status()}`;
    detail = (await current.json()).data;
    return detail?.summary?.status;
  }, { timeout: 90_000, intervals: [250, 500, 1000] }).toBe("passed");
  return detail!;
}

function envelope(data: unknown, requestId: string) {
  return {
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify({ success: true, data, error: null, request_id: requestId })
  };
}

function mockedTrace() {
  return {
    schema_version: 1,
    run_id: "run-mocked",
    trace_id: "trace-mocked",
    goal: "Mocked trace goal",
    requested_mode: "force_agent",
    effective_mode: "force_agent",
    status: "running",
    phase: "plan",
    provider_mode: "demo",
    created_at: "2026-08-27T10:00:00Z",
    started_at: "2026-08-27T10:00:00Z",
    finished_at: null,
    active_elapsed_ms: 100,
    budget_limits: { max_steps: 8 },
    budget_usage: { steps: 1 },
    events: [
      { sequence: 1, run_version: 1, event_type: "run.opened", visibility: "public", redacted: false, facts: ["status=queued"], elapsed_ms: 0, delta_ms: 0, step_id: null, tool_call_id: null },
      { sequence: 2, run_version: 2, event_type: "model.started", visibility: "private", redacted: true, facts: [], elapsed_ms: 100, delta_ms: 100, step_id: null, tool_call_id: null }
    ],
    tool_calls: [],
    model_calls: [],
    policies: [],
    replay: {
      digest: "d".repeat(64), sequence_contiguous: true, trace_id_consistent: true,
      stored_terminal_state: "running", replayed_terminal_state: null, stored_state_matches: true,
      event_count: 2, redacted_event_count: 1, checkpoint_count: 0, latest_checkpoint_checksum: null
    },
    triage: { category: "none", summary: "没有执行故障。", retryable: false, supporting_facts: ["status=running"], suggested_action: "无需处理。" },
    warnings: []
  };
}
