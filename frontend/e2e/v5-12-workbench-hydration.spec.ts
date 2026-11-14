import { expect, test } from "@playwright/test";

test("research question becomes editable only after the initial draft is restored", async ({ page }) => {
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path === "/api/system/status" ? {
      llm: { ok: true, status: "configured" }, embedding: { ok: true, status: "configured" },
      qdrant: { ok: true, status: "ready" }, redis: { ok: true, status: "ready" }
    } : [];
    return route.fulfill({ contentType: "application/json",
      body: JSON.stringify({ success: true, data, error: null, request_id: "v512-hydration" }) });
  });

  let releaseScripts: () => void = () => {};
  const scriptsHeld = new Promise<void>((resolve) => { releaseScripts = resolve; });
  let holdScripts = true;
  await page.route("**/_next/static/**", async (route) => {
    if (holdScripts && route.request().resourceType() === "script") await scriptsHeld;
    await route.continue();
  });

  const goal = page.getByLabel("研究目标");
  try {
    await page.goto("/workbench?scenario=compare", { waitUntil: "commit" });
    await expect(goal).toBeVisible();
    // The server-rendered form must not accept edits while its defaults can
    // still be replaced by React hydration and saved-draft restoration.
    expect(await goal.isDisabled()).toBe(true);
    await page.locator("details").filter({ hasText: "来源与运行设置" }).locator("summary").click();
    await expect(page.getByLabel("交付物")).toBeDisabled();
    await expect(page.getByLabel("执行模式")).toBeDisabled();
    await expect(page.getByLabel("预算上限")).toBeDisabled();
    await expect(page.getByRole("checkbox", { name: /使用演示模式/ })).toBeDisabled();
    await expect(page.getByRole("button", { name: "清除草稿" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "开始三资料对比" })).toBeDisabled();
  } finally {
    holdScripts = false;
    releaseScripts();
  }

  await expect(goal).toBeEnabled();
  await goal.fill("比较三个方案的实际部署风险");
  await page.getByLabel("比较维度").fill("人力成本、数据迁移、长期维护");
  await page.getByLabel("预算上限").selectOption("deep");
  await page.getByRole("heading", { name: "研究工作台" }).click();
  await page.reload();
  await expect(goal).toBeEnabled();
  await expect(goal).toHaveValue("比较三个方案的实际部署风险");
  await expect(page.getByLabel("比较维度")).toHaveValue("人力成本、数据迁移、长期维护");
  await expect(page.getByLabel("预算上限")).toHaveValue("deep");
});
