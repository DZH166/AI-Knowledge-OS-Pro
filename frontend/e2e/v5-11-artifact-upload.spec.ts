import { expect, test, type Locator, type Page } from "@playwright/test";
import type { IngestionJob } from "../types/api";

// All HTTP data below is controlled test input, not live-provider or real-service evidence.
const respond = (data: unknown) => ({ contentType: "application/json", headers: { "access-control-allow-origin": "*" },
  body: JSON.stringify({ success: true, data, error: null, request_id: "controlled-v511" }) });
const markdown = "# 对比结论\n\n| 方案 | 条件 | 证据 | 限制 | 成本 | 可追溯性 | 备注 |\n| --- | --- | --- | --- | --- | --- | --- |\n"
  + "| 方案 A | 指定负载下的测量 | 固定版本的原文证据 | 不能推广到所有负载 | 尚待核对 | 可以回到引用来源 | 需要人工核对缺失条件 |\n\n"
  + "- 保留必要条件\n- 打开引用核对\n\n```ts\nconst fixedEvidence = '" + "long-code-value-".repeat(30) + "';\n```\n\n"
  + "[来源链接](https://example.com/source)\n\n[不安全链接](javascript:alert%281%29)\n\n"
  + "![远程图片说明](https://example.com/tracking-image.png)\n\n<script>window.reportExecuted = true</script>";

async function uploadCatalog(page: Page) {
  await page.route("**/api/knowledge-spaces", (route) => route.fulfill(respond([{ id: 7, name: "受控上传空间", description: "",
    created_at: "2026-10-13T00:00:00Z", updated_at: "2026-10-13T00:00:00Z" }])));
  await page.route("**/api/documents", (route) => route.fulfill(respond([])));
  await page.route("**/api/media/sources", (route) => route.fulfill(respond([])));
  await page.route("**/api/onboarding", (route) => route.fulfill(respond({ steps: { upload_document: true } })));
  await page.route("**/api/documents/upload", (route) => route.fulfill(respond({ document: { id: 42, space_id: 7,
    original_filename: "受控资料.md", processing_progress: 0, chunk_count: 0,
    created_at: "2026-10-13T00:00:00Z", updated_at: "2026-10-13T00:00:00Z" }, job_id: 511, message: "已接收文件，等待处理" })));
}

function completedJob(): IngestionJob {
  return { id: 511, document_id: 42, source_id: 7, space_id: 7, target_type: "document", job_type: "reparse",
    status: "completed", current_step: "indexing", step_index: 5, step_total: 5, progress: 100,
    worker_id: null, queue_name: "default", priority: 100, attempt: 1, max_attempts: 3, message: "已完成",
    error_code: null, error_message: null, error_details_json: "{}", result_json: "{}", parent_job_id: null, retry_count: 0,
    started_at: "2026-10-13T00:00:00Z", heartbeat_at: null, finished_at: "2026-10-13T00:00:05Z",
    cancel_requested_at: null, duration_ms: 5000, created_at: "2026-10-13T00:00:00Z", updated_at: "2026-10-13T00:00:05Z" };
}

async function reportCatalog(page: Page, secondEvidence = false) {
  const artifact = { schema_version: 1, id: "controlled-artifact-v511", producing_run_id: "controlled-run-v511",
    kind: "comparison", title: "受控录制成果 · 不是服务质量评测", body_markdown: markdown, status: "final",
    claims: [{ id: "claim-v511", ordinal: 1, text: "指定条件下的比较结论", kind: "factual", verification_status: "supported",
      evidence_ids: secondEvidence ? ["evidence-v511-first", "evidence-v511-second"] : ["evidence-v511-first"] }] };
  await page.route("**/api/v1/artifacts/controlled-artifact-v511", (route) => route.fulfill(respond(artifact)));
  await page.route("**/api/v1/evidence/evidence-v511-first", (route) => route.fulfill(respond(evidence("first"))));
  await page.route("**/api/v1/evidence/evidence-v511-second", (route) => route.fulfill(respond(evidence("second"))));
}

