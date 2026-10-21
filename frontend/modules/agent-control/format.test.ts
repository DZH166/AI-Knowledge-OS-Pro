import { describe, expect, it } from "vitest";

import {
  formatDateTime,
  formatDuration,
  formatMetricValue,
  formatNumber,
  formatPercentage
} from "./format";


describe("agent control formatters", () => {
  it("formats counters, percentages, durations, and timestamps consistently", () => {
    expect(formatNumber(12_345)).toBe("12,345");
    expect(formatPercentage(0.9833)).toBe("98.33%");
    expect(formatPercentage(null)).toBe("未记录");
    expect(formatDuration(250)).toBe("250 ms");
    expect(formatDuration(1_250)).toBe("1.25 s");
    expect(formatDateTime("2026-08-27T10:00:00Z")).toMatch(/2026/);
  });

  it("uses an explicit metric vocabulary instead of guessing from name fragments", () => {
    expect(formatMetricValue("case_pass_rate", -0.1)).toBe("-10%");
    expect(formatMetricValue("fusion_ndcg_at_10", 0.9876)).toBe("98.76%");
    expect(formatMetricValue("multi_hop_agent_lift_pp", 58.3333)).toBe("58.3333");
    expect(formatMetricValue("custom_recall_like_counter", 2)).toBe("2");
  });
});
