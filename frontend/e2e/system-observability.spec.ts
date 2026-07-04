import { expect, test } from "@playwright/test";

test.describe("runtime observability", () => {
  test("observability page exposes request, task and provider sections", async ({ page }) => {
    const response = await page.goto("/system/observability");
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator("body")).toContainText("request_id");
    await expect(page.locator("body")).toContainText("retrieval_trace_id");
    await expect(page.locator("body")).toContainText(/provider|Provider|NOT_CONFIGURED/);
  });
});
