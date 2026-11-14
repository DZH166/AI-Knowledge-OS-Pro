import { expect, test } from "@playwright/test";

const routes = [
  "/workbench",
  "/runs",
  "/library",
  "/artifacts",
  "/upload",
  "/tasks",
  "/learning",
  "/chat",
  "/media",
  "/system",
  "/evaluations",
  "/policies"
];

test.describe("accessible page shell", () => {
  for (const route of routes) {
    test(`${route} keeps one heading, named controls and no horizontal overflow`, async ({ page }) => {
      await page.goto(route, { waitUntil: "networkidle" });

      await expect(page.locator("h1")).toHaveCount(1);

      const unnamedButtons = await page.locator("button").evaluateAll((buttons) =>
        buttons
          .filter((button) => {
            const element = button as HTMLButtonElement;
            const label = (element.getAttribute("aria-label") || element.textContent || "").trim();
            return !label && !element.getAttribute("title");
          })
          .map((button) => button.outerHTML.slice(0, 120))
      );
      expect(unnamedButtons).toEqual([]);

      const imagesWithoutAlt = await page.locator("img").evaluateAll((images) =>
        images.filter((image) => !image.getAttribute("alt")).map((image) => image.outerHTML.slice(0, 120))
      );
      expect(imagesWithoutAlt).toEqual([]);

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      );
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }
});
