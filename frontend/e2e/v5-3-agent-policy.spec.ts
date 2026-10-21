import { expect, test, type APIRequestContext, type Page } from "@playwright/test";


const DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001";

test.describe("V5.3 adaptive policy lab", () => {
  test("creates, simulates, evaluates, activates, pins, and rolls back a policy", async ({ page, request }) => {
    test.setTimeout(180_000);
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBase, "strict V5.3 E2E must expose the backend origin").toBeTruthy();
    const runId = await openTerminalRun(request, apiBase!);

    await page.goto("/policies");
    await expect(page.getByTestId("policy-lab-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "先评测，再让新策略影响任务" })).toBeVisible();
    await expect(page.locator('.nav-item[aria-current="page"]')).toHaveCount(1);
    await page.getByLabel("候选策略名称").fill("V5.3 browser candidate");
    await page.getByLabel("事实型 Top-K").fill("9");
    await page.getByLabel("向前相邻片段").fill("2");
    await page.getByRole("button", { name: "创建策略草稿" }).click();
    await expect(page).toHaveURL(/\/policies\/[A-Za-z0-9_-]+$/);
    const policyId = page.url().split("/").at(-1)!;

    await expect(page.getByTestId("policy-detail-page")).toBeVisible();
    await expect(page.getByText("策略字段差异")).toBeVisible();
    await page.getByLabel("选择已结束的 Run").selectOption(runId);
    await page.getByRole("button", { name: "模拟这个策略" }).click();
    await expect(page.getByTestId("policy-simulation")).toContainText("改变的决策");
    await expect(page.getByTestId("policy-simulation")).toContainText("no model, retrieval");

    await page.getByRole("button", { name: "运行固定 60 场景评测" }).click();
    await expect(page.getByText("已有通过评测，可以启用。")).toBeVisible({ timeout: 90_000 });
    const activationResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith(`/api/v1/agent-policies/${policyId}/activate`)
    );
    await page.getByRole("button", { name: "启用已通过评测的策略" }).click();
    expect((await activationResponse).ok()).toBeTruthy();
    await expect(page.getByRole("button", { name: "启用已通过评测的策略" })).toHaveCount(0);
    const activeCandidate = await apiData(request, `${apiBase}/api/v1/agent-policies/active`);
    expect(activeCandidate.id).toBe(policyId);

    const spaces = await apiData(request, `${apiBase}/api/knowledge-spaces`);
    const pinnedRun = await request.post(`${apiBase}/api/v1/evidence-runs`, {
      data: {
        schema_version: 1,
        request_id: `v53-policy-pin-${crypto.randomUUID()}`,
        space_id: spaces[0].id,
        goal: "Show which policy this run pins.",
        scope: { source_ids: [] },
        deliverable: { kind: "answer", title: "V5.3 policy pin" },
        mode: "force_quick",
        permissions: { read_only: true, allow_scope_expansion: false },
        provider_mode: "demo"
      }
    });
    expect(pinnedRun.status()).toBe(201);
    const pinnedRunId = (await pinnedRun.json()).data.run_id;
    await expect.poll(async () => {
      const view = await apiData(request, `${apiBase}/api/v1/evidence-runs/${pinnedRunId}`);
      return ["completed", "insufficient_evidence", "failed", "cancelled"].includes(view.status)
        ? "terminal"
        : view.status;
    }, { timeout: 60_000 }).toBe("terminal");
    const pinnedView = await apiData(request, `${apiBase}/api/v1/evidence-runs/${pinnedRunId}`);
    expect(pinnedView.decision_policy).toMatchObject({
      id: policyId,
      version: activeCandidate.version,
      config_sha256: activeCandidate.config_sha256
    });
    await page.goto(`/runs/${pinnedRunId}/trace`);
    await expect(page.getByTestId("run-trace-page")).toBeVisible();
    await expect(page.getByText(`SHA-256 ${activeCandidate.config_sha256}`)).toBeVisible();
    const adaptiveFacts = page.locator("details").filter({ hasText: "retrieval_policy.top_k=9" });
    await adaptiveFacts.locator("summary").click();
    await expect(page.getByText("retrieval_policy.top_k=9")).toBeVisible();

    await page.goto(`/policies/${DEFAULT_POLICY_ID}`);
    await expect(page.getByRole("button", { name: "回滚到这个历史策略" })).toBeEnabled();
    const rollbackResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith(`/api/v1/agent-policies/${DEFAULT_POLICY_ID}/rollback`)
    );
    await page.getByRole("button", { name: "回滚到这个历史策略" }).click();
    expect((await rollbackResponse).ok()).toBeTruthy();
    await expect(page.getByRole("button", { name: "回滚到这个历史策略" })).toHaveCount(0);
    const rolledBack = await apiData(request, `${apiBase}/api/v1/agent-policies/active`);
    expect(rolledBack.id).toBe(DEFAULT_POLICY_ID);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/policies");
    await expect(page.getByTestId("policy-lab-page")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await expect(page.locator('.nav-item[aria-current="page"]')).toHaveCount(1);
  });

  test("creates a bounded draft with keyboard only at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/policies");
    await expect(page.getByTestId("policy-lab-page")).toBeVisible();
    await focusByTab(page, (active) => active.id === "policy-label");
    await page.keyboard.press("Control+A");
    await page.keyboard.insertText("V5.3 keyboard candidate");
    await focusByTab(page, (active) => active.text === "创建策略草稿");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/policies\/[A-Za-z0-9_-]+$/);
    await expect(page.getByTestId("policy-detail-page")).toBeVisible();
  });

  test("shows a production error without falling back to a demo policy", async ({ page }) => {
    await page.route("**/api/v1/agent-policies/active", async (route) => route.fulfill({
      status: 500,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: false, data: null, error: { code: "POLICY_FAILED", message: "policy unavailable" }, request_id: "policy-error" })
    }));
    await page.goto("/policies");
    await expect(page.getByRole("heading", { name: "无法打开策略实验室" })).toBeVisible();
    await expect(page.getByText(/不会显示演示策略/)).toBeVisible();
    await expect(page.getByText("Balanced evidence retrieval")).toHaveCount(0);
  });
});


