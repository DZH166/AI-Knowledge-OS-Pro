import { expect, test, type APIRequestContext, type Page } from "@playwright/test";


test.describe("V5.7 optimizer workbench", () => {
  test("retries a committed create after response loss without duplicating the Study", async ({ page }) => {
    let createdId = "";
    let attempts = 0;
    await page.route("**/api/v1/optimizer/studies/from-template", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      attempts += 1;
      if (attempts === 1) {
        const response = await route.fetch();
        createdId = (await response.json()).data.study_id;
        await route.abort("failed");
      } else await route.continue();
    });
    await page.goto("/policies/optimizer");
    await page.getByLabel("实验名称").fill("Response-loss retry audit");
    await page.getByRole("button", { name: "创建优化实验" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await page.getByRole("button", { name: "创建优化实验" }).click();
    await expect(page).toHaveURL(new RegExp(`/policies/optimizer/${createdId}$`));
    expect(attempts).toBe(2);
  });

  test("creates, evaluates, compares, converts, and shares durable facts", async ({ page, request }) => {
    test.setTimeout(240_000);
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBase, "strict V5.7 E2E must expose the backend origin").toBeTruthy();

    await page.goto("/policies");
    await page.getByRole("link", { name: "打开优化工作台" }).click();
    await expect(page.getByTestId("optimizer-lab-page")).toBeVisible();
    await page.getByLabel("实验模板").selectOption("cost_first");
    await page.getByLabel("实验名称").fill("V5.7 browser optimizer study");
    await page.getByLabel("候选总预算").fill("3");
    await page.getByLabel("评测总预算").fill("3");
    await page.getByRole("button", { name: "创建优化实验" }).click();
    await expect(page).toHaveURL(/\/policies\/optimizer\/[A-Za-z0-9_-]+$/);
    const studyId = page.url().split("/").at(-1)!;
    await expect(page.getByTestId("optimizer-study-page")).toBeVisible();

    await page.getByRole("button", { name: "启动实验" }).click();
    await expect(page.getByTestId("optimizer-study-page")).toHaveAttribute("data-study-status", "completed", { timeout: 150_000 });
    await expect(page.getByTestId("optimizer-study-page")).toBeVisible();
    await expect(page.getByText("推荐 #1")).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "通过率" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "证据召回" })).toBeVisible();

    const trialChecks = page.getByRole("checkbox", { name: /选择 Trial/ });
    await expect(trialChecks).toHaveCount(3);
    await trialChecks.nth(0).check();
    await trialChecks.nth(1).check();
    await trialChecks.nth(2).check();
    await page.getByRole("button", { name: "导出对比" }).click();
    await expect(page.getByText("delta vs trial 1", { exact: false })).toBeVisible();
    await expect(page.getByText("trial 2 vs trial 3", { exact: false }).first()).toBeVisible();

    const convertResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().includes("/convert-draft")
    );
    await page.getByRole("button", { name: "转为草稿" }).click();
    expect((await convertResponse).ok()).toBeTruthy();
    await expect(page.getByRole("link", { name: "打开已转换草稿" })).toBeVisible();

    const runId = await openTerminalRun(request, apiBase!);
    await page.goto(`/runs/${runId}/trace`);
    await expect(page.getByTestId("run-trace-page")).toBeVisible();
    const shareResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith(`/api/v1/agent-runs/${runId}/share`)
    );
    await page.getByRole("button", { name: "创建只读分享" }).click();
    const share = (await (await shareResponse).json()).data;
    await page.reload();
    await expect(page.getByTestId("run-share-panel")).toContainText(share.url_path);
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.getByRole("button", { name: "复制分享路径" }).click();
    await expect(page.getByText("分享路径已复制。", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(share.url_path);
    const shared = await request.get(`${apiBase}${share.url_path}`);
    expect(shared.ok()).toBeTruthy();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await page.getByRole("button", { name: "复制分享路径" }).focus();
    await expect(page.getByRole("button", { name: "复制分享路径" })).toBeFocused();
    await page.getByRole("button", { name: "撤销分享" }).click();
    await expect(page.getByTestId("run-share-panel")).toHaveCount(0);
    expect((await request.get(`${apiBase}${share.url_path}`)).status()).toBe(404);
    await page.goto(`/policies/optimizer/${studyId}`);
    await expect(page.getByTestId("optimizer-study-page")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  });

  test("keeps optimizer creation keyboard-operable at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/policies/optimizer");
    await expect(page.getByTestId("optimizer-lab-page")).toBeVisible();
    await focusByTab(page, "optimizer-label");
    await page.keyboard.press("Control+A");
    await page.keyboard.insertText("Keyboard optimizer study");
    await expect(page.getByLabel("实验名称")).toHaveValue("Keyboard optimizer study");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await expect(page.locator('.nav-item[aria-current="page"]')).toHaveCount(1);
  });
});


async function openTerminalRun(request: APIRequestContext, apiBase: string): Promise<string> {
  const spaces = await apiData(request, `${apiBase}/api/knowledge-spaces`);
  const opened = await request.post(`${apiBase}/api/v1/evidence-runs`, {
    data: {
      schema_version: 1,
      request_id: `v57-share-${crypto.randomUUID()}`,
      space_id: spaces[0].id,
      goal: "Create a read-only trace share.",
      scope: { source_ids: [] },
      deliverable: { kind: "answer", title: "V5.7 shared trace" },
      mode: "force_quick",
      permissions: { read_only: true, allow_scope_expansion: false },
      provider_mode: "demo"
    }
  });
  expect(opened.status()).toBe(201);
  const runId = (await opened.json()).data.run_id;
  await expect.poll(async () => {
    const run = await apiData(request, `${apiBase}/api/v1/evidence-runs/${runId}`);
    return ["completed", "insufficient_evidence", "failed", "cancelled"].includes(run.status) ? "terminal" : run.status;
  }, { timeout: 90_000 }).toBe("terminal");
  return runId;
}

async function focusByTab(page: Page, id: string): Promise<void> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await page.keyboard.press("Tab");
    if (await page.evaluate((target) => (document.activeElement as HTMLElement | null)?.id === target, id)) return;
  }
  throw new Error(`Keyboard navigation did not reach #${id}.`);
}

async function apiData(request: APIRequestContext, url: string) {
  const response = await request.get(url);
  expect(response.ok(), `${url} should return success`).toBeTruthy();
  return (await response.json()).data;
}