function evidence(which: "first" | "second") {
  return { schema_version: 1, id: `evidence-v511-${which}`, run_id: "controlled-run-v511", source_id: which === "first" ? 7 : 17,
    revision_id: which === "first" ? 8 : 18, index_revision_id: which === "first" ? 9 : 19,
    chunk_id: which === "first" ? 10 : 20, source_type: "document",
    locator: { kind: "document_page", document_id: which === "first" ? 42 : 43, page_number: which === "first" ? 3 : 4 },
    content_hash: (which === "first" ? "a" : "c").repeat(64), revision_content_hash: "b".repeat(64),
    excerpt_preview: which === "first" ? "第一份证据：数值成立需要保留指定负载条件。" : "第二份证据：不能被第一份请求的晚到结果覆盖。",
    claim_ids: ["claim-v511"] };
}

async function tabTo(page: Page, target: Locator) {
  for (let index = 0; index < 40; index += 1) {
    if (await target.evaluate((element) => element === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error("Keyboard navigation did not reach the file control");
}

async function drop(page: Page, name: string) {
  const transfer = await page.evaluateHandle((filename) => {
    const data = new DataTransfer();
    data.items.add(new File(["受控文件内容"], filename, { type: filename.endsWith(".md") ? "text/markdown" : "image/png" }));
    return data;
  }, name);
  const target = page.locator("label").filter({ hasText: "拖拽或点击选择 txt / md / pdf" });
  await target.dispatchEvent("dragover", { dataTransfer: transfer });
  await target.dispatchEvent("drop", { dataTransfer: transfer });
  await transfer.dispose();
}

test("keyboard file selection reaches the backend completed stage at 100 percent", async ({ page }) => {
  await uploadCatalog(page);
  await page.route("**/api/ingestion-jobs/511", (route) => route.fulfill(respond(completedJob())));
  await page.goto("/upload?scenario=compare&space_id=7");
  const input = page.getByLabel("选择文档文件", { exact: true });
  await expect(input).toBeVisible();
  await tabTo(page, input);
  await expect(input).toBeFocused();
  const chooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Enter");
  await (await chooser).setFiles({ name: "keyboard.md", mimeType: "text/markdown", buffer: Buffer.from("受控资料") });
  await expect(page.getByText("keyboard.md", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "开始上传", exact: true }).click();
  await expect(page.getByRole("list", { name: "文档处理阶段" }).locator('[aria-current="step"]')).toHaveText("完成");
  await expect(page.getByRole("progressbar", { name: "keyboard.md 的处理进度" })).toHaveAttribute("value", "100");
});

test("drop validates file types and polling failure recovers with a status read instead of a job restart", async ({ page }) => {
  await uploadCatalog(page);
  let unavailable = true;
  let restartCommands = 0;
  await page.route("**/api/ingestion-jobs/511", (route) => unavailable ? route.fulfill({ status: 503,
    contentType: "application/json", headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify({ success: false, error: { code: "CONTROLLED_STATUS_UNAVAILABLE", user_message: "受控状态读取失败" } })
  }) : route.fulfill(respond(completedJob())));
  await page.route("**/api/ingestion-jobs/511/retry", (route) => { restartCommands += 1; return route.abort(); });
  await page.goto("/upload?scenario=compare&space_id=7");
  await drop(page, "unsupported.png");
  await expect(page.getByText("暂不支持该格式", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始上传", exact: true })).toBeDisabled();
  await drop(page, "dropped.md");
  await expect(page.getByText("dropped.md", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "开始上传", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("保留上次已知进度");
  unavailable = false;
  await page.getByRole("button", { name: "刷新处理状态", exact: true }).click();
  await expect(page.getByRole("list", { name: "文档处理阶段" }).locator('[aria-current="step"]')).toHaveText("完成");
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  expect(restartCommands).toBe(0);
});

test("report Markdown stays safe and scrollable at 390px without fetching remote images", async ({ page }, testInfo) => {
  await reportCatalog(page);
  const imageRequests: string[] = [];
  await page.route("https://example.com/**", (route) => { imageRequests.push(route.request().url()); return route.abort(); });
  await page.goto("/artifacts/controlled-artifact-v511");
  await expect(page.getByRole("heading", { name: "对比结论", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("artifact-body-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const table = page.getByRole("region", { name: "研究正文表格", exact: true });
  const code = page.getByRole("region", { name: "研究正文代码", exact: true });
  await expect(table.getByRole("table")).toBeVisible();
  for (const region of [table, code]) {
    await region.focus();
    await expect(region).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect.poll(() => region.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByTestId("artifact-body").locator("img")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "不安全链接", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => "reportExecuted" in window)).toBe(false);
  expect(imageRequests).toEqual([]);
});

test("mobile artifact citation opens in view, Escape restores focus, and widening releases the dialog", async ({ page }, testInfo) => {
  await reportCatalog(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/artifacts/controlled-artifact-v511");
  const citation = page.getByRole("button", { name: "查看证据 1.1", exact: true });
  await citation.click();
  const dialog = page.getByRole("dialog", { name: "证据详情", exact: true });
  await expect(dialog).toContainText("第一份证据：数值成立需要保留指定负载条件。");
  const box = await dialog.boundingBox();
  expect(box?.y).toBeGreaterThanOrEqual(0);
  expect((box?.y ?? 844) + (box?.height ?? 844)).toBeLessThanOrEqual(844);
  await expect(dialog.getByRole("link", { name: "打开固定来源" })).toHaveAttribute("href",
    /\/documents\/42\?page=3&source=7&revision=8&index_revision=9&chunk=10&hash=/);
  await page.screenshot({ path: testInfo.outputPath("artifact-evidence-mobile.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(citation).toBeFocused();
  await citation.click();
  await expect(dialog).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await expect(page.getByTestId("evidence-inspector")).toContainText("page_number=3");
  const backgroundLink = page.getByRole("link", { name: "返回成果列表", exact: true });
  await backgroundLink.focus();
  await expect(backgroundLink).toBeFocused();
});

test("mobile recording-run evidence closes back to its ledger button and remains usable after widening", async ({ page }, testInfo) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url()); });
  await page.route("**/api/**", (route) => route.abort());
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workbench?demo=1");
  await page.getByRole("button", { name: "开始研究", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\/demo-run-/);
  const citation = page.getByRole("button", { name: "检查证据 Evidence Agent contract.pdf", exact: true });
  await citation.click();
  const dialog = page.getByRole("dialog", { name: "证据详情", exact: true });
  await expect(dialog).toContainText("immutable revision");
  await expect(dialog.getByRole("button", { name: "关闭证据详情" })).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath("run-evidence-mobile.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(citation).toBeFocused();
  await citation.click();
  await expect(dialog).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  const cancel = page.getByRole("button", { name: "取消 Run", exact: true });
  await cancel.focus();
  await expect(cancel).toBeFocused();
  expect(apiRequests).toEqual([]);
});

test("closing a pending evidence read clears busy state and a late result cannot replace the next citation", async ({ page }) => {
  await reportCatalog(page, true);
  let releaseFirst: () => void = () => {};
  const firstResponse = new Promise<void>((resolve) => { releaseFirst = resolve; });
  let firstRequested: () => void = () => {};
  const requested = new Promise<void>((resolve) => { firstRequested = resolve; });
  let handledFirst: () => void = () => {};
  const handled = new Promise<void>((resolve) => { handledFirst = resolve; });
  await page.route("**/api/v1/evidence/evidence-v511-first", async (route) => {
    firstRequested();
    await firstResponse;
    try { await route.fulfill(respond(evidence("first"))); }
    catch (error) { if (!route.request().failure()) throw error; }
    finally { handledFirst(); }
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/artifacts/controlled-artifact-v511");
  try {
    const first = page.getByRole("button", { name: "查看证据 1.1", exact: true });
    await first.click();
    await requested;
    const dialog = page.getByRole("dialog", { name: "证据详情", exact: true });
    await expect(dialog).toHaveAttribute("aria-busy", "true");
    await page.keyboard.press("Escape");
    await expect(first).toBeFocused();
    await expect(page.getByTestId("evidence-inspector")).toHaveAttribute("aria-busy", "false");
    await page.getByRole("button", { name: "查看证据 1.2", exact: true }).click();
    await expect(dialog).toContainText("第二份证据：不能被第一份请求的晚到结果覆盖。");
    releaseFirst();
    await handled;
    await expect(dialog).toContainText("第二份证据：不能被第一份请求的晚到结果覆盖。");
    await expect(dialog).not.toContainText("第一份证据：");
    await expect(dialog.getByRole("link", { name: "打开固定来源" })).toHaveAttribute("href", /source=17&revision=18&index_revision=19&chunk=20/);
  } finally { releaseFirst(); }
});
