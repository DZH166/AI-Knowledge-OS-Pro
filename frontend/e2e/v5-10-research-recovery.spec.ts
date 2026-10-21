import { expect, test, type Page } from "@playwright/test";
import type { SourceItem } from "../types/api";

// Controlled public-page recovery checks; the integration window supplies the server.

const draftKey = "evidence-agent:workbench-draft:v1:real";
const pendingKey = "evidence-agent:workbench-pending:v1:real";
const respond = (data: unknown, status = 200) => ({ status, contentType: "application/json",
  headers: { "access-control-allow-origin": "*" },
  body: JSON.stringify({ success: true, data, error: null, request_id: "v510-browser" }) });

function source(id: number, spaceId = 7): SourceItem {
  const revisionId = id * 10;
  const indexId = id * 100;
  return {
    id, space_id: spaceId, document_id: id, source_type: "document", title: `资料 ${id}.md`,
    original_filename: `资料 ${id}.md`, mime_type: "text/markdown", file_size: 100,
    storage_path: null, content_hash: "a".repeat(64), status: "active", language: "zh-CN",
    duration_ms: null, page_count: null, width: null, height: null, metadata_json: "{}",
    active_revision_id: revisionId, latest_revision_id: revisionId, active_index_revision_id: indexId,
    media_assets: [], created_at: "2026-10-02T00:00:00Z", updated_at: "2026-10-02T00:00:00Z",
    revisions: [{ id: revisionId, source_id: id, revision_number: 1, status: "active",
      parser_name: "markdown", parser_version: "1", chunk_count: 1, vector_count: 1,
      validation_status: "passed", error_message: null, metadata_json: "{}", activated_at: "2026-10-02T00:00:00Z",
      index_revisions: [{ id: indexId, source_id: id, revision_id: revisionId, status: "active", index_version: "1" }],
      chunks: [], transcript_segments: [], visual_frames: [] }]
  };
}

async function catalog(page: Page, initialSources = [source(71), source(72), source(73), source(81, 8)]) {
  let sources = initialSources;
  const spaces = [7, 8].map((id) => ({ id, name: `研究空间 ${id}`, description: "",
    created_at: "2026-10-02T00:00:00Z", updated_at: "2026-10-02T00:00:00Z" }));
  await page.route("**/api/knowledge-spaces", (route) => route.fulfill(respond(spaces)));
  await page.route("**/api/media/sources", (route) => route.fulfill(respond(sources)));
  await page.route("**/api/documents", (route) => route.fulfill(respond([])));
  await page.route("**/api/onboarding", (route) => route.fulfill(respond({ steps: {} })));
  await page.route("**/api/system/status", (route) => route.fulfill(respond({
    llm: { ok: true, status: "configured" }, embedding: { ok: true, status: "configured" },
    qdrant: { ok: true, status: "ready" }, redis: { ok: true, status: "ready" }
  })));
  return { setSources: (next: SourceItem[]) => { sources = next; } };
}

async function settings(page: Page) {
  const disclosure = page.locator("details").filter({ hasText: "来源与运行设置" });
  if (await disclosure.count() && await disclosure.getAttribute("open") === null) await disclosure.locator("summary").click();
}

function runView(runId: string, goal: string, gap = false) {
  return { schema_version: 1, id: runId, space_id: 7, goal, requested_mode: "force_agent", effective_mode: "force_agent",
    status: gap ? "insufficient_evidence" : "queued", phase: gap ? "persist_artifact" : "route", version: 1,
    execution_epoch: 0, scope_snapshot: { space_id: 7, revisions: [] }, budget_limits: { max_steps: 16 },
    budget_usage: {}, cost_measurement: "unknown", provider_mode: "real", last_event_cursor: 0,
    final_artifact_id: gap ? "gap-report" : null, termination_reason: gap ? "第三份资料没有支持证据" : null,
    outcome: gap ? { kind: "insufficient_evidence", reason: "requirements_uncovered", gaps: ["缺少第三份资料的关联证据"] } : null };
}

async function stream(page: Page, view: ReturnType<typeof runView>) {
  await page.route(`**/api/v1/evidence-runs/${view.id}/stream*`, (route) => route.fulfill({
    contentType: "text/event-stream", headers: { "access-control-allow-origin": "*" },
    body: `id: 0\nevent: sync\ndata: ${JSON.stringify({ schema_version: 1, cursor: 0, run_version: 1,
      type: "sync", payload: { run: view } })}\n\n`
  }));
}

