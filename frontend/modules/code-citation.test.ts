import { describe, expect, it } from "vitest";

import type { SourceItem } from "@/types/api";
import { buildCodeExcerpt, buildPinnedCodeExcerpt, listCodeLocations } from "./code-citation";

const revisionHash = "a".repeat(64);
const chunkHash = "b".repeat(64);

const source: SourceItem = {
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
  active_revision_id: 21,
  latest_revision_id: 21,
  media_assets: [],
  revisions: [{
    id: 21,
    source_id: 4,
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
    index_revisions: [{ id: 30, source_id: 4, revision_id: 21, status: "active", index_version: "v1" }],
    chunks: [{
      id: 31,
      source_id: 4,
      revision_id: 21,
      chunk_index: 0,
      modality: "code_file",
      source_type: "code_repository",
      content_text: "File: backend/app/api/router.py\nLines: 10-13\nLanguage: python\n\ndef configure():\n    router = APIRouter()\n    include_routes(router)\n    return router",
      content_hash: chunkHash,
      search_text: "configure router",
      locator_json: JSON.stringify({
        kind: "code_range",
        file_path: "backend/app/api/router.py",
        line_start: 10,
        line_end: 13,
        language: "python"
      }),
      start_ms: null,
      end_ms: null,
      page_number: null,
      slide_number: null,
      frame_id: null,
      status: "active",
      qdrant_point_id: "point-31",
      retired_at: null,
      created_at: "2026-08-15T10:00:00Z"
    }],
    transcript_segments: [],
    visual_frames: []
  }],
  created_at: "2026-08-15T10:00:00Z",
  updated_at: "2026-08-15T10:00:00Z"
};

describe("buildCodeExcerpt", () => {
  it("lists real files and line ranges for a code_repository source detail", () => {
    expect(listCodeLocations(source)).toEqual([
      {
        chunkId: 31,
        filePath: "backend/app/api/router.py",
        language: "python",
        lineStart: 10,
        lineEnd: 13,
        revisionId: 21
      }
    ]);
  });

  it("extracts actual code lines and semantically marks the requested range", () => {
    const excerpt = buildCodeExcerpt(source, "backend\\app\\api\\router.py", 11, 12);

    expect(excerpt).toMatchObject({ revisionId: 21, filePath: "backend/app/api/router.py", exact: true });
    expect(excerpt?.lines).toEqual([
      { number: 10, text: "def configure():", highlighted: false },
      { number: 11, text: "    router = APIRouter()", highlighted: true },
      { number: 12, text: "    include_routes(router)", highlighted: true },
      { number: 13, text: "    return router", highlighted: false }
    ]);
  });

  it("returns null instead of substituting an unrelated file", () => {
    expect(buildCodeExcerpt(source, "backend/app/missing.py", 1, 1)).toBeNull();
  });

  it("opens the exact retired revision and chunk after active switches", () => {
    const retiredRevision = {
      ...source.revisions[0],
      status: "retired",
      retired_at: "2026-08-15T11:00:00Z",
      index_revisions: [{ id: 30, source_id: 4, revision_id: 21, status: "retired", index_version: "v1" }],
      chunks: source.revisions[0].chunks.map((chunk) => ({ ...chunk, status: "retired" }))
    };
    const switchedSource: SourceItem = {
      ...source,
      active_revision_id: 22,
      latest_revision_id: 22,
      active_index_revision_id: 40,
      revisions: [
        retiredRevision,
        {
          ...retiredRevision,
          id: 22,
          revision_number: 2,
          status: "active",
          content_hash: "c".repeat(64),
          retired_at: null,
          index_revisions: [{ id: 40, source_id: 4, revision_id: 22, status: "active", index_version: "v1" }],
          chunks: []
        }
      ]
    };

    const excerpt = buildPinnedCodeExcerpt(switchedSource, {
      pin: {
        sourceId: 4,
        revisionId: 21,
        indexRevisionId: 30,
        chunkId: 31,
        contentHash: chunkHash,
        revisionContentHash: revisionHash
      },
      filePath: "backend/app/api/router.py",
      lineStart: 11,
      lineEnd: 12
    });

    expect(excerpt).toMatchObject({ revisionId: 21, chunkId: 31, historical: true, exact: true });
    expect(excerpt?.lines.filter((line) => line.highlighted).map((line) => line.number)).toEqual([11, 12]);
  });

  it("fails closed instead of falling back when any immutable code coordinate drifts", () => {
    const request = {
      pin: {
        sourceId: 4,
        revisionId: 21,
        indexRevisionId: 30,
        chunkId: 31,
        contentHash: chunkHash,
        revisionContentHash: revisionHash
      },
      filePath: "backend/app/api/router.py",
      lineStart: 11,
      lineEnd: 12
    };

    expect(buildPinnedCodeExcerpt(source, { ...request, pin: { ...request.pin, contentHash: "0".repeat(64) } })).toBeNull();
    expect(buildPinnedCodeExcerpt(source, { ...request, pin: { ...request.pin, chunkId: 999 } })).toBeNull();
    expect(buildPinnedCodeExcerpt(source, { ...request, filePath: "backend/app/other.py" })).toBeNull();
    expect(buildPinnedCodeExcerpt(source, { ...request, lineStart: 100, lineEnd: 100 })).toBeNull();
  });
});
