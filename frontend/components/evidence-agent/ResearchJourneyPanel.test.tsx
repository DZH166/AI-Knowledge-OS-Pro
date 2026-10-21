import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ResearchJourneyPanel } from "./ResearchJourneyPanel";

describe("three-source comparison preparation", () => {
  it("shows the next action when a new user has no knowledge space", () => {
    const markup = renderToStaticMarkup(createElement(ResearchJourneyPanel, {
      activeSourceCount: 0, enabled: true, onToggle: vi.fn(), readiness: { state: "unknown" },
      selectedSourceCount: 0, spaceId: 0
    }));

    expect(markup).toContain("先创建知识空间");
    expect(markup).toContain('href="/knowledge"');
  });

  it("does not count unfinished uploads as usable evidence", () => {
    const markup = renderToStaticMarkup(createElement(ResearchJourneyPanel, {
      activeSourceCount: 2, enabled: true, onToggle: vi.fn(), readiness: { state: "blocked", missing: ["真实语言模型"] },
      selectedSourceCount: 2, spaceId: 7
    }));

    expect(markup).toContain("还差 1 份可用资料");
    expect(markup).toContain('href="/upload?space_id=7&amp;scenario=compare"');
    expect(markup).toContain("真实语言模型未就绪");
    expect(markup).toContain('href="/system/settings"');
  });

  it("describes present documents without a usable version without assuming their processing state", () => {
    const markup = renderToStaticMarkup(createElement(ResearchJourneyPanel, {
      activeSourceCount: 0, enabled: true, onToggle: vi.fn(), readiness: { state: "unknown" },
      selectedSourceCount: 0, spaceId: 7, totalSourceCount: 3
    }));

    expect(markup).toContain("3 份尚无可用版本");
    expect(markup).not.toContain("仍在处理");
    expect(markup).toContain('href="/tasks"');
  });

  it("recognizes three selected active sources while keeping recording mode explicit", () => {
    const markup = renderToStaticMarkup(createElement(ResearchJourneyPanel, {
      activeSourceCount: 3, enabled: true, onToggle: vi.fn(), readiness: { state: "recording" },
      selectedSourceCount: 3, spaceId: 7
    }));

    expect(markup).toContain("已选择 3 份可用资料");
    expect(markup).toContain("录制样例，不会调用真实模型");
    expect(markup).toContain("真实研究完成后才能提交错误反馈");
  });

  it("never sends a recording-only space to the real upload center", () => {
    const markup = renderToStaticMarkup(createElement(ResearchJourneyPanel, {
      activeSourceCount: 1, enabled: true, onToggle: vi.fn(), readiness: { state: "recording" },
      selectedSourceCount: 0, spaceId: 9_002
    }));

    expect(markup).toContain("请切换到含三份示例资料的研究空间");
    expect(markup).not.toContain('href="/upload?space_id=9002');
  });
});