test("comparison draft survives reload with question, dimensions, scope and budget", async ({ page }) => {
  // Legacy sources can lack the Source pointer while retaining a valid same-revision active index.
  await catalog(page, [{ ...source(71), active_index_revision_id: null }, source(72), source(73)]);
  await page.goto("/workbench?scenario=compare&space_id=7");
  await page.getByLabel("研究目标").fill("比较三个方案的实际部署风险");
  await page.getByLabel("比较维度").fill("人力成本、数据迁移、长期维护");
  await page.getByLabel("预算上限").selectOption("deep");
  for (const id of [71, 72, 73]) await page.getByRole("checkbox", { name: `选择 资料 ${id}.md` }).check();
  await page.reload();
  await expect(page.getByLabel("研究目标")).toHaveValue("比较三个方案的实际部署风险");
  await expect(page.getByLabel("比较维度")).toHaveValue("人力成本、数据迁移、长期维护");
  await expect(page.getByLabel("预算上限")).toHaveValue("deep");
  await expect(page.getByRole("combobox", { name: "知识空间 *", exact: true })).toHaveValue("7");
  for (const id of [71, 72, 73]) await expect(page.getByRole("checkbox", { name: `选择 资料 ${id}.md` })).toBeChecked();
  await expect(page.getByRole("button", { name: "开始对比研究" })).toBeEnabled();
});

test("ordinary draft keeps its selected space, deliverable and execution mode", async ({ page }) => {
  await catalog(page);
  await page.goto("/workbench");
  await settings(page);
  await page.getByLabel("研究目标").fill("核对空间八的具体方案");
  await page.getByRole("combobox", { name: "知识空间 *", exact: true }).selectOption("8");
  await page.getByRole("checkbox", { name: "选择 资料 81.md" }).check();
  await page.getByLabel("交付物").selectOption("answer");
  await page.getByLabel("执行模式").selectOption("force_quick");
  await page.getByLabel("预算上限").selectOption("quick");
  await page.reload();
  await settings(page);
  await expect(page.getByLabel("研究目标")).toHaveValue("核对空间八的具体方案");
  await expect(page.getByRole("combobox", { name: "知识空间 *", exact: true })).toHaveValue("8");
  await expect(page.getByRole("checkbox", { name: "选择 资料 81.md" })).toBeChecked();
  await expect(page.getByLabel("交付物")).toHaveValue("answer");
  await expect(page.getByLabel("执行模式")).toHaveValue("force_quick");
  await expect(page.getByLabel("预算上限")).toHaveValue("quick");
});

test("uploading a missing third document and returning keeps the existing comparison draft", async ({ page }) => {
  const scope = await catalog(page, [source(71), source(72)]);
  await page.route("**/api/documents/upload", async (route) => {
    scope.setSources([source(71), source(72), source(73)]);
    await route.fulfill(respond({ document: { id: 73, space_id: 7, original_filename: "第三份资料.md",
      chunk_count: 1, processing_progress: 100, created_at: "2026-10-02T00:00:00Z", updated_at: "2026-10-02T00:00:00Z" },
      message: "已处理", job_id: null }));
  });
  await page.goto("/workbench?scenario=compare&space_id=7");
  await page.getByLabel("研究目标").fill("我自己的三方案问题");
  await page.getByLabel("比较维度").fill("成本、维护难度");
  await page.getByLabel("预算上限").selectOption("deep");
  for (const id of [71, 72]) await page.getByRole("checkbox", { name: `选择 资料 ${id}.md` }).check();
  await page.getByRole("link", { name: "前往上传资料" }).click();
  await expect(page.getByRole("combobox", { name: "本次研究的知识空间" })).toHaveValue("7");
  await page.locator('input[type="file"]').setInputFiles({ name: "第三份资料.md", mimeType: "text/markdown", buffer: Buffer.from("补充资料") });
  await page.getByRole("button", { name: "开始上传" }).click();
  await expect(page.getByRole("link", { name: "返回对比工作台" })).toBeVisible();
  await page.getByRole("link", { name: "返回三资料对比" }).click();
  await expect(page.getByLabel("研究目标")).toHaveValue("我自己的三方案问题");
  await expect(page.getByLabel("比较维度")).toHaveValue("成本、维护难度");
  await expect(page.getByLabel("预算上限")).toHaveValue("deep");
  for (const id of [71, 72]) await expect(page.getByRole("checkbox", { name: `选择 资料 ${id}.md` })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "选择 资料 73.md" })).not.toBeChecked();
});

