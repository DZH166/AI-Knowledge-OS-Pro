import { describe, expect, it } from "vitest";

import { RECORDING_SOURCES, sourceTypeLabel } from "./source-presenter";

describe("source presenter", () => {
  it("uses the backend code_repository name and keeps compatibility with legacy code", () => {
    expect(sourceTypeLabel("code_repository")).toBe("代码仓库");
    expect(sourceTypeLabel("code")).toBe("代码仓库");
    expect(RECORDING_SOURCES.find((source) => source.source_type === "code_repository")?.id).toBe(9_103);
  });
});
