import { describe, expect, it } from "vitest";

import {
  comparisonVerdictLabel,
  evaluationStatusLabel,
  failureCategoryLabel,
  metricLabel,
  traceEventLabel
} from "./presenter";

describe("agent control presenter", () => {
  it("keeps technical states understandable without hiding their meaning", () => {
    expect(evaluationStatusLabel("queued")).toBe("等待后台执行");
    expect(evaluationStatusLabel("passed")).toContain("门禁通过");
    expect(comparisonVerdictLabel("regressed")).toBe("出现回退");
    expect(failureCategoryLabel("worker_interrupted")).toContain("后台任务进程中断");
    expect(metricLabel("citation_completeness")).toBe("引用完整率");
    expect(traceEventLabel("tool.completed")).toBe("工具步骤 · completed");
  });
});
