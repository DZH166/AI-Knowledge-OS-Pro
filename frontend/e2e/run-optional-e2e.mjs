import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const strict = process.argv.includes("--strict");
const passthroughArgs = process.argv.slice(2).filter((argument) => argument !== "--strict");
const frontendDir = fileURLToPath(new URL("..", import.meta.url));

function stopForMissingRuntime(reason, hint) {
  console.log(`e2e_status=${strict ? "failed" : "skipped"} reason=${reason}`);
  console.log(`hint=${hint}`);
  return strict ? 1 : 0;
}

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

function parseFrontendOrigin() {
  const configured = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
  const url = new URL(configured);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("E2E_BASE_URL must use http(s).");
  const port = Number(url.port || (url.protocol === "https:" ? 443 : 80));
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("E2E_BASE_URL has an invalid port.");
  return {
    url: url.toString().replace(/\/$/, ""),
    hostname: url.hostname.replace(/^\[|\]$/g, ""),
    port
  };
}

async function waitForFrontend(origin, child, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "";
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Next.js exited early with code ${child.exitCode}.`);
    try {
      const response = await fetch(`${origin}/workbench`, {
        redirect: "follow",
        signal: AbortSignal.timeout(3_000)
      });
      if (response.status < 500) return;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for ${origin}: ${lastError}`);
}

function startFrontend(origin, env) {
  const nextCli = require.resolve("next/dist/bin/next");
  return spawn(
    process.execPath,
    [nextCli, "dev", "--hostname", origin.hostname, "--port", String(origin.port)],
    {
      cwd: frontendDir,
      env,
      stdio: "inherit",
      windowsHide: true
    }
  );
}

async function terminateOwnedChild(child) {
  if (!child || child.exitCode !== null || !child.pid) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true
    });
  } else {
    child.kill("SIGTERM");
  }
  await Promise.race([once(child, "exit"), delay(5_000)]);
  if (child.exitCode === null) child.kill("SIGKILL");
}

function runPlaywright(cli, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [cli, "test", "--config=playwright.config.ts", ...passthroughArgs],
      {
        cwd: frontendDir,
        env,
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true
      }
    );
    let output = "";
    for (const [stream, destination] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) {
      stream.on("data", (chunk) => {
        const text = String(chunk);
        output += text;
        destination.write(text);
      });
    }
    child.once("error", reject);
    child.once("exit", (status) => resolve({ status: status ?? 1, output }));
  });
}

async function main() {
  const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configuredApiBase) {
    return stopForMissingRuntime(
      "NEXT_PUBLIC_API_BASE_URL_MISSING",
      "Set NEXT_PUBLIC_API_BASE_URL to the live backend origin or use python scripts/run_demo_e2e.py --strict."
    );
  }

  let normalizedApiBase;
  try {
    const apiUrl = new URL(configuredApiBase);
    if (!["http:", "https:"].includes(apiUrl.protocol)) throw new Error("unsupported protocol");
    normalizedApiBase = configuredApiBase.replace(/\/+$/, "");
  } catch {
    return stopForMissingRuntime(
      "NEXT_PUBLIC_API_BASE_URL_INVALID",
      "NEXT_PUBLIC_API_BASE_URL must be an absolute http(s) backend origin."
    );
  }

  if (
    strict &&
    !process.env.E2E_SKIP_WEBSERVER &&
    !process.env.E2E_BASE_URL?.trim() &&
    !process.env.PLAYWRIGHT_BASE_URL?.trim()
  ) {
    return stopForMissingRuntime(
      "E2E_FRONTEND_ORIGIN_MISSING",
      "Set E2E_BASE_URL to an isolated non-default frontend origin or use python scripts/run_demo_e2e.py --strict."
    );
  }

  const cli = resolvePlaywrightCli();
  if (!cli) {
    return stopForMissingRuntime(
      "PLAYWRIGHT_NOT_INSTALLED",
      "Install @playwright/test and browser binaries to run live browser E2E."
    );
  }

  const artifactDirectory = join(frontendDir, "test-results");
  mkdirSync(artifactDirectory, { recursive: true });
  const env = {
    ...process.env,
    NEXT_PUBLIC_API_BASE_URL: normalizedApiBase,
    E2E_SKIP_WEBSERVER: "1",
    CHROME_LOG_FILE: join(artifactDirectory, "chromium-debug.log")
  };
  let frontend;
  try {
    if (!process.env.E2E_SKIP_WEBSERVER) {
      const origin = parseFrontendOrigin();
      frontend = startFrontend(origin, env);
      await waitForFrontend(origin.url, frontend);
    }
    const result = await runPlaywright(cli, env);
    if (result.status !== 0 && /Executable doesn't exist|playwright install|browser.*not.*installed/i.test(result.output)) {
      return stopForMissingRuntime(
        "PLAYWRIGHT_BROWSER_NOT_INSTALLED",
        "Run npx playwright install before requiring browser E2E as a hard gate."
      );
    }
    return result.status;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    console.error(`e2e_status=${strict ? "failed" : "skipped"} reason=E2E_WEBSERVER_STARTUP_FAILED detail=${detail}`);
    return strict ? 1 : 0;
  } finally {
    await terminateOwnedChild(frontend);
  }
}

process.exitCode = await main();
