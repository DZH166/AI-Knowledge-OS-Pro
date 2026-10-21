import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EvidenceDetail } from "./EvidenceDetail";

describe("public fixed evidence presentation", () => {
  it("retains the source, revision, index, chunk, hashes and exact locator in the visible detail and source link", () => {
    const markup = renderToStaticMarkup(createElement(EvidenceDetail, { title: "方案 A 原文", excerpt: "原文片段",
      sourceType: "document", revisionContentHash: "b".repeat(64), reference: {
        source_id: 7, revision_id: 8, index_revision_id: 9, chunk_id: 10, content_hash: "a".repeat(64),
        locator: { kind: "document_page", document_id: 42, page_number: 3 }
      } }));
    expect(markup).toContain("page_number=3");
    expect(markup).toContain('href="/documents/42?page=3&amp;source=7&amp;revision=8&amp;index_revision=9&amp;chunk=10&amp;hash=' + "a".repeat(64));
    expect(markup).toContain("revision_hash=" + "b".repeat(64));
    expect(markup).toContain("<dt>证据片段</dt><dd>10</dd>");
  });

  it("displays source HTML as quoted text instead of executing it", () => {
    const markup = renderToStaticMarkup(createElement(EvidenceDetail, { title: "原文", excerpt: "<script>alert(1)</script>",
      reference: { source_id: 7, revision_id: 8, index_revision_id: 9, chunk_id: 10,
        content_hash: "a".repeat(64), locator: { kind: "text" } } }));
    expect(markup).not.toContain("<script>");
    expect(markup).toContain("&lt;script&gt;");
  });
});
