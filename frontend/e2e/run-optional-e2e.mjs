import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";

const require = createRequire(import.meta.url);

function resolvePlaywrightCli() {
  for (const target of ["@playwright/test/cli", "@playwright/test/cli.js"]) {
    try {
      return require.resolve(target);
    } catch {
      // Try the next known CLI entry.
    }
  }
  return null;
}

const cli = resolvePlaywrightCli();
if (!cli) {
  console.log("e2e_status=skipped reason=PLAYWRIGHT_NOT_INSTALLED");
  console.log("hint=Install @playwright/test and browser binaries to run live browser E2E.");
  process.exit(0);
}

const result = spawnSync(process.execPath, [cli, "test", "--config=playwright.config.ts"], {
  cwd: new URL("..", import.meta.url),
  env: process.env,
  encoding: "utf-8",
  stdio: "pipe"
});

const output = `${result.stdout || ""}\n${result.stderr || ""}`;
process.stdout.write(result.stdout || "");
process.stderr.write(result.stderr || "");

if (result.status !== 0 && /Executable doesn't exist|playwright install|browser.*not.*installed/i.test(output)) {
  console.log("e2e_status=skipped reason=PLAYWRIGHT_BROWSER_NOT_INSTALLED");
  console.log("hint=Run npx playwright install before requiring browser E2E as a hard gate.");
  process.exit(0);
}

process.exit(result.status ?? 1);
