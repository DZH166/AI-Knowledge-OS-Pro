import { expect, test } from "@playwright/test";

test.describe("V5 Evidence Agent product loop", () => {
  test("starts a clearly labelled recording run, handles approval, and opens a cited artifact", async ({ page }) => {
    const productionApiRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/")) productionApiRequests.push(request.url());
    });
    await page.goto("/workbench?demo=1");

    await expect(page.getByRole("heading", { name: "开始一次可核验研究" })).toBeVisible();
    await expect(page.getByText("Recording Demo · 非真实执行")).toBeVisible();
    await expect(page.getByRole("option", { name: "Synthetic · Evidence Agent 产品研究" })).toBeAttached();
    await page.getByLabel("研究目标").fill("比较现有 RAG 与 Evidence Agent 的可追溯性，并给出有证据约束的升级建议。");
    await page.getByRole("button", { name: "开始研究" }).click();

    // Next dev compiles this dynamic route on first use; parallel CI workers can
    // legitimately spend more than the global 5 s assertion window on that cold build.
    await expect(page).toHaveURL(/\/runs\/demo-run-/, { timeout: 15_000 });
    const runId = decodeURIComponent(new URL(page.url()).pathname.split("/").at(-1) ?? "");
    await expect(page.getByTestId("run-timeline")).toBeVisible();
    await expect(page.getByTestId("evidence-ledger")).toContainText("immutable revision");
    await expect(page.getByTestId("attention-panel")).toContainText("需要你的批准");
    await page.getByRole("button", { name: "批准并继续" }).click();

    await expect(page.getByRole("heading", { name: "研究已完成" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "研究已完成" })).toBeVisible();
    await expect(page.getByTestId("attention-panel")).toHaveCount(0);
    const artifactId = `artifact-${runId}`;
    const artifactLink = page.getByRole("link", { name: "查看研究成果" });
    await expect(artifactLink).toHaveAttribute("href", `/artifacts/${artifactId}?demo=1`);
    await artifactLink.click();
    await expect(page).toHaveURL(new RegExp(`/artifacts/${artifactId}\\?demo=1$`), { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Evidence Agent 升级决策简报" })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看 producing run" })).toHaveAttribute(
      "href",
      `/runs/${runId}?demo=1`
    );
    await page.getByRole("button", { name: /查看证据 1/ }).click();
    const inspector = page.getByTestId("evidence-inspector");
    await expect(inspector).toContainText("Revision 9201");
    const sourceLink = inspector.getByRole("link", { name: "打开固定来源" });
    await expect(sourceLink).toHaveAttribute("href", /\/library\?demo=1&source=9101/);
    await sourceLink.click();
    await expect(page).toHaveURL(/\/library\?demo=1&source=9101/);
    await expect(page.getByText("Recording Demo · Synthetic Sources")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Evidence Agent contract.pdf" })).toBeVisible();
    expect(productionApiRequests).toEqual([]);

    await page.goto("/artifacts/artifact-does-not-exist?demo=1");
    await expect(page.getByRole("heading", { name: "无法加载研究成果" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Evidence Agent 升级决策简报" })).toHaveCount(0);
    expect(productionApiRequests).toEqual([]);
  });

  test("advances a durable backend demo run through the live worker", async ({ request }) => {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBase, "strict live E2E must expose the backend origin").toBeTruthy();
    const spacesResponse = await request.get(`${apiBase}/api/knowledge-spaces`);
    expect(spacesResponse.ok()).toBeTruthy();
    const spacesEnvelope = await spacesResponse.json();
    const spaceId = spacesEnvelope.data?.[0]?.id;
    expect(spaceId).toBeTruthy();

    const openResponse = await request.post(`${apiBase}/api/v1/evidence-runs`, {
      data: {
        schema_version: 1,
        request_id: `live-worker-${crypto.randomUUID()}`,
        space_id: spaceId,
        goal: "How does the system keep multimodal RAG answers traceable?",
        scope: { source_ids: [] },
        deliverable: { kind: "answer", title: "Live worker evidence answer" },
        mode: "force_quick",
        permissions: { read_only: true, allow_scope_expansion: false },
        provider_mode: "demo"
      }
    });
    expect(openResponse.status()).toBe(201);
    const receipt = (await openResponse.json()).data;
    expect(receipt.run_id).toBeTruthy();

    let finalView: Record<string, unknown> | undefined;
    await expect.poll(async () => {
      const response = await request.get(`${apiBase}/api/v1/evidence-runs/${receipt.run_id}`);
      if (!response.ok()) return `http-${response.status()}`;
      finalView = (await response.json()).data;
      return finalView?.status;
    }, { timeout: 30_000 }).toBe("completed");

    expect(finalView?.provider_mode).toBe("demo");
    expect(finalView?.outcome).toMatchObject({ kind: "artifact" });
    expect(Number(finalView?.last_event_cursor)).toBeGreaterThan(0);
  });

  test("replays a production plan and its final supported evidence relation into the workspace", async ({ page }) => {
    const runId = "run-production-projection";
    const runView = {
      schema_version: 1,
      id: runId,
      space_id: 1,
      goal: "Verify immutable evidence projection.",
      requested_mode: "force_agent",
      effective_mode: "force_agent",
      status: "completed",
      phase: "persist_artifact",
      version: 4,
      execution_epoch: 0,
      scope_snapshot: { space_id: 1, revisions: [] },
      budget_limits: { max_steps: 8 },
      budget_usage: { steps: 3 },
      cost_measurement: "reported",
      provider_mode: "real",
      last_event_cursor: 6,
      final_artifact_id: null,
      termination_reason: null,
      outcome: null
    };
    let streamCalls = 0;
    await page.route(`**/api/v1/evidence-runs/${runId}/stream**`, async (route) => {
      streamCalls += 1;
      const frames = streamCalls === 1
        ? [{ schema_version: 1, cursor: 0, run_version: 4, type: "sync", payload: { run: runView } }]
        : [
            {
              schema_version: 1,
              cursor: 1,
              run_version: 2,
              type: "plan.created",
              payload: {
                plan_version: 1,
                strategy: "structured_model_plan",
                requirements: ["核验不可变引用"]
              }
            },
            {
              schema_version: 1,
              cursor: 2,
              run_version: 3,
              type: "evidence.added",
              payload: {
                evidence_id: "evidence-production-projection",
                source_title: "Production projection source",
                excerpt: "A durable event records this immutable evidence for assessment.",
                relation: "candidate",
                reference: {
                  source_id: 1,
                  revision_id: 2,
                  index_revision_id: 3,
                  chunk_id: 4,
                  content_hash: "a".repeat(64),
                  locator: { kind: "text", start_offset: 0, end_offset: 62 }
                }
              }
            },
            {
              schema_version: 1,
              cursor: 3,
              run_version: 3,
              type: "evidence.added",
              payload: {
                evidence_id: "evidence-production-excluded",
                source_title: "Excluded projection source",
                excerpt: "A candidate that was not selected for the final claim.",
                relation: "candidate",
                reference: {
                  source_id: 5,
                  revision_id: 6,
                  index_revision_id: 7,
                  chunk_id: 8,
                  content_hash: "b".repeat(64),
                  locator: { kind: "text", start_offset: 0, end_offset: 56 }
                }
              }
            },
            {
              schema_version: 1,
              cursor: 4,
              run_version: 4,
              type: "evidence.relation_changed",
              payload: {
                evidence_id: "evidence-production-projection",
                requirement_id: "requirement-production-projection",
                requirement_ordinal: 1,
                previous_relation: "candidate",
                relation: "supports",
                reason: "model_selected_support",
                method: "model_assessment"
              }
            },
            {
              schema_version: 1,
              cursor: 5,
              run_version: 4,
              type: "evidence.relation_changed",
              payload: {
                evidence_id: "evidence-production-excluded",
                requirement_id: "requirement-production-projection",
                requirement_ordinal: 1,
                previous_relation: "candidate",
                relation: "excluded",
                reason: "model_not_selected",
                method: "model_assessment"
              }
            },
            { schema_version: 1, cursor: 6, run_version: 4, type: "run.completed", payload: {} }
          ];
      const body = frames
        .map((frame) => `id: ${frame.cursor}\nevent: ${frame.type}\ndata: ${JSON.stringify(frame)}\n\n`)
        .join("");
      await route.fulfill({
        contentType: "text/event-stream",
        headers: { "access-control-allow-origin": "*" },
        body
      });
    });

    await page.goto(`/runs/${runId}`);

    await expect(page.getByTestId("research-plan")).toContainText("核验不可变引用");
    const ledger = page.getByTestId("evidence-ledger");
    await expect(ledger).toContainText("Production projection source");
    await expect(ledger).toContainText("支持结论");
    await expect(ledger).toContainText("已排除");
    await expect(ledger).toContainText("未选为该需求的支持证据");
    await expect(ledger).not.toContainText("候选证据");
    expect(streamCalls).toBe(2);
  });

  test("loads a production artifact and follows its claim to immutable evidence", async ({ page }) => {
    const artifactRequests: string[] = [];
    const evidenceRequests: string[] = [];
    await page.route("**/api/v1/artifacts/artifact-production-1", async (route) => {
      artifactRequests.push(route.request().url());
      await route.fulfill({
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({
          success: true,
          data: {
            schema_version: 1,
            id: "artifact-production-1",
            producing_run_id: "run-production-1",
            kind: "research_report",
            title: "Production evidence report",
            body_markdown: "A production report backed by immutable evidence.",
            status: "final",
            claims: [{
              id: "claim-production-1",
              ordinal: 1,
              text: "A supported production claim",
              kind: "factual",
              verification_status: "supported",
              evidence_ids: ["evidence-production-1"]
            }]
          },
          error: null,
          request_id: "request-artifact-detail"
        })
      });
    });
    await page.route("**/api/v1/evidence/evidence-production-1", async (route) => {
      evidenceRequests.push(route.request().url());
      await route.fulfill({
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({
          success: true,
          data: {
            schema_version: 1,
            id: "evidence-production-1",
            run_id: "run-production-1",
            source_id: 2,
            revision_id: 3,
            index_revision_id: 4,
            chunk_id: 5,
            source_type: "document",
            locator: { kind: "pdf_page", document_id: 12, page: 6 },
            revision_content_hash: "a".repeat(64),
            content_hash: "b".repeat(64),
            excerpt_preview: "supporting production excerpt",
            claim_ids: ["claim-production-1"]
          },
          error: null,
          request_id: "request-evidence-detail"
        })
      });
    });
    const fulfill = (data: unknown) => ({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: true, data, error: null, request_id: "immutable-document" })
    });
    await page.route("**/api/documents/12/chunks", async (route) => route.fulfill(fulfill([{
      id: 99,
      document_id: 12,
      source_id: 2,
      space_id: 1,
      target_type: "document",
      chunk_index: 0,
      content: "new active legacy content",
      content_preview: "new active legacy content",
      char_count: 25,
      page_number: 6,
      heading_path: null,
      section_title: null,
      token_count: 5,
      created_at: "2026-08-15T11:00:00Z"
    }])));
    await page.route("**/api/documents/12", async (route) => route.fulfill(fulfill({
      id: 12,
      space_id: 1,
      filename: "evidence.pdf",
      original_filename: "evidence.pdf",
      file_type: "pdf",
      content_type: "application/pdf",
      file_size: 1024,
      status: "ready",
      parse_status: "parsed",
      chunk_status: "completed",
      vector_status: "completed",
      processing_status: "completed",
      processing_progress: 100,
      retry_count: 0,
      content_hash: "f".repeat(64),
      title: "Versioned evidence",
      tags: [],
      source_type: "upload",
      summary: "Current document metadata",
      extractive_preview: null,
      ai_summary: null,
      error_message: null,
      chunk_count: 1,
      indexed_at: "2026-08-15T11:00:00Z",
      embedding_provider: "test",
      embedding_model: "test",
      embedding_dimensions: 8,
      embedding_fingerprint: "test::8",
      index_version: "v1",
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T11:00:00Z"
    })));
    await page.route("**/api/ingestion-jobs", async (route) => route.fulfill(fulfill([])));
    await page.route("**/api/media/sources/2", async (route) => route.fulfill(fulfill({
      id: 2,
      space_id: 1,
      document_id: 12,
      source_type: "document",
      title: "Versioned evidence",
      original_filename: "evidence.pdf",
      mime_type: "application/pdf",
      file_size: 1024,
      storage_path: null,
      content_hash: "f".repeat(64),
      status: "ready",
      language: "en",
      duration_ms: null,
      page_count: 6,
      width: null,
      height: null,
      metadata_json: "{}",
      active_revision_id: 6,
      latest_revision_id: 6,
      active_index_revision_id: 7,
      media_assets: [],
      revisions: [{
        id: 3,
        source_id: 2,
        revision_number: 1,
        status: "retired",
        parser_name: "pdf",
        parser_version: "1",
        content_hash: "a".repeat(64),
        chunk_count: 1,
        vector_count: 1,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T10:00:00Z",
        retired_at: "2026-08-15T11:00:00Z",
        index_revisions: [{ id: 4, source_id: 2, revision_id: 3, status: "retired", index_version: "v1" }],
        chunks: [{
          id: 5,
          source_id: 2,
          revision_id: 3,
          legacy_chunk_id: null,
          chunk_index: 0,
          modality: "text",
          source_type: "document",
          content_text: "retired canonical document evidence",
          content_hash: "b".repeat(64),
          search_text: "retired canonical document evidence",
          locator_json: JSON.stringify({ kind: "pdf_page", document_id: 12, page: 6 }),
          start_ms: null,
          end_ms: null,
          page_number: 6,
          slide_number: null,
          frame_id: null,
          status: "retired",
          qdrant_point_id: "retired-point",
          retired_at: "2026-08-15T11:00:00Z",
          created_at: "2026-08-15T10:00:00Z"
        }],
        transcript_segments: [],
        visual_frames: []
      }, {
        id: 6,
        source_id: 2,
        revision_number: 2,
        status: "active",
        parser_name: "pdf",
        parser_version: "1",
        content_hash: "c".repeat(64),
        chunk_count: 0,
        vector_count: 0,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T11:00:00Z",
        retired_at: null,
        index_revisions: [{ id: 7, source_id: 2, revision_id: 6, status: "active", index_version: "v1" }],
        chunks: [],
        transcript_segments: [],
        visual_frames: []
      }],
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T11:00:00Z"
    })));

    await page.goto("/artifacts/artifact-production-1");
    await expect(page.getByRole("heading", { name: "Production evidence report" })).toBeVisible();
    await expect(page.getByText("Production API · Verified Artifact")).toBeVisible();
    await page.getByRole("button", { name: "查看证据 1.1" }).click();

    const inspector = page.getByTestId("evidence-inspector");
    await expect(inspector).toContainText("supporting production excerpt");
    await expect(inspector).toContainText("Revision");
    await expect(inspector).toContainText("kind=pdf_page · document_id=12 · page=6");
    await expect(inspector.getByRole("link", { name: "打开固定来源" })).toHaveAttribute(
      "href",
      `/documents/12?page=6&source=2&revision=3&index_revision=4&chunk=5&hash=${"b".repeat(64)}&revision_hash=${"a".repeat(64)}`
    );
    await inspector.getByRole("link", { name: "打开固定来源" }).click();
    await expect(page.getByTestId("immutable-evidence-banner")).toContainText("历史固定证据 · Revision 3 / Chunk 5");
    await expect(page.getByText("retired canonical document evidence")).toBeVisible();
    await expect(page.getByText("new active legacy content")).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("immutable-evidence-banner")).toContainText("历史固定证据 · Revision 3 / Chunk 5");
    await expect(page.getByText("retired canonical document evidence")).toBeVisible();
    expect(artifactRequests).toHaveLength(1);
    expect(evidenceRequests).toHaveLength(1);
  });

  test("uses real spaces and sources in Workbench, then exposes their revision state in Library", async ({ page }) => {
    const artifactCatalogRequests: string[] = [];
    const spaces = [
      { id: 1, name: "Alpha research", description: "Alpha scope", created_at: "2026-08-15T10:00:00Z", updated_at: "2026-08-15T10:00:00Z" },
      { id: 2, name: "Beta research", description: "Beta scope", created_at: "2026-08-15T10:00:00Z", updated_at: "2026-08-15T10:00:00Z" }
    ];
    const source = (id: number, spaceId: number, title: string, revisionId: number) => ({
      id,
      space_id: spaceId,
      document_id: null,
      source_type: "document",
      title,
      original_filename: title,
      mime_type: "application/pdf",
      file_size: 12_000,
      storage_path: null,
      content_hash: "c".repeat(64),
      status: "active",
      language: "zh-CN",
      duration_ms: null,
      page_count: 4,
      width: null,
      height: null,
      metadata_json: "{}",
      active_revision_id: revisionId,
      latest_revision_id: revisionId,
      media_assets: [],
      revisions: [{
        id: revisionId,
        source_id: id,
        revision_number: 1,
        status: "active",
        parser_name: "pdf-parser",
        parser_version: "1",
        chunk_count: 12,
        vector_count: 12,
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
    const sources = [source(11, 1, "Alpha evidence.pdf", 101), source(22, 2, "Beta evidence.pdf", 202)];
    await page.route("**/api/knowledge-spaces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({ success: true, data: spaces, error: null, request_id: "request-spaces" })
      });
    });
    await page.route("**/api/media/sources", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({ success: true, data: sources, error: null, request_id: "request-sources" })
      });
    });
    await page.route("**/api/v1/artifacts**", async (route) => {
      artifactCatalogRequests.push(route.request().url());
      await route.fulfill({
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({
          success: true,
          data: {
            schema_version: 1,
            items: [{
              id: "artifact-source-11",
              producing_run_id: "run-source-11",
              kind: "research_report",
              title: "Alpha derived report",
              status: "final"
            }]
          },
          error: null,
          request_id: "request-source-artifacts"
        })
      });
    });

    await page.goto("/workbench");
    const spaceSelect = page.getByLabel("知识空间 *");
    await expect(spaceSelect).toHaveValue("1");
    await page.getByLabel("选择 Alpha evidence.pdf").check();
    await expect(page.getByText("已固定 1 个来源")).toBeVisible();
    await spaceSelect.selectOption("2");
    await expect(page.getByLabel("选择 Beta evidence.pdf")).toBeVisible();
    await spaceSelect.selectOption("1");
    await expect(page.getByLabel("选择 Alpha evidence.pdf")).not.toBeChecked();

    await page.goto("/library");
    await expect(page.getByRole("heading", { name: "统一证据资料库" })).toBeVisible();
    const alphaCard = page.getByRole("article").filter({ hasText: "Alpha evidence.pdf" });
    await expect(alphaCard).toContainText("Revision 101");
    await expect(alphaCard).toContainText("passed · 12 vectors");
    await expect(alphaCard).toContainText("active");
    await expect(alphaCard.getByRole("link", { name: "查看来源详情" })).toHaveAttribute("href", "/library?source=11");
    const derivedArtifacts = alphaCard.getByRole("link", { name: "查看 Alpha evidence.pdf 的派生成果" });
    await expect(derivedArtifacts).toHaveAttribute("href", "/artifacts?source_id=11");
    await derivedArtifacts.click();

    await expect(page).toHaveURL(/\/artifacts\?source_id=11$/);
    await expect(page.getByRole("heading", { name: "来源派生成果" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Alpha derived report" })).toBeVisible();
    expect(new URL(artifactCatalogRequests[0]).searchParams.get("source_id")).toBe("11");
  });

  test("opens a backend code_repository Library source in a consumable real code viewer", async ({ page }) => {
    const revisionHash = "a".repeat(64);
    const chunkHash = "b".repeat(64);
    const codeSource = {
      id: 44,
      space_id: 1,
      document_id: null,
      source_type: "code_repository",
      title: "Evidence Agent repository",
      original_filename: "Evidence Agent repository",
      mime_type: "application/x-git",
      file_size: 42_000,
      storage_path: null,
      content_hash: revisionHash,
      status: "active",
      language: "python",
      duration_ms: null,
      page_count: null,
      width: null,
      height: null,
      metadata_json: "{}",
      active_revision_id: 51,
      latest_revision_id: 51,
      active_index_revision_id: 71,
      media_assets: [],
      revisions: [{
        id: 51,
        source_id: 44,
        revision_number: 1,
        status: "active",
        parser_name: "code_repository_service",
        parser_version: "1",
        content_hash: revisionHash,
        chunk_count: 1,
        vector_count: 1,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T10:00:00Z",
        retired_at: null,
        index_revisions: [{ id: 71, source_id: 44, revision_id: 51, status: "active", index_version: "v1" }],
        chunks: [{
          id: 61,
          source_id: 44,
          revision_id: 51,
          chunk_index: 0,
          modality: "code_file",
          source_type: "code_repository",
          content_text: "File: backend/app/worker.py\nLines: 40-41\nLanguage: python\n\ndef advance():\n    return True",
          content_hash: chunkHash,
          search_text: "advance worker",
          locator_json: JSON.stringify({
            kind: "code_range",
            file_path: "backend/app/worker.py",
            line_start: 40,
            line_end: 41,
            language: "python"
          }),
          start_ms: null,
          end_ms: null,
          page_number: null,
          slide_number: null,
          frame_id: null,
          status: "active",
          qdrant_point_id: "code-point-61",
          retired_at: null,
          created_at: "2026-08-15T10:00:00Z"
        }],
        transcript_segments: [],
        visual_frames: []
      }],
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T10:00:00Z"
    };
    const envelope = (data: unknown, requestId: string) => ({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: true, data, error: null, request_id: requestId })
    });
    await page.route("**/api/knowledge-spaces", async (route) => route.fulfill(envelope([{
      id: 1,
      name: "Engineering",
      description: "Code evidence",
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T10:00:00Z"
    }], "code-spaces")));
    await page.route("**/api/media/sources", async (route) => route.fulfill(envelope([codeSource], "code-sources")));
    await page.route("**/api/code-repositories/44", async (route) => route.fulfill(envelope(codeSource, "code-source-detail")));
    await page.route("**/api/code-repositories", async (route) => route.fulfill(envelope([codeSource], "code-source-list")));

    await page.goto("/library");
    const card = page.getByRole("article").filter({ hasText: "Evidence Agent repository" });
    await expect(card).toContainText("代码仓库");
    const sourceDetail = card.getByRole("link", { name: "查看来源详情" });
    await expect(sourceDetail).toHaveAttribute("href", "/code?source=44");
    await sourceDetail.click();

    await expect(page).toHaveURL(/\/code\?source=44$/);
    const detail = page.getByTestId("code-source-detail");
    await expect(detail).toContainText("code_repository");
    await expect(detail).toContainText("backend/app/worker.py");
    await detail.getByRole("link", { name: /backend\/app\/worker.py/ }).click();
    await expect(page.getByTestId("code-citation-viewer")).toContainText("def advance():");
    await expect(page.getByLabel("backend/app/worker.py 代码引用").locator("[aria-current='location']")).toHaveCount(2);
  });

  test("keeps one active nav item and remains operable at a mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/workbench?demo=1");

    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();
    await expect(page.locator(".nav-item[aria-current='page']")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "打开导航" })).toBeVisible();
    await page.getByRole("button", { name: "打开导航" }).click();
    await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
    await expect(page.getByLabel("研究目标")).toHaveAttribute("name", "goal");

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
