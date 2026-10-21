import { expect, test } from "@playwright/test";

test.describe("citation deep-link contracts", () => {
  test("document citation URL keeps page, heading and chunk locators", async ({ page }) => {
    await page.goto("/documents/1?page=2&heading=RAG&chunk=3");
    await expect(page).toHaveURL(/\/documents\/1\?page=2&heading=RAG&chunk=3/);
  });

  test("audio timestamp citation opens the player and highlights transcript evidence", async ({ page }) => {
    await page.goto("/media/sources/2?t=6000&chunk=3");
    await expect(page.getByTestId("media-detail-page")).toBeVisible();
    await expect(page.getByTestId("audio-player")).toBeVisible();
    await expect(page.getByTestId("transcript-timeline")).toBeVisible();
    await expect(page.locator("[data-testid='transcript-segment'][data-active='true']")).toContainText("Timestamp citations return");
  });

  test("video timestamp citation opens the player, keyframes and highlighted transcript evidence", async ({ page }) => {
    await page.goto("/media/sources/3?t=6000&chunk=6");
    await expect(page.getByTestId("media-detail-page")).toBeVisible();
    await expect(page.getByTestId("video-player")).toBeVisible();
    await expect(page.getByTestId("keyframe-timeline")).toBeVisible();
    await expect(page.getByTestId("keyframe-tile")).toHaveCount(3);
    await expect(page.locator("[data-testid='transcript-segment'][data-active='true']")).toContainText("Timestamp citations return");
  });

  test("image citation opens the source detail without provider fabrication", async ({ page }) => {
    await page.goto("/media/sources/1?chunk=1");
    await expect(page.getByTestId("media-detail-page")).toBeVisible();
    await expect(page.locator("body")).toContainText("Architecture");
    await expect(page.locator("body")).not.toContainText("fake OCR");
  });

  test("code citation URL keeps file and line locators", async ({ page }) => {
    await page.goto("/code?file=backend/app/api/router.py&line=1&line_end=31&source=4");
    await expect(page).toHaveURL(/\/code\?file=backend(%2F|\/)app(%2F|\/)api(%2F|\/)router.py&line=1&line_end=31&source=4/);
    await expect(page.locator("body")).toContainText(/line|引用|定位|backend\/app\/api\/router.py/i);
  });

  test("chat citation link navigates to a concrete source locator", async ({ page }) => {
    await page.goto("/chat");
    await page.locator("#session").selectOption({ label: "Traceable multimodal RAG" });
    await expect(page.getByTestId("citation-source-link").first()).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("citation-source-link").first().click();
    await expect(page).toHaveURL(/\/(media\/sources|documents|code)/);
    await expect(page.locator("body")).not.toContainText("Failed to fetch");
  });
});