async function openTerminalRun(request: APIRequestContext, apiBase: string): Promise<string> {
  const spaces = await apiData(request, `${apiBase}/api/knowledge-spaces`);
  const opened = await request.post(`${apiBase}/api/v1/evidence-runs`, {
    data: {
      schema_version: 1,
      request_id: `v53-policy-simulation-${crypto.randomUUID()}`,
      space_id: spaces[0].id,
      goal: "Explain immutable evidence for policy simulation.",
      scope: { source_ids: [] },
      deliverable: { kind: "answer", title: "V5.3 simulation run" },
      mode: "force_quick",
      permissions: { read_only: true, allow_scope_expansion: false },
      provider_mode: "demo"
    }
  });
  expect(opened.status()).toBe(201);
  const runId = (await opened.json()).data.run_id;
  await expect.poll(async () => {
    const view = await apiData(request, `${apiBase}/api/v1/evidence-runs/${runId}`);
    return ["completed", "insufficient_evidence", "failed", "cancelled"].includes(view.status)
      ? "terminal"
      : view.status;
  }, { timeout: 60_000 }).toBe("terminal");
  return runId;
}

async function apiData(request: APIRequestContext, url: string) {
  const response = await request.get(url);
  expect(response.ok(), `${url} should return success`).toBeTruthy();
  return (await response.json()).data;
}

async function focusByTab(
  page: Page,
  matches: (active: { id: string; text: string }) => boolean
): Promise<void> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate(() => ({
      id: (document.activeElement as HTMLElement | null)?.id ?? "",
      text: (document.activeElement as HTMLElement | null)?.textContent?.trim() ?? ""
    }));
    if (matches(active)) return;
  }
  throw new Error("Keyboard navigation did not reach the expected Policy Lab control.");
}
