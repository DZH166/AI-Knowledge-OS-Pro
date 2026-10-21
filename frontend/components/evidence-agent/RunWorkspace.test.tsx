import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { RunView } from "@/modules/evidence-agent";

vi.mock("next/navigation", () => ({ useParams: () => ({ runId: "run-controls" }) }));

import { EvidenceCard, ResearchPlanPanel, RunLifecycleControls } from "./RunWorkspace";

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

    expect(markup).toContain("Research Plan");
    expect(markup).toContain("核验成本");
    expect(markup).toContain("核验延迟");
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
