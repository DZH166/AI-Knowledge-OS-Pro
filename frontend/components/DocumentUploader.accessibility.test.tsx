import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { DocumentUploader, DocumentUploadProgress } from "./DocumentUploader";

describe("accessible document intake", () => {
  it("provides a labelled native file control that keyboard users can reach", () => {
    const markup = renderToStaticMarkup(createElement(DocumentUploader, {
      spaces: [{ id: 7, name: "研究资料", description: "", created_at: "2026-10-13T00:00:00Z", updated_at: "2026-10-13T00:00:00Z" }],
      defaultSpaceId: 7, onUploaded: vi.fn()
    }));
    expect(markup).toMatch(/<input[^>]*aria-label="选择文档文件"[^>]*type="file"/);
    expect(markup).not.toContain("display:none");
    expect(markup).toContain('accept=".txt,.md,.pdf"');
  });

  it("shows completed as the current stage at 100%, even if the last stage name is stale", () => {
    const markup = renderToStaticMarkup(createElement(DocumentUploadProgress, {
      job: { status: "completed", current_step: "indexing", progress: 100 }
    }));
    expect(markup).toMatch(/<li[^>]*aria-current="step"[^>]*>完成<\/li>/);
  });

  it("makes a failed status read visible and recoverable without asking to restart the backend job", () => {
    const markup = renderToStaticMarkup(createElement(DocumentUploadProgress, {
      job: { status: "running", current_step: "embedding", progress: 40 },
      pollError: "网络暂时不可用", onRefresh: vi.fn()
    }));
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("网络暂时不可用");
    expect(markup).toContain("刷新处理状态");
    expect(markup).not.toContain("重新处理");
  });

  it.each([
    ["parsing", "解析内容"], ["chunking", "切分片段"], ["embedding", "生成向量"], ["indexing", "写入索引"]
  ])("uses the backend %s stage even when the reported percentage is near completion", (stage, label) => {
    const markup = renderToStaticMarkup(createElement(DocumentUploadProgress, {
      job: { status: "running", current_step: stage, progress: 99 }
    }));
    expect(markup).toMatch(new RegExp(`<li[^>]*aria-current="step"[^>]*>${label}</li>`));
  });
});
