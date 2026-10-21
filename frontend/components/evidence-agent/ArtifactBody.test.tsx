import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ArtifactBody } from "./ArtifactBody";

describe("readable research body", () => {
  it("renders report headings, a real table, a list and a code block instead of literal Markdown", () => {
    const markup = renderToStaticMarkup(createElement(ArtifactBody, { markdown: "# 比较结论\n\n| 方案 | 成本 |\n| --- | --- |\n| A | 低 |\n\n- 核对来源\n\n```ts\nconst evidence = true;\n```" }));
    expect(markup).toContain("<h3>比较结论</h3>");
    expect(markup).toContain("<table>");
    expect(markup).toContain("<li>核对来源</li>");
    expect(markup).toContain('class="language-ts"');
  });

  it("shows a remote image as an explicit link without loading an image on report open", () => {
    const markup = renderToStaticMarkup(createElement(ArtifactBody, { markdown: "![资料截图](https://example.com/tracking-image.png)" }));
    expect(markup).not.toContain("<img");
    expect(markup).toContain("资料截图");
    expect(markup).toContain('href="https://example.com/tracking-image.png"');
  });

  it("keeps safe links while omitting executable HTML and unsafe link protocols", () => {
    const markup = renderToStaticMarkup(createElement(ArtifactBody, { markdown:
      '[危险](javascript:alert%281%29)\n\n[数据](data:text/html;base64,abc)\n\n<img src=x onerror=alert(1)>\n\n<script>bad()</script>\n\n[文档](/documents/7#page=2)\n\n[来源](https://example.com/source)' }));
    expect(markup).not.toMatch(/<script|<img|onerror=|href="(?:javascript:|data:)/);
    expect(markup).toContain('href="/documents/7#page=2"');
    expect(markup).toContain('href="https://example.com/source"');
  });

  it("makes report tables and code independently keyboard-scrollable regions", () => {
    const markup = renderToStaticMarkup(createElement(ArtifactBody, { markdown:
      '| 方案 | 约束 |\n| --- | --- |\n| A | 需要核对 |\n\n```text\n固定证据内容\n```' }));
    expect(markup).toMatch(/aria-label="研究正文表格"[^>]*role="region"[^>]*tabindex="0"/);
    expect(markup).toMatch(/aria-label="研究正文代码"[^>]*role="region"[^>]*tabindex="0"/);
  });

  it.each(["![空图片]()", "![非法图片](javascript:alert%281%29)"])("does not create a link for an empty or unsafe image URL: %s", (markdown) => {
    const markup = renderToStaticMarkup(createElement(ArtifactBody, { markdown }));
    expect(markup).not.toMatch(/<img|<a /);
    expect(markup).toContain("图片：");
  });
});
