import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ProductTermHelp } from "./ProductTermHelp";

describe("ProductTermHelp", () => {
  it("pairs specialist product terms with concise Chinese explanations", () => {
    const markup = renderToStaticMarkup(createElement(ProductTermHelp, {
      terms: ["agent", "rag", "evidenceLedger", "revision", "proposalDigest", "artifact"]
    }));

    expect(markup).toContain("Agent");
    expect(markup).toContain("证据研究智能体");
    expect(markup).toContain("检索增强生成");
    expect(markup).toContain("证据账本");
    expect(markup).toContain("来源版本");
    expect(markup).toContain("提案指纹");
    expect(markup).toContain("研究成果");
    expect(markup).toContain('aria-label="产品术语说明"');
  });
});
