import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ResearchOverview } from "./ResearchOverview";

describe("honest research visualization", () => {
  it("labels the actual phase rather than manufacturing completion percentages", () => {
    const html = renderToStaticMarkup(createElement(ResearchOverview, { view: {
      status: "running", phase: "assess", budget_usage: { steps: 3 }, budget_limits: { max_steps: 8 }
    }, ledger: [{ relation: "supports" }, { relation: "candidate" }, { relation: "excluded" }, { relation: "contradicts" }] }));
    expect(html).toContain("当前执行阶段");
    expect(html).toContain('aria-current="step"');
    expect(html).toContain("阶段位置不代表完成比例");
    expect(html).toContain("4 条记录");
    expect(html).toContain('data-relation="supports"><dt>支持结论</dt><dd>1</dd>');
    expect(html).toContain('data-relation="contradicts"><dt>存在冲突</dt><dd>1</dd>');
    expect(html).toContain('max="8"');
    expect(html).toContain('value="3"');
    expect(html).not.toContain("100%");
  });

  it("labels terminal phases as last reported rather than currently executing, without inventing usage", () => {
    for (const status of ["completed", "failed", "cancelled", "insufficient_evidence"] as const) {
      const html = renderToStaticMarkup(createElement(ResearchOverview, { view: {
        status, phase: "retrieve", budget_usage: {}, budget_limits: {}
      }, ledger: [] }));
      expect(html).toContain("最后上报阶段");
      expect(html).not.toContain('aria-current="step"');
      expect(html).toContain("0 条记录");
      expect(html).toContain("步骤预算尚未上报");
      expect(html).not.toContain("研究已完成");
      expect(html).not.toContain("<meter");
    }
  });

  it("does not animate an old phase as current while an approval or input is pending", () => {
    for (const status of ["awaiting_approval", "awaiting_input", "paused", "queued"] as const) {
      const html = renderToStaticMarkup(createElement(ResearchOverview, { view: {
        status, phase: "route", budget_usage: { steps: 0 }, budget_limits: { max_steps: 8 }
      }, ledger: [] }));
      expect(html).toContain("研究阶段记录");
      expect(html).toContain("等待状态不表示该阶段仍在执行");
      expect(html).not.toContain('aria-current="step"');
    }
  });
});
