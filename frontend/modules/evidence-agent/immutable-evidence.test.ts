import { describe, expect, it } from "vitest";

import type { SourceItem } from "@/types/api";
import {
  matchesImmutableMediaTime,
  parseImmutableEvidencePin,
  parseMediaTimestamp,
  resolveImmutableEvidence
} from "./immutable-evidence";

const chunkHash = "b".repeat(64);
const retiredRevisionHash = "a".repeat(64);

const source: SourceItem = {
  id: 4,
  space_id: 1,
  document_id: 12,
  source_type: "document",
  title: "Pinned document",
  original_filename: "pinned.md",
  mime_type: "text/markdown",
  file_size: 10,
  storage_path: null,
  content_hash: "f".repeat(64),
  status: "ready",
  language: "zh-CN",
  duration_ms: null,
  page_count: null,
  width: null,
  height: null,
  metadata_json: "{}",
  active_revision_id: 22,
  latest_revision_id: 22,
  active_index_revision_id: 32,
  media_assets: [],
  revisions: [
    {
      id: 21,
      source_id: 4,
      revision_number: 1,
      status: "retired",
      parser_name: "test",
      parser_version: "1",
      content_hash: retiredRevisionHash,
      chunk_count: 1,
      vector_count: 1,
      validation_status: "passed",
      error_message: null,
      metadata_json: "{}",
      activated_at: "2026-08-15T10:00:00Z",
      retired_at: "2026-08-15T11:00:00Z",
      index_revisions: [{ id: 31, source_id: 4, revision_id: 21, status: "retired", index_version: "v1" }],
      chunks: [{
        id: 41,
        source_id: 4,
        revision_id: 21,
        legacy_chunk_id: null,
        chunk_index: 0,
        modality: "text",
        source_type: "document",
        content_text: "retired canonical evidence",
        content_hash: chunkHash,
        search_text: "retired canonical evidence",
        locator_json: JSON.stringify({ kind: "document_page", document_id: 12, page_number: 1 }),
        start_ms: null,
        end_ms: null,
        page_number: 1,
        slide_number: null,
        frame_id: null,
        status: "retired",
        qdrant_point_id: "old-point",
        retired_at: "2026-08-15T11:00:00Z",
        created_at: "2026-08-15T10:00:00Z"
      }],
      transcript_segments: [],
      visual_frames: []
    },
    {
      id: 22,
      source_id: 4,
      revision_number: 2,
      status: "active",
      parser_name: "test",
      parser_version: "1",
      content_hash: "c".repeat(64),
      chunk_count: 0,
      vector_count: 0,
      validation_status: "passed",
      error_message: null,
      metadata_json: "{}",
      activated_at: "2026-08-15T11:00:00Z",
      retired_at: null,
      index_revisions: [{ id: 32, source_id: 4, revision_id: 22, status: "active", index_version: "v1" }],
      chunks: [],
      transcript_segments: [],
      visual_frames: []
    }
  ],
  created_at: "2026-08-15T10:00:00Z",
  updated_at: "2026-08-15T11:00:00Z"
};

describe("immutable evidence pins", () => {
  it("parses a complete immutable locator but leaves legacy current-view URLs alone", () => {
    const parsed = parseImmutableEvidencePin(new URLSearchParams(
      `source=4&revision=21&index_revision=31&chunk=41&hash=${chunkHash}&revision_hash=${retiredRevisionHash}`
    ));

    expect(parsed).toEqual({
      mode: "pinned",
      pin: {
        sourceId: 4,
        revisionId: 21,
        indexRevisionId: 31,
        chunkId: 41,
        contentHash: chunkHash,
        revisionContentHash: retiredRevisionHash
      }
    });
    expect(parseImmutableEvidencePin(new URLSearchParams("source=4&chunk=41"))).toEqual({ mode: "current" });
  });

  it("resolves a retired revision after active switches without falling forward", () => {
    const result = resolveImmutableEvidence(source, {
      sourceId: 4,
      revisionId: 21,
      indexRevisionId: 31,
      chunkId: 41,
      contentHash: chunkHash,
      revisionContentHash: retiredRevisionHash
    });

    expect(result).toMatchObject({ ok: true, historical: true });
    if (result.ok) {
      expect(result.revision.id).toBe(21);
      expect(result.chunk.id).toBe(41);
      expect(result.chunk.content_text).toBe("retired canonical evidence");
    }
  });

  it("fails closed on revision, index, chunk, or hash drift", () => {
    const base = {
      sourceId: 4,
      revisionId: 21,
      indexRevisionId: 31,
      chunkId: 41,
      contentHash: chunkHash,
      revisionContentHash: retiredRevisionHash
    };

    expect(resolveImmutableEvidence(source, { ...base, revisionId: 22 }).ok).toBe(false);
    expect(resolveImmutableEvidence(source, { ...base, indexRevisionId: 32 }).ok).toBe(false);
    expect(resolveImmutableEvidence(source, { ...base, chunkId: 999 }).ok).toBe(false);
    expect(resolveImmutableEvidence(source, { ...base, contentHash: "0".repeat(64) }).ok).toBe(false);
    expect(resolveImmutableEvidence(source, { ...base, revisionContentHash: "0".repeat(64) }).ok).toBe(false);
  });

  it("accepts only a timestamp inside the pinned canonical media locator", () => {
    const mediaChunk = {
      ...source.revisions[0].chunks[0],
      start_ms: 9_000,
      end_ms: 12_000,
      locator_json: JSON.stringify({ kind: "media_time", start_ms: 9_000, end_ms: 12_000 })
    };

    expect(matchesImmutableMediaTime(mediaChunk, "9000")).toBe(true);
    expect(matchesImmutableMediaTime(mediaChunk, "12000")).toBe(true);
    expect(matchesImmutableMediaTime(mediaChunk, "12001")).toBe(false);
    expect(matchesImmutableMediaTime(mediaChunk, null)).toBe(false);
    expect(matchesImmutableMediaTime(mediaChunk, "9.5")).toBe(false);
  });

  it("distinguishes a zero timestamp from an absent or malformed timestamp", () => {
    expect(parseMediaTimestamp("0")).toEqual({ mode: "valid", milliseconds: 0 });
    expect(parseMediaTimestamp("9000")).toEqual({ mode: "valid", milliseconds: 9000 });
    expect(parseMediaTimestamp(null)).toEqual({ mode: "absent" });
    expect(parseMediaTimestamp("")).toMatchObject({ mode: "invalid" });
    expect(parseMediaTimestamp("-1")).toMatchObject({ mode: "invalid" });
    expect(parseMediaTimestamp("1.5")).toMatchObject({ mode: "invalid" });
    expect(parseMediaTimestamp("Infinity")).toMatchObject({ mode: "invalid" });
    expect(parseMediaTimestamp(String(Number.MAX_SAFE_INTEGER + 1))).toMatchObject({ mode: "invalid" });
  });
});
