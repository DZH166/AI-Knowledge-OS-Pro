import { describe, expect, it } from "vitest";

import { RECORDING_SOURCES, RECORDING_SPACES, comparisonReadySources, sourceAvailabilityLabel, sourceIndexSummary, sourceTypeLabel } from "./source-presenter";

describe("source presenter", () => {
  it("uses the backend code_repository name and keeps compatibility with legacy code", () => {
    expect(sourceTypeLabel("code_repository")).toBe("代码仓库");
    expect(sourceTypeLabel("code")).toBe("代码仓库");
    expect(RECORDING_SOURCES.find((source) => source.source_type === "code_repository")?.id).toBe(9_103);
  });

  it("offers three clearly synthetic active documents for the recording comparison journey", () => {
    const researchSpace = RECORDING_SPACES[0];
    const activeDocuments = RECORDING_SOURCES.filter((source) =>
      source.space_id === researchSpace.id && source.source_type === "document" && source.active_revision_id !== null
    );

    expect(activeDocuments).toHaveLength(3);
    expect(sourceIndexSummary(activeDocuments[0])).toBe("校验通过 · 已建立 18 条索引");
  });

  it("counts only documents with an available revision in the comparison journey", () => {
    const source = RECORDING_SOURCES[0];
    expect(comparisonReadySources([
      source,
      { ...source, id: 10, active_revision_id: source.active_revision_id, revisions: [] },
      { ...source, id: 11, source_type: "video" },
      { ...source, id: 12, active_revision_id: null }
    ])).toEqual([source]);
  });

  it("does not mislabel retired or failed documents as still processing", () => {
    const source = RECORDING_SOURCES[0];
    expect(sourceAvailabilityLabel({ ...source, active_revision_id: null, status: "retired" })).toBe("已退役");
    expect(sourceAvailabilityLabel({ ...source, active_revision_id: null, status: "failed" })).toBe("处理失败");
    expect(sourceAvailabilityLabel({ ...source, active_revision_id: null, status: "uploaded", revisions: [] }))
      .toBe("尚不可用");
    expect(sourceAvailabilityLabel(source)).toBe("可用");
  });
});
