import { chromium } from "@playwright/test";
import { mkdir, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const option = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
};
const baseURL = option("--base-url", "http://127.0.0.1:3000").replace(/\/$/, "");
const outputDir = resolve(option("--output", resolve(repoRoot, "docs/assets/screenshots")));

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  locale: "zh-CN"
});
const page = await context.newPage();

async function openPage(route, readyText) {
  const response = await page.goto(`${baseURL}${route}`, {
    waitUntil: "domcontentloaded",
    timeout: 45_000
  });
  if (!response?.ok()) throw new Error(`Failed to load ${route}: ${response?.status() ?? "no response"}`);
  await page.getByText(readyText, { exact: false }).first().waitFor({ state: "visible", timeout: 30_000 });
  if ((await page.locator("body").innerText()).includes("Failed to fetch")) {
    throw new Error(`Page ${route} contains a failed API request.`);
  }
}

async function capture(filename) {
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.waitForTimeout(500);
  const path = resolve(outputDir, filename);
  await page.screenshot({ path, fullPage: true });
  if ((await stat(path)).size < 5_000) throw new Error(`Screenshot ${filename} is visually empty.`);
  process.stdout.write(`captured=${path.replaceAll("\\", "/")}\n`);
}

try {
  await openPage("/workbench?demo=1", "演示模式 · 非真实执行");
  await capture("v5-workbench.png");

  await page.getByLabel("研究目标").fill("比较现有 RAG 与 Evidence Agent 的可追溯性，并给出有证据约束的升级建议。");
  await page.getByRole("button", { name: "开始研究" }).click();
  await page.getByText("需要你的批准", { exact: false }).waitFor({ state: "visible", timeout: 30_000 });
  await capture("v5-run-workspace.png");

  await page.getByRole("button", { name: "批准并继续" }).click();
  await page.getByRole("heading", { name: "研究已完成" }).waitFor({ state: "visible", timeout: 30_000 });
  await page.getByRole("link", { name: "查看研究成果" }).click();
  await page.getByRole("heading", { name: "Evidence Agent 升级决策简报" }).waitFor({ state: "visible", timeout: 30_000 });
  await page.getByRole("button", { name: "查看证据 1.1" }).click();
  await page.getByTestId("evidence-inspector").waitFor({ state: "visible", timeout: 30_000 });
  await capture("v5-artifact-evidence.png");

  const spaces = [
    { id: 1, name: "Synthetic · Evidence Agent 产品研究", description: "Public showcase data", created_at: "2026-08-15T10:00:00Z", updated_at: "2026-08-15T10:00:00Z" }
  ];
  const source = (id, title, sourceType, revisionId, vectors) => ({
    id,
    space_id: 1,
    document_id: sourceType === "document" ? id + 100 : null,
    source_type: sourceType,
    title,
    original_filename: title,
    mime_type: sourceType === "code" ? "text/x-python" : "application/pdf",
    file_size: 12_000 + id,
    storage_path: null,
    content_hash: "c".repeat(64),
    status: "active",
    language: "zh-CN",
    duration_ms: sourceType === "video" ? 84_000 : null,
    page_count: sourceType === "document" ? 18 : null,
    width: null,
    height: null,
    metadata_json: "{}",
    active_revision_id: revisionId,
    latest_revision_id: revisionId,
    media_assets: [],
    revisions: [{
      id: revisionId,
      source_id: id,
      revision_number: 2,
      status: "active",
      parser_name: "v5-evidence-index",
      parser_version: "1",
      chunk_count: vectors,
      vector_count: vectors,
      validation_status: "passed",
      error_message: null,
      metadata_json: "{}",
      activated_at: "2026-08-15T10:00:00Z",
      chunks: [],
      transcript_segments: [],
      visual_frames: []
    }],
    created_at: "2026-08-15T10:00:00Z",
    updated_at: "2026-08-15T10:00:00Z"
  });
  const sources = [
    source(11, "Evidence Agent contract.pdf", "document", 21, 18),
    source(12, "RAG evaluation baseline.md", "document", 22, 10),
    source(13, "agent_runtime.py", "code", 23, 14),
    source(14, "Architecture review.mp4", "video", 24, 26)
  ];
  await page.route("**/api/knowledge-spaces", (route) => route.fulfill({
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify({ success: true, data: spaces, error: null, request_id: "showcase-spaces" })
  }));
  await page.route("**/api/media/sources", (route) => route.fulfill({
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify({ success: true, data: sources, error: null, request_id: "showcase-sources" })
  }));
  await openPage("/library", "证据资料库");
  await page.getByText("Evidence Agent contract.pdf", { exact: true }).waitFor({ state: "visible", timeout: 30_000 });
  await capture("v5-library.png");
} finally {
  await browser.close();
}
