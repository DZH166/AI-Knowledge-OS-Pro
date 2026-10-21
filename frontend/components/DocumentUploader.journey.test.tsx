import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { DocumentUploader } from "./DocumentUploader";

describe("document intake for the comparison journey", () => {
  it("explains that upload and indexed evidence are different states", () => {
    const markup = renderToStaticMarkup(createElement(DocumentUploader, {
      comparisonMode: true,
      defaultSpaceId: 7,
      onUploaded: vi.fn(),
      spaces: [{
        id: 7, name: "方案资料", description: "", document_count: 0, chunk_count: 0, qa_count: 0,
        created_at: "2026-09-26T00:00:00Z", updated_at: "2026-09-26T00:00:00Z"
      }]
    }));

    expect(markup).toContain("上传后还需等待处理和索引完成");
    expect(markup).toMatch(/<select[^>]*disabled=""[^>]*id="space"|<select[^>]*id="space"[^>]*disabled=""/);
    expect(markup).not.toContain("V3 会继续扩展");
  });
});
