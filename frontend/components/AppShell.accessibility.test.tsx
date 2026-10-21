import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({ usePathname: () => "/runs/run-42", useSearchParams: () => new URLSearchParams(navigation.search) }));
vi.mock("@/services/page-metrics", () => ({ markRouteTransitionStart: vi.fn(), recordRouteReady: vi.fn() }));

import { AppShell } from "./AppShell";

describe("AppShell accessibility", () => {
  beforeEach(() => { vi.clearAllMocks(); navigation.search = ""; });

  it("provides a skip target, one active navigation link, and a collapsed developer section", () => {
    const markup = renderToStaticMarkup(createElement(AppShell, null, createElement("h1", null, "Run Workspace")));

    expect(markup).toContain('href="#main-content"');
    expect(markup).toContain('<main class="main-content" id="main-content"');
    expect(markup.match(/<a[^>]+aria-current="page"/g)).toHaveLength(1);
    expect(markup).toContain("Developer Mode");
    expect(markup).toContain("<details");
  });

  it("keeps recording mode on all core links without turning developer tools into fake demos", () => {
    navigation.search = "demo=1";
    const markup = renderToStaticMarkup(createElement(AppShell, null, createElement("h1", null, "研究")));
    for (const route of ["workbench", "runs", "library", "artifacts"]) expect(markup).toContain(`href="/${route}?demo=1"`);
    expect(markup).toContain('href="/system"');
    expect(markup).not.toContain('href="/system?demo=1"');
    expect(markup).toContain("演示模式 · 非真实执行");
  });
});
