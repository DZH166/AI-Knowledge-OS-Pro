import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RunTraceSchema } from "@/modules/agent-control/contract";
import { runTrace } from "@/modules/agent-control/test-fixtures";
import { RunTraceContent } from "./RunTraceView";


describe("RunTraceContent", () => {
  it("explains replay, policy, budget and redaction without rendering private payloads", () => {
    const fixture = runTrace();
    const trace = RunTraceSchema.parse({
      ...fixture,
      events: [
        fixture.events[0],
        {
          ...fixture.events[0],
          sequence: 2,
          run_version: 2,
          event_type: "model.started",
          visibility: "private",
          redacted: true,
          facts: [],
          elapsed_ms: 1100,
          delta_ms: 100
        }
      ],
      policies: [{ policy_id: "evidence-gap-readonly", version: "1", source: "tool.started", config_sha256: null }],
      replay: {
        ...fixture.replay,
        event_count: 2,
        redacted_event_count: 1,
        stored_state_matches: true
      }
    });
    const markup = renderToStaticMarkup(createElement(RunTraceContent, { trace }));
    expect(markup).toContain("重放结果与数据库终态一致");
    expect(markup).toContain("evidence-gap-readonly");
    expect(markup).toContain("私有事件已脱敏");
    expect(markup).toContain("max_steps");
    expect(markup).toContain("事件顺序");
    expect(markup).toContain("Trace ID");
    expect(markup).toContain("开始时间");
    expect(markup).toContain("未记录上限");
    expect(markup).not.toContain("private prompt");
    expect(markup).not.toContain("api_key");
  });

  it("shows an actionable failure classification without claiming replay success", () => {
    const fixture = runTrace();
    const trace = RunTraceSchema.parse({
      ...fixture,
      status: "failed",
      replay: {
        ...fixture.replay,
        stored_terminal_state: "failed",
        replayed_terminal_state: "failed",
        stored_state_matches: true,
        trace_id_consistent: false
      },
      triage: {
        category: "worker_interrupted",
        summary: "后台任务进程在完成当前步骤前中断。",
        retryable: true,
        supporting_facts: ["termination_reason=worker_interrupted"],
        suggested_action: "恢复 Worker 后从最近检查点继续。"
      },
      warnings: ["trace_id_mismatch"]
    });
    const markup = renderToStaticMarkup(createElement(RunTraceContent, { trace }));
    expect(markup).toContain("后台任务进程中断");
    expect(markup).toContain("需要检查");
    expect(markup).toContain("可以重试");
    expect(markup).toContain("恢复 Worker 后从最近检查点继续");
    expect(markup).toContain("trace_id_mismatch");
  });
});
