import { describe, expect, it } from "vitest";

import { artifactKindLabel } from "./artifact-presenter";

describe("artifact presenter", () => {
  it("shares stable Chinese artifact-kind labels and preserves unknown kinds", () => {
    expect(artifactKindLabel("answer")).toBe("带引用回答");
    expect(artifactKindLabel("comparison")).toBe("对比报告");
    expect(artifactKindLabel("research_report")).toBe("研究报告");
    expect(artifactKindLabel("custom_brief")).toBe("custom_brief");
  });
});
