import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { RunView } from "@/modules/evidence-agent";

vi.mock("next/navigation", () => ({ useParams: () => ({ runId: "run-controls" }) }));

import { CancelRunDialog, EvidenceCard, ResearchOutcomePanel, ResearchPlanPanel, RunLifecycleControls } from "./RunWorkspace";

function renderControls(status: RunView["status"]): string {
  return renderToStaticMarkup(
    createElement(RunLifecycleControls, {
      acting: false,
      confirmCancel: false,
      onCancelRequest: vi.fn(),
      onPause: vi.fn(),
      onResume: vi.fn(),
      status
    })
  );
}

describe("Run lifecycle controls", () => {
  it("offers Pause only while the backend state machine allows a running run to pause", () => {
    const running = renderControls("running");

    expect(running).toContain("暂停 Run");
    expect(running).not.toContain("继续 Run");

    for (const status of ["queued", "routing", "planned", "awaiting_input", "awaiting_approval"] as const) {
      const markup = renderControls(status);
      expect(markup).not.toContain("暂停 Run");
      expect(markup).not.toContain("继续 Run");
    }
  });

  it("offers Resume instead of Pause for a paused run", () => {
    const paused = renderControls("paused");

    expect(paused).toContain("继续 Run");
    expect(paused).not.toContain("暂停 Run");
  });

  it("describes cancellation as a modal alert dialog with keyboard-safe actions", () => {
    const markup = renderToStaticMarkup(
      createElement(CancelRunDialog, {
        acting: false,
        onConfirm: vi.fn(),
        onDismiss: vi.fn()
      })
    );

    expect(markup).toContain('role="alertdialog"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain('aria-labelledby="cancel-title"');
    expect(markup).toContain('aria-describedby="cancel-description"');
    expect(markup).toContain("继续研究");
  });
});

describe("research plan", () => {
  it("renders every public plan requirement in the production workspace", () => {
    const markup = renderToStaticMarkup(
      createElement(ResearchPlanPanel, {
        plan: {
          version: 1,
          strategy: "structured_model_plan",
          requirements: ["核验成本", "核验延迟"]
        }
      })
    );

    expect(markup).toContain("研究计划");
    expect(markup).toContain("核验成本");
    expect(markup).toContain("核验延迟");
  });
});

describe("evidence gap report entry", () => {
  it("opens the saved artifact even when the outcome is insufficient evidence", () => {
    const markup = renderToStaticMarkup(createElement(ResearchOutcomePanel, {
      view: { status: "insufficient_evidence", final_artifact_id: "gap/研究", termination_reason: "第三份资料没有支持证据" },
      mode: "production"
    }));
    expect(markup).toContain("查看缺口报告");
    expect(markup).toContain('href="/artifacts/gap%2F%E7%A0%94%E7%A9%B6"');
    expect(markup).not.toContain("研究已完成");
    expect(markup).toContain("第三份资料没有支持证据");
  });

  it("does not invent a report link when no final artifact was saved", () => {
    const markup = renderToStaticMarkup(createElement(ResearchOutcomePanel, {
      view: { status: "insufficient_evidence", final_artifact_id: null, termination_reason: null }, mode: "production"
    }));
    expect(markup).toContain("证据不足");
    expect(markup).not.toContain("href=");
  });
});

describe("Evidence Ledger relations", () => {
  it("explains excluded evidence in Chinese instead of showing only an English code", () => {
    const markup = renderToStaticMarkup(
      createElement(EvidenceCard, {
        item: {
          id: "evidence-excluded",
          sourceTitle: "候选来源",
          excerpt: "这条证据未被选中。",
          relation: "excluded",
          reason: "model_not_selected",
          method: "model_assessment",
          reference: {
            source_id: 1,
            revision_id: 2,
            index_revision_id: 3,
            chunk_id: 4,
            content_hash: "a".repeat(64),
            locator: { kind: "text" }
          }
        },
        onSelect: vi.fn()
      })
    );
    expect(markup).toContain("已排除");
    expect(markup).toContain("未选为该需求的支持证据");
  });
});
