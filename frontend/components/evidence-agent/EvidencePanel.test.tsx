import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { EvidencePanel } from "./EvidencePanel";

describe("evidence presentation", () => {
  it("offers a labelled close action without removing the evidence content or loading state", () => {
    const markup = renderToStaticMarkup(<EvidencePanel open busy onClose={vi.fn()} returnFocusRef={{ current: null }}>
      来源版本 8 · 片段 10
    </EvidencePanel>);
    expect(markup).toContain('aria-label="关闭证据详情"');
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain("来源版本 8 · 片段 10");
  });
});
