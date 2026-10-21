import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const requestedTimeout = Number.parseInt(process.env.E2E_TEST_TIMEOUT_MS ?? "", 10);
const testTimeout = Number.isFinite(requestedTimeout) && requestedTimeout >= 30_000 ? requestedTimeout : 30_000;
const expectTimeout = Math.min(testTimeout, Math.max(5_000, Math.ceil(testTimeout / 2)));
const requestedWorkers = Number.parseInt(process.env.E2E_WORKERS ?? "", 10);
const workers = Number.isFinite(requestedWorkers) && requestedWorkers > 0 ? requestedWorkers : undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: testTimeout,
  expect: { timeout: expectTimeout },
  fullyParallel: true,
  workers,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  outputDir: "test-results",
  webServer: undefined,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
