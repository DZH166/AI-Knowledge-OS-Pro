import { describe, expect, it } from "vitest";

import { catalogSourceHref, evidenceSourceHref } from "./source-locator";

describe("evidenceSourceHref", () => {
  it("routes a canonical document locator to the pinned document page", () => {
    expect(
      evidenceSourceHref({
        sourceId: 2,
        revisionId: 3,
        indexRevisionId: 4,
        chunkId: 5,
        contentHash: "b".repeat(64),
        revisionContentHash: "a".repeat(64),
        sourceType: "document",
        locator: { kind: "document_page", document_id: 12, page_number: 6 }
      })
    ).toBe(
      `/documents/12?page=6&source=2&revision=3&index_revision=4&chunk=5&hash=${"b".repeat(64)}&revision_hash=${"a".repeat(64)}`
    );
  });

  it("routes code evidence to the real code viewer with exact lines", () => {
    expect(
      evidenceSourceHref({
        sourceId: 4,
        revisionId: 7,
        indexRevisionId: 8,
        chunkId: 9,
        contentHash: "d".repeat(64),
        revisionContentHash: "c".repeat(64),
        sourceType: "code",
        locator: { kind: "code_range", file_path: "backend/app/main.py", line_start: 20, line_end: 24 }
      })
    ).toBe(
      `/code?source=4&revision=7&index_revision=8&chunk=9&hash=${"d".repeat(64)}&revision_hash=${"c".repeat(64)}&file=backend%2Fapp%2Fmain.py&line=20&line_end=24`
    );
  });

  it("recognizes the backend code_repository discriminator without relying on the locator kind", () => {
    expect(
      evidenceSourceHref({
        sourceId: 5,
        revisionId: 7,
        chunkId: 9,
        contentHash: "d".repeat(64),
        sourceType: "code_repository",
        locator: { kind: "text", file_path: "backend/app/main.py", line_start: 20 }
      })
    ).toBe(`/code?source=5&revision=7&chunk=9&hash=${"d".repeat(64)}&file=backend%2Fapp%2Fmain.py&line=20`);
  });

  it("routes media evidence to the source and exact timestamp", () => {
    expect(
      evidenceSourceHref({
        sourceId: 8,
        revisionId: 11,
        indexRevisionId: 12,
        chunkId: 13,
        contentHash: "f".repeat(64),
        revisionContentHash: "e".repeat(64),
        sourceType: "video",
        locator: { kind: "media_time", start_ms: 9_000, end_ms: 12_000 }
      })
    ).toBe(
      `/media/sources/8?t=9000&source=8&revision=11&index_revision=12&chunk=13&hash=${"f".repeat(64)}&revision_hash=${"e".repeat(64)}`
    );
  });

  it("falls back to the unified Library instead of lying about the source kind", () => {
    expect(
      evidenceSourceHref({
        sourceId: 11,
        revisionId: 21,
        chunkId: 41,
        contentHash: "1".repeat(64),
        sourceType: "unknown",
        locator: { kind: "text" }
      })
    ).toBe(`/library?source=11&revision=21&chunk=41&hash=${"1".repeat(64)}`);
  });

  it("routes catalog cards by their real source type", () => {
    expect(catalogSourceHref({ sourceId: 2, sourceType: "document", documentId: 12 })).toBe("/documents/12");
    expect(catalogSourceHref({ sourceId: 4, sourceType: "code", documentId: null })).toBe("/code?source=4");
    expect(catalogSourceHref({ sourceId: 5, sourceType: "code_repository", documentId: null })).toBe("/code?source=5");
    expect(catalogSourceHref({ sourceId: 8, sourceType: "audio", documentId: null })).toBe("/media/sources/8");
  });

  it("keeps every demo source fallback inside the labelled Recording surface", () => {
    expect(
      evidenceSourceHref({
        sourceId: 9_101,
        revisionId: 9_201,
        indexRevisionId: 9_301,
        chunkId: 9_401,
        contentHash: "1".repeat(64),
        sourceType: "document",
        locator: { kind: "page", page_number: 12 },
        demo: true
      })
    ).toBe(`/library?demo=1&source=9101&revision=9201&index_revision=9301&chunk=9401&hash=${"1".repeat(64)}`);
  });
});
