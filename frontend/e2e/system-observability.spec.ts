import { expect, test } from "@playwright/test";

test.describe("runtime observability", () => {
  test("observability page exposes request, task, retrieval and provider sections", async ({ page }) => {
    await page.goto("/dashboard");
    await page.goto("/tasks");
    await page.goto("/chat");
    const response = await page.goto("/system/observability");

    expect(response?.status()).toBeLessThan(500);
    await expect(page.getByTestId("observability-page")).toBeVisible();
    await expect(page.getByTestId("observability-requests")).toContainText("request_id", { timeout: 20_000 });
    await expect(page.getByTestId("observability-tasks")).toContainText(/task|任务|stage/i, { timeout: 20_000 });
    await expect(page.getByTestId("observability-retrievals")).toContainText(/retrieval_trace_id|暂无|检索/i, { timeout: 20_000 });
    await expect(page.getByTestId("observability-providers")).toContainText(/provider|Provider|NOT_CONFIGURED|not_configured/i, { timeout: 20_000 });
    await expect(page.getByTestId("observability-errors")).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("body")).not.toContainText("OPENAI_API_KEY");
    await expect(page.locator("body")).not.toContainText("Traceback");
  });
});
