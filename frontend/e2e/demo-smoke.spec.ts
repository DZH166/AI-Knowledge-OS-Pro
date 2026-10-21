import { expect, test } from "@playwright/test";

const routes = [
  { path: "/", marker: "body" },
  { path: "/dashboard", marker: "body" },
  { path: "/upload", marker: "body" },
  { path: "/tasks", marker: "body" },
  { path: "/chat", marker: "[data-testid='knowledge-chat']" },
  { path: "/media", marker: "body" },
  { path: "/media/sources/3?t=6000&chunk=6", marker: "[data-testid='media-detail-page']" },
  { path: "/learning", marker: "body" },
  { path: "/learning/cards", marker: "body" },
  { path: "/portfolio", marker: "body" },
  { path: "/portfolio/resume", marker: "body" },
  { path: "/portfolio/interview", marker: "body" },
  { path: "/system", marker: "body" },
  { path: "/system/observability", marker: "[data-testid='observability-page']" },
  { path: "/evaluations", marker: "[data-testid='evaluation-index-page']" },
  { path: "/policies", marker: "[data-testid='policy-lab-page']" },
  { path: "/policies/optimizer", marker: "[data-testid='optimizer-lab-page']" }
];

test.describe("portfolio demo smoke", () => {
  for (const route of routes) {
    test(`loads ${route.path}`, async ({ page }) => {
      const response = await page.goto(route.path);
      expect(response?.status(), `${route.path} should not return a server error`).toBeLessThan(500);
      await expect(page.locator(route.marker)).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Failed to fetch");
      await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
      await expect(page.locator("body")).not.toContainText("NEXT_PUBLIC_API_BASE_URL");
      await expect(page.locator("body")).not.toContainText("OPENAI_API_KEY");
    });
  }

  test("runs the seeded chat to citation surface", async ({ page }) => {
    await page.goto("/chat");
    await page.getByTestId("chat-question-input").fill("How does the system keep multimodal RAG answers traceable?");
    await page.getByTestId("chat-submit").click();
    await expect(page.getByTestId("chat-answer")).toContainText(/\[[0-9]+\]/, { timeout: 20_000 });
    await expect(page.getByTestId("citation-panel")).toBeVisible();
    await expect(page.getByTestId("citation-card").first()).toBeVisible();
  });
});