test("an uncertain POST is saved before sending and manually replays the unchanged original after edit and retirement", async ({ page }) => {
  const scope = await catalog(page);
  const posts: Array<Record<string, unknown>> = [];
  const view = runView("uncertain-run", "原始请求的问题");
  await stream(page, view);
  await page.route("**/api/v1/evidence-runs/uncertain-run", (route) => route.fulfill(respond(view)));
  await page.route("**/api/v1/evidence-runs", async (route) => {
    const input = route.request().postDataJSON();
    const persisted = await page.evaluate((key) => JSON.parse(sessionStorage.getItem(key) ?? "null"), pendingKey);
    expect(persisted.value.input).toEqual(input);
    posts.push(input);
    if (posts.length === 1) return route.abort("failed");
    return route.fulfill(respond({ schema_version: 1, command_id: "same-command", run_id: view.id,
      run_version: 1, status: "queued", cursor: 0, replayed: true }, 201));
  });
  await page.goto("/workbench");
  await settings(page);
  await page.getByLabel("研究目标").fill(view.goal);
  await page.getByLabel("预算上限").selectOption("deep");
  await page.getByLabel("交付物").selectOption("answer");
  await page.getByRole("checkbox", { name: "选择 资料 71.md" }).check();
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("网络连接失败");
  await page.getByLabel("研究目标").fill("修改后的另一个问题");
  scope.setSources([{ ...source(71), status: "retired" }, source(72), source(73)]);
  await page.reload();
  await settings(page);
  await expect(page.getByLabel("研究目标")).toHaveValue("修改后的另一个问题");
  await expect(page.getByRole("button", { name: "开始研究" })).toBeDisabled();
  expect(posts).toHaveLength(1);
  await page.getByRole("button", { name: "确认使用当前证据范围" }).click();
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("当前草稿已改变");
  expect(posts).toHaveLength(1);
  await page.getByRole("button", { name: "恢复原研究" }).click();
  await expect(page).toHaveURL(/\/runs\/uncertain-run$/);
  expect(posts).toHaveLength(2);
  expect(posts[1]).toEqual(posts[0]);
});

test("known run recovery survives refresh and clear-draft and only reads the original run", async ({ page }) => {
  await catalog(page);
  let posts = 0;
  let detailReads = 0;
  const view = runView("known-run", "保留已建成任务");
  await stream(page, view);
  await page.route("**/api/v1/evidence-runs", (route) => {
    posts += 1;
    return route.fulfill(respond({ schema_version: 1, command_id: "known-command", run_id: view.id,
      run_version: 1, status: "queued", cursor: 0, replayed: false }, 201));
  });
  await page.route("**/api/v1/evidence-runs/known-run", (route) => {
    detailReads += 1;
    return detailReads === 1 ? route.fulfill({ status: 503, body: "temporarily unavailable" }) : route.fulfill(respond(view));
  });
  await page.goto("/workbench");
  await page.getByLabel("研究目标").fill(view.goal);
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("研究任务已创建");
  await page.reload();
  await expect(page.getByRole("button", { name: "打开已创建的研究" })).toBeVisible();
  expect(detailReads).toBe(1);
  expect(posts).toBe(1);
  await page.getByRole("button", { name: "清除草稿" }).click();
  await expect(page.getByText("草稿已清除。此前尚未确认的任务没有被取消，仍可恢复原研究。")).toBeVisible();
  await page.getByRole("button", { name: "打开已创建的研究" }).click();
  await expect(page).toHaveURL(/\/runs\/known-run$/);
  expect(detailReads).toBe(2);
  expect(posts).toBe(1);
});

test("clearing identical default fields and refreshing still requires an explicit recovery choice", async ({ page }) => {
  await catalog(page);
  const posts: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/evidence-runs", (route) => { posts.push(route.request().postDataJSON()); return route.abort("failed"); });
  await page.goto("/workbench");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.getByRole("button", { name: "恢复原研究" })).toBeVisible();
  const originalGoal = await page.getByLabel("研究目标").inputValue();
  await page.getByRole("button", { name: "清除草稿" }).click();
  await expect(page.getByLabel("研究目标")).toHaveValue(originalGoal);
  await page.reload();
  await expect(page.getByRole("button", { name: "恢复原研究" })).toBeVisible();
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("原提交解绑");
  expect(posts).toHaveLength(1);
  await page.getByRole("button", { name: "恢复原研究" }).click();
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[1]).toEqual(posts[0]);
});

