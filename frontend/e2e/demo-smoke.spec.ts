import { expect, test } from "@playwright/test";

const routes = [
  "/",
  "/dashboard",
  "/upload",
  "/tasks",
  "/chat",
  "/media",
  "/learning",
  "/portfolio",
  "/portfolio/resume",
  "/portfolio/interview",
  "/system",
  "/system/observability"
];

test.describe("portfolio demo smoke", () => {
  for (const route of routes) {
    test(`loads ${route}`, async ({ page }) => {
      const response = await page.goto(route);
      expect(response?.status(), `${route} should not return a server error`).toBeLessThan(500);
      await expect(page.locator("body")).not.toContainText("Failed to fetch");
      await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
      await expect(page.locator("body")).not.toContainText("NEXT_PUBLIC_API_BASE_URL");
    });
  }
});
