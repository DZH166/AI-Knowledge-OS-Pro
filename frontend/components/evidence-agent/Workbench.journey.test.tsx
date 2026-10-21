import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

import { Workbench } from "./Workbench";

describe("Workbench first research", () => {
  it("offers the three-source comparison path without replacing ordinary research", () => {
    const markup = renderToStaticMarkup(createElement(Workbench));

    expect(markup).toContain("开始三资料对比");
    expect(markup).toContain("研究目标");
    expect(markup).toContain("开始研究");
  });
});