test("a retained known recording marker opens the same run when marker removal is denied", async ({ page }) => {
  await page.addInitScript(() => {
    const remove = Storage.prototype.removeItem;
    Storage.prototype.removeItem = function (key) {
      if (key.includes("workbench-pending")) throw new Error("marker removal denied");
      return remove.call(this, key);
    };
  });
  await page.goto("/workbench?demo=1");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page).toHaveURL(/\/runs\/demo-run-/);
  const originalPath = new URL(page.url()).pathname;
  await expect(page.getByText(/本地仍有这项研究的待确认标记/)).toBeVisible();
  await page.goto("/workbench?demo=1");
  await page.getByRole("button", { name: "打开已创建的研究" }).click();
  await expect(page).toHaveURL(new RegExp(`${originalPath}\\?demo=1$`));
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("evidence-agent:runs:v1") ?? "[]").length)).toBe(1);
});

test("readable but unwritable state keeps live scenario changes and reports failed draft removal honestly", async ({ page }) => {
  await catalog(page);
  await page.addInitScript(({ draftKey, pendingKey }) => {
    sessionStorage.setItem(draftKey, JSON.stringify({ version: 1, savedAt: Date.now(), value: {
      recording: false, journeyEnabled: true, goal: "旧草稿问题", dimensions: "旧维度", spaceId: 7,
      selectedSourceIds: [71, 72, 73], scopeNeedsReview: false, submissionDetached: false,
      budgetProfile: "deep", deliverable: "answer", mode: "force_agent"
    } }));
    sessionStorage.setItem(pendingKey, JSON.stringify({ version: 1, savedAt: Date.now(),
      value: { input: { request_id: "read-only-stable-request", space_id: 7, goal: "原始待确认问题", provider_mode: "real" } } }));
    const set = Storage.prototype.setItem;
    const remove = Storage.prototype.removeItem;
    Storage.prototype.setItem = function (key, value) {
      if (key.includes("workbench-")) throw new Error("write denied");
      return set.call(this, key, value);
    };
    Storage.prototype.removeItem = function (key) {
      if (key.includes("workbench-")) throw new Error("removal denied");
      return remove.call(this, key);
    };
  }, { draftKey, pendingKey });
  await page.goto("/workbench?scenario=compare&space_id=7");
  await page.getByLabel("研究目标").fill("本页还未保存的新问题");
  await page.getByRole("button", { name: "退出对比流程" }).click();
  await expect(page.getByLabel("比较维度")).toHaveCount(0);
  await expect(page.getByLabel("研究目标")).toHaveValue("本页还未保存的新问题");
  await expect(page).toHaveURL(/scenario=ordinary/);
  await expect(page.getByRole("button", { name: "恢复原研究" })).toBeVisible();
  await page.getByRole("button", { name: "清除草稿" }).click();
  await expect(page.getByText(/当前表单已重置，但草稿清除失败/)).toBeVisible();
  await expect(page.getByRole("region", { name: "待确认研究" })).toContainText("read-only-stable-request");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.locator("form [role='alert']")).toContainText("原提交解绑");
});

test("real and recording drafts stay separate while the original real request remains recoverable", async ({ page }) => {
  await catalog(page);
  let posts = 0;
  await page.route("**/api/v1/evidence-runs", (route) => { posts += 1; return route.abort("failed"); });
  await page.goto("/workbench");
  await settings(page);
  await page.getByLabel("研究目标").fill("仅用于真实研究的问题");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page.getByRole("button", { name: "恢复原研究" })).toBeVisible();
  await page.getByRole("checkbox", { name: "使用演示模式" }).check();
  await expect(page).toHaveURL(/demo=1/);
  await expect(page.getByLabel("研究目标")).not.toHaveValue("仅用于真实研究的问题");
  await settings(page);
  await page.getByLabel("研究目标").fill("仅用于录制练习的问题");
  await page.getByRole("checkbox", { name: "使用演示模式" }).uncheck();
  await expect(page.getByLabel("研究目标")).toHaveValue("仅用于真实研究的问题");
  await expect(page.getByRole("button", { name: "恢复原研究" })).toBeVisible();
  expect(posts).toBe(1);
});

test("explicit URL space and scenario override the saved draft without cross-space selections", async ({ page }) => {
  await catalog(page);
  await page.goto("/workbench?scenario=compare&space_id=7");
  await page.getByLabel("研究目标").fill("保留问题但不能保留其他空间选择");
  await page.getByRole("checkbox", { name: "选择 资料 71.md" }).check();
  await page.goto("/workbench?scenario=ordinary&space_id=8");
  await settings(page);
  await expect(page.getByRole("combobox", { name: "知识空间 *", exact: true })).toHaveValue("8");
  await expect(page.getByLabel("比较维度")).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "选择 资料 81.md" })).not.toBeChecked();
  await expect(page.getByRole("button", { name: "开始研究" })).toBeDisabled();
  await expect(page.getByText("原证据范围需要重新确认")).toBeVisible();
});

