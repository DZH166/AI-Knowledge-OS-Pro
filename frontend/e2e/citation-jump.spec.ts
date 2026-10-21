import { expect, test } from "@playwright/test";

test.describe("citation deep-link contracts", () => {
  test("document citation URL keeps page, heading and chunk locators", async ({ page }) => {
    await page.goto("/documents/1?page=2&heading=RAG&chunk=3");
    await expect(page).toHaveURL(/\/documents\/1\?page=2&heading=RAG&chunk=3/);
  });

  test("media citation URL keeps timestamp and chunk locators", async ({ page }) => {
    await page.goto("/media/sources/1?t=12&chunk=7");
    await expect(page).toHaveURL(/\/media\/sources\/1\?t=12&chunk=7/);
  });

  test("code citation URL keeps file and line locators", async ({ page }) => {
    await page.goto("/code?file=backend/app/main.py&line=1&line_end=5&source=1");
    await expect(page).toHaveURL(/\/code\?file=backend%2Fapp%2Fmain.py&line=1&line_end=5&source=1/);
    await expect(page.locator("body")).toContainText(/line|引用|定位/i);
  });
});
