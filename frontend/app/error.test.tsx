import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import ErrorBoundary from "@/app/error";

describe("route error boundary", () => {
  it("explains that saved work is safe and offers retry and recovery", () => {
    const markup = renderToStaticMarkup(
      createElement(ErrorBoundary, {
        error: Object.assign(new Error("boom"), { digest: "digest-123" }),
        reset: () => {}
      })
    );

    expect(markup).toContain("这一页没有完成加载");
    expect(markup).toContain("重试当前页");
    expect(markup).toContain("回到工作台");
    expect(markup).toContain("digest-123");
  });
});
