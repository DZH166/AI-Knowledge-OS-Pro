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

  test("media citation renders the exact historical revision, chunk, and timestamp", async ({ page }) => {
    const envelope = (data: unknown) => ({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: true, data, error: null, request_id: "pinned-media" })
    });
    const chunk = (id: number, revisionId: number, content: string, hash: string, status: string) => ({
      id,
      source_id: 8,
      revision_id: revisionId,
      legacy_chunk_id: null,
      chunk_index: 0,
      modality: "audio_transcript",
      source_type: "audio",
      content_text: content,
      content_hash: hash,
      search_text: content,
      locator_json: JSON.stringify({ kind: "media_time", start_ms: 0, end_ms: 3000 }),
      start_ms: 0,
      end_ms: 3000,
      page_number: null,
      slide_number: null,
      frame_id: null,
      status,
      qdrant_point_id: `point-${id}`,
      retired_at: status === "retired" ? "2026-08-15T11:00:00Z" : null,
      created_at: "2026-08-15T10:00:00Z"
    });
    const segment = (id: number, revisionId: number, text: string) => ({
      id,
      source_id: 8,
      revision_id: revisionId,
      segment_index: 0,
      start_ms: 0,
      end_ms: 3000,
      speaker: null,
      language: "en",
      text,
      confidence: 99,
      created_at: "2026-08-15T10:00:00Z"
    });
    const source = {
      id: 8,
      space_id: 1,
      document_id: null,
      source_type: "audio",
      title: "Versioned interview",
      original_filename: "interview.mp3",
      mime_type: "audio/mpeg",
      file_size: 100,
      storage_path: null,
      content_hash: "f".repeat(64),
      status: "ready",
      language: "en",
      duration_ms: 30_000,
      page_count: null,
      width: null,
      height: null,
      metadata_json: "{}",
      active_revision_id: 12,
      latest_revision_id: 12,
      active_index_revision_id: 15,
      media_assets: [],
      revisions: [{
        id: 11,
        source_id: 8,
        revision_number: 1,
        status: "retired",
        parser_name: "transcriber",
        parser_version: "1",
        content_hash: "e".repeat(64),
        chunk_count: 1,
        vector_count: 1,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T10:00:00Z",
        retired_at: "2026-08-15T11:00:00Z",
        index_revisions: [{ id: 14, source_id: 8, revision_id: 11, status: "retired", index_version: "v1" }],
        chunks: [chunk(13, 11, "retired timestamp evidence", "f".repeat(64), "retired")],
        transcript_segments: [segment(101, 11, "retired timestamp evidence")],
        visual_frames: []
      }, {
        id: 12,
        source_id: 8,
        revision_number: 2,
        status: "active",
        parser_name: "transcriber",
        parser_version: "1",
        content_hash: "c".repeat(64),
        chunk_count: 1,
        vector_count: 1,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T11:00:00Z",
        retired_at: null,
        index_revisions: [{ id: 15, source_id: 8, revision_id: 12, status: "active", index_version: "v1" }],
        chunks: [chunk(16, 12, "new active timestamp content", "d".repeat(64), "active")],
        transcript_segments: [segment(102, 12, "new active timestamp content")],
        visual_frames: []
      }],
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T11:00:00Z"
    };
    await page.route("**/api/media/sources/8/file", async (route) => route.fulfill({ status: 200, contentType: "audio/mpeg", body: "" }));
    await page.route("**/api/media/sources/8", async (route) => route.fulfill(envelope(source)));
    await page.route("**/api/errors**", async (route) => route.fulfill(envelope([])));

    await page.goto(`/media/sources/8?t=0&source=8&revision=11&index_revision=14&chunk=13&hash=${"f".repeat(64)}&revision_hash=${"e".repeat(64)}`);

    await expect(page.getByTestId("immutable-evidence-banner")).toContainText("历史固定证据 · Revision 11 / Chunk 13");
    await expect(page.locator("body")).toContainText("retired timestamp evidence");
    await expect(page.locator("body")).not.toContainText("new active timestamp content");
    await expect(page.getByTestId("audio-player")).toBeVisible();
    const target = page.locator("[data-testid='transcript-segment'][data-active='true']");
    await expect(target).toContainText("retired timestamp evidence");
    await expect(target).toHaveAttribute("data-citation-target", "true");

    await page.goto(`/media/sources/8?t=not-a-timestamp&source=8&revision=11&index_revision=14&chunk=13&hash=${"f".repeat(64)}&revision_hash=${"e".repeat(64)}`);
    await expect(page.getByText("固定媒体证据校验失败")).toBeVisible();
    await expect(page.locator("body")).toContainText("媒体时间参数 t 必须是非负整数");
    await expect(page.getByTestId("audio-player")).toHaveCount(0);
  });

  test("video OCR citation seeks a retired pinned timestamp without a transcript", async ({ page }) => {
    const envelope = (data: unknown) => ({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: true, data, error: null, request_id: "pinned-video-ocr" })
    });
    const retiredChunk = {
      id: 51,
      source_id: 9,
      revision_id: 31,
      legacy_chunk_id: null,
      chunk_index: 0,
      modality: "video_frame_text",
      source_type: "video",
      content_text: "retired OCR evidence at seven seconds",
      content_hash: "7".repeat(64),
      search_text: "retired OCR evidence",
      locator_json: JSON.stringify({ kind: "video_frame", timestamp_ms: 7000 }),
      start_ms: null,
      end_ms: null,
      page_number: null,
      slide_number: null,
      frame_id: 71,
      status: "retired",
      qdrant_point_id: "point-51",
      retired_at: "2026-08-15T11:00:00Z",
      created_at: "2026-08-15T10:00:00Z"
    };
    const source = {
      id: 9,
      space_id: 1,
      document_id: null,
      source_type: "video",
      title: "Versioned screen recording",
      original_filename: "recording.mp4",
      mime_type: "video/mp4",
      file_size: 100,
      storage_path: null,
      content_hash: "9".repeat(64),
      status: "ready",
      language: "en",
      duration_ms: 10_000,
      page_count: null,
      width: 1280,
      height: 720,
      metadata_json: "{}",
      active_revision_id: 32,
      latest_revision_id: 32,
      active_index_revision_id: 62,
      media_assets: [],
      revisions: [{
        id: 31,
        source_id: 9,
        revision_number: 1,
        status: "retired",
        parser_name: "video_pipeline",
        parser_version: "1",
        content_hash: "8".repeat(64),
        chunk_count: 1,
        vector_count: 1,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T10:00:00Z",
        retired_at: "2026-08-15T11:00:00Z",
        index_revisions: [{ id: 61, source_id: 9, revision_id: 31, status: "retired", index_version: "v1" }],
        chunks: [retiredChunk],
        transcript_segments: [],
        visual_frames: []
      }, {
        id: 32,
        source_id: 9,
        revision_number: 2,
        status: "active",
        parser_name: "video_pipeline",
        parser_version: "1",
        content_hash: "6".repeat(64),
        chunk_count: 0,
        vector_count: 0,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T11:00:00Z",
        retired_at: null,
        index_revisions: [{ id: 62, source_id: 9, revision_id: 32, status: "active", index_version: "v1" }],
        chunks: [],
        transcript_segments: [],
        visual_frames: []
      }],
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T11:00:00Z"
    };
    const tenSecondVideo = Buffer.from(
      "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAANIbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAJxAAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAnN0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAJxAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAABAAAAAQAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAACcQAAAAAAABAAAAAAHrbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAABAAAACgABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABlm1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAVZzdGJsAAAAtnN0c2QAAAAAAAAAAQAAAKZhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAABAAEABIAAAASAAAAAAAAAABFUxhdmM2MS4xOS4xMDAgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAALGF2Y0MBQsAK/+EAFWdCwAraewEQAAADABAAAAMAIPEiagEABGjOD8gAAAAQcGFzcAAAAAEAAAABAAAAFGJ0cnQAAAAAAAACLAAAAiwAAAAYc3R0cwAAAAAAAAABAAAACgAAQAAAAAAUc3RzcwAAAAAAAAABAAAAAQAAABxzdHNjAAAAAAAAAAEAAAABAAAACgAAAAEAAAA8c3RzegAAAAAAAAAAAAAACgAAAmcAAAAJAAAACQAAAAkAAAAJAAAACQAAAAkAAAAJAAAACQAAAAkAAAAUc3RjbwAAAAAAAAABAAADeAAAAGF1ZHRhAAAAWW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAALGlsc3QAAAAkqXRvbwAAABxkYXRhAAAAAQAAAABMYXZmNjEuNy4xMDAAAAAIZnJlZQAAAsBtZGF0AAACVQYF//9R3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzE5MiBjMjRlMDZjIC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyNCAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTAgcmVmPTEgZGVibG9jaz0wOi0zOi0zIGFuYWx5c2U9MDowIG1lPWRpYSBzdWJtZT0wIHBzeT0xIHBzeV9yZD0yLjAwOjAuNzAgbWl4ZWRfcmVmPTAgbWVfcmFuZ2U9MTYgY2hyb21hX21lPTEgdHJlbGxpcz0wIDh4OGRjdD0wIGNxbT0wIGRlYWR6b25lPTIxLDExIGZhc3RfcHNraXA9MSBjaHJvbWFfcXBfb2Zmc2V0PTAgdGhyZWFkcz0xIGxvb2thaGVhZF90aHJlYWRzPTEgc2xpY2VkX3RocmVhZHM9MCBucj0wIGRlY2ltYXRlPTEgaW50ZXJsYWNlZD0wIGJsdXJheV9jb21wYXQ9MCBjb25zdHJhaW5lZF9pbnRyYT0wIGJmcmFtZXM9MCB3ZWlnaHRwPTAga2V5aW50PTI1MCBrZXlpbnRfbWluPTEgc2NlbmVjdXQ9MCBpbnRyYV9yZWZyZXNoPTAgcmM9Y3JmIG1idHJlZT0wIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTAAgAAAAApliIQ6JigACQLgAAAABUGaIBSlAAAABUGaQBWlAAAABUGaYBWlAAAABUGagBWlAAAABUGaoBWlAAAABUGawBWlAAAABUGa4BalAAAABUGbABalAAAABUGbIBal",
      "base64"
    );

    await page.route("**/api/media/sources/9/file", async (route) => {
      const range = route.request().headers().range;
      if (!range) {
        await route.fulfill({
          status: 200,
          contentType: "video/mp4",
          headers: { "accept-ranges": "bytes", "content-length": String(tenSecondVideo.length) },
          body: tenSecondVideo
        });
        return;
      }
      const match = /^bytes=(\d+)-(\d*)$/.exec(range);
      const start = match ? Number(match[1]) : 0;
      const requestedEnd = match?.[2] ? Number(match[2]) : tenSecondVideo.length - 1;
      const end = Math.min(requestedEnd, tenSecondVideo.length - 1);
      const body = tenSecondVideo.subarray(start, end + 1);
      await route.fulfill({
        status: 206,
        contentType: "video/mp4",
        headers: {
          "accept-ranges": "bytes",
          "content-length": String(body.length),
          "content-range": `bytes ${start}-${end}/${tenSecondVideo.length}`
        },
        body
      });
    });
    await page.route("**/api/media/sources/9", async (route) => route.fulfill(envelope(source)));
    await page.route("**/api/errors**", async (route) => route.fulfill(envelope([])));

    await page.goto(`/media/sources/9?t=7000&source=9&revision=31&index_revision=61&chunk=51&hash=${"7".repeat(64)}&revision_hash=${"8".repeat(64)}`);

    await expect(page.getByTestId("immutable-evidence-banner")).toContainText("历史固定证据 · Revision 31 / Chunk 51");
    const player = page.getByTestId("video-player");
    await expect(player).toBeVisible();
    await expect.poll(() => player.evaluate((media: HTMLVideoElement) => media.currentTime)).toBeGreaterThan(6.9);
    await expect.poll(() => player.evaluate((media: HTMLVideoElement) => media.currentTime)).toBeLessThan(7.1);
    const target = page.locator("#chunk-51");
    await expect(target).toContainText("retired OCR evidence at seven seconds");
    await expect(target).toHaveAttribute("data-citation-target", "true");
    await expect(page.getByTestId("transcript-timeline")).toContainText("No transcript segments");
  });

  test("code citation keeps a retired pinned chunk after the active revision switches", async ({ page }) => {
    const source = {
      id: 4,
      space_id: 1,
      document_id: null,
      source_type: "code_repository",
      title: "AIKOS",
      original_filename: "AIKOS",
      mime_type: "application/x-git",
      file_size: 0,
      storage_path: null,
      content_hash: "a".repeat(64),
      status: "active",
      language: "python",
      duration_ms: null,
      page_count: null,
      width: null,
      height: null,
      metadata_json: "{}",
      active_revision_id: 22,
      latest_revision_id: 22,
      active_index_revision_id: 40,
      media_assets: [],
      revisions: [{
        id: 21,
        source_id: 4,
        revision_number: 1,
        status: "retired",
        parser_name: "code_repository_service",
        parser_version: "1",
        content_hash: "a".repeat(64),
        chunk_count: 1,
        vector_count: 1,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T10:00:00Z",
        retired_at: "2026-08-15T11:00:00Z",
        index_revisions: [{ id: 30, source_id: 4, revision_id: 21, status: "retired", index_version: "v1" }],
        chunks: [{
          id: 31,
          source_id: 4,
          revision_id: 21,
          chunk_index: 0,
          modality: "code_file",
          source_type: "code_repository",
          content_text: "File: backend/app/api/router.py\nLines: 1-6\nLanguage: python\n\nfrom fastapi import APIRouter\n\nrouter = APIRouter()\ndef include_routes():\n    router.include_router(api_router)\n    return router",
          content_hash: "b".repeat(64),
          search_text: "include router",
          locator_json: JSON.stringify({ kind: "code_range", file_path: "backend/app/api/router.py", line_start: 1, line_end: 6, language: "python" }),
          start_ms: null,
          end_ms: null,
          page_number: null,
          slide_number: null,
          frame_id: null,
          status: "retired",
          qdrant_point_id: "point-31",
          retired_at: "2026-08-15T11:00:00Z",
          created_at: "2026-08-15T10:00:00Z"
        }],
        transcript_segments: [],
        visual_frames: []
      }, {
        id: 22,
        source_id: 4,
        revision_number: 2,
        status: "active",
        parser_name: "code_repository_service",
        parser_version: "1",
        content_hash: "c".repeat(64),
        chunk_count: 0,
        vector_count: 0,
        validation_status: "passed",
        error_message: null,
        metadata_json: "{}",
        activated_at: "2026-08-15T11:00:00Z",
        retired_at: null,
        index_revisions: [{ id: 40, source_id: 4, revision_id: 22, status: "active", index_version: "v1" }],
        chunks: [],
        transcript_segments: [],
        visual_frames: []
      }],
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T10:00:00Z"
    };
    const fulfill = (data: unknown) => ({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ success: true, data, error: null, request_id: "citation-jump" })
    });
    await page.route("**/api/knowledge-spaces", async (route) => route.fulfill(fulfill([
      { id: 1, name: "Architecture", description: null, created_at: "2026-08-15T10:00:00Z", updated_at: "2026-08-15T10:00:00Z" }
    ])));
    await page.route("**/api/code-repositories", async (route) => route.fulfill(fulfill([source])));
    await page.route("**/api/code-repositories/4", async (route) => route.fulfill(fulfill(source)));

    await page.goto(`/code?source=4&revision=21&index_revision=30&chunk=31&hash=${"b".repeat(64)}&revision_hash=${"a".repeat(64)}&file=backend/app/api/router.py&line=4&line_end=4`);
    await expect(page.getByTestId("code-citation-viewer")).toContainText("Revision 21");
    await expect(page.getByTestId("code-citation-viewer")).toContainText("历史固定证据");
    const target = page.locator("#code-citation-line-4");
    await expect(target).toContainText("def include_routes():");
    await expect(target).toHaveAttribute("data-citation-target", "true");
    await expect(target).toHaveAttribute("aria-current", "location");
    await expect(target).toBeFocused();
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
