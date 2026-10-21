import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/runs/run-42" }));
vi.mock("@/services/page-metrics", () => ({ markRouteTransitionStart: vi.fn(), recordRouteReady: vi.fn() }));

import { AppShell } from "./AppShell";

describe("AppShell accessibility", () => {
  beforeEach(() => vi.clearAllMocks());

  it("provides a skip target, one active navigation link, and a collapsed developer section", () => {
    const markup = renderToStaticMarkup(createElement(AppShell, null, createElement("h1", null, "Run Workspace")));

    expect(markup).toContain('href="#main-content"');
    expect(markup).toContain('<main class="main-content" id="main-content"');
    expect(markup.match(/<a[^>]+aria-current="page"/g)).toHaveLength(1);
    expect(markup).toContain("Developer Mode");
    expect(markup).toContain("<details");
  });
});