test("corrupt pending data requires an explicit record check and never silently creates a new identity", async ({ page }) => {
  await catalog(page);
  let posts = 0;
  await page.route("**/api/v1/evidence-runs", (route) => { posts += 1; return route.abort("failed"); });
  await page.addInitScript(({ draftKey, pendingKey }) => {
    sessionStorage.setItem(draftKey, "{"); sessionStorage.setItem(pendingKey, "{");
  }, { draftKey, pendingKey });
  await page.goto("/workbench");
  await page.getByLabel("研究目标").fill("损坏状态后仍能编辑");
  await expect(page.getByRole("button", { name: "开始研究" })).toBeDisabled();
  expect(posts).toBe(0);
  await page.getByRole("button", { name: "已核对记录，开始新的研究" }).click();
  await expect(page.getByRole("button", { name: "开始研究" })).toBeEnabled();
});

test("expired editable draft does not expire an immutable pending request", async ({ page }) => {
  await catalog(page);
  await page.addInitScript(({ draftKey, pendingKey }) => {
    sessionStorage.setItem(draftKey, JSON.stringify({ version: 1, savedAt: Date.now() - 25 * 60 * 60 * 1000,
      value: { recording: false, journeyEnabled: false, goal: "已经过期的问题", dimensions: "旧维度", spaceId: 7,
        selectedSourceIds: [71], scopeNeedsReview: false, budgetProfile: "deep", deliverable: "answer", mode: "force_agent" } }));
    sessionStorage.setItem(pendingKey, JSON.stringify({ version: 1, savedAt: Date.now() - 25 * 60 * 60 * 1000,
      value: { input: { request_id: "old-stable-identity", space_id: 7, goal: "已经发出的原始问题", provider_mode: "real" } } }));
  }, { draftKey, pendingKey });
  await page.goto("/workbench");
  await expect(page.getByLabel("研究目标")).not.toHaveValue("已经过期的问题");
  await expect(page.getByRole("region", { name: "待确认研究" })).toContainText("old-stable-identity");
  await expect(page.getByRole("button", { name: "恢复原研究" })).toBeVisible();
});

test("denied session storage leaves editing usable and explains the recovery limitation", async ({ page }) => {
  await catalog(page);
  await page.addInitScript(() => { Object.defineProperty(window, "sessionStorage", { get: () => { throw new Error("storage denied"); } }); });
  await page.goto("/workbench");
  await page.getByLabel("研究目标").fill("禁用存储时也能编辑问题");
  await expect(page.getByText(/不能保证刷新或返回后恢复/)).toBeVisible();
  await page.getByRole("button", { name: "已核对记录，开始新的研究" }).click();
  await expect(page.getByRole("button", { name: "开始研究" })).toBeEnabled();
});

test("denied local cache does not misreport successful production creation", async ({ page }) => {
  await catalog(page);
  await page.addInitScript(() => { Object.defineProperty(window, "localStorage", { get: () => { throw new Error("cache denied"); } }); });
  const view = runView("cache-denied-run", "后端已创建的研究仍可打开");
  await stream(page, view);
  await page.route("**/api/v1/evidence-runs", (route) => route.fulfill(respond({ schema_version: 1,
    command_id: "cache-command", run_id: view.id, run_version: 1, status: "queued", cursor: 0, replayed: false }, 201)));
  await page.route(`**/api/v1/evidence-runs/${view.id}`, (route) => route.fulfill(respond(view)));
  await page.goto("/workbench");
  await page.getByLabel("研究目标").fill(view.goal);
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect(page).toHaveURL(/\/runs\/cache-denied-run$/);
  await expect(page.getByRole("heading", { name: view.goal })).toBeVisible();
});

test("an insufficient-evidence run opens its saved gap report", async ({ page }) => {
  const view = runView("gap-run", "未覆盖全部来源的研究", true);
  await stream(page, view);
  await page.route("**/api/v1/artifacts/gap-report", (route) => route.fulfill(respond({ schema_version: 1,
    id: "gap-report", producing_run_id: view.id, kind: "evidence_gap_report", title: "尚未完成的研究部分",
    body_markdown: "第三份资料没有关联的支持或矛盾证据。", status: "final", claims: [] })));
  await page.goto("/runs/gap-run");
  const link = page.getByRole("link", { name: "查看缺口报告" });
  await expect(link).toHaveAttribute("href", "/artifacts/gap-report");
  await link.click();
  await expect(page.getByRole("heading", { name: "尚未完成的研究部分" })).toBeVisible();
});
