import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { RunConnectionStatus } from "./RunConnectionStatus";

describe("Run connection feedback", () => {
  it("keeps a retry available when completed task history has not reached its known final cursor", () => {
    const snapshot = { connection: "closed" as const, error: null, lastSyncedAt: 1791872400000,
      reconnectAttempt: 3, cursor: 6, view: { status: "completed" as const, last_event_cursor: 12 } };
    const markup = renderToStaticMarkup(createElement(RunConnectionStatus, {
      snapshot, mode: "production", onReconnect: vi.fn()
    }));
    expect(markup).not.toContain("事件已同步");
    expect(markup).toContain("重新连接");
  });
  it.each(["idle", "connecting", "retrying", "closed", "error"] as const)(
    "never calls a nonterminal %s connection synchronized", (connection) => {
      const markup = renderToStaticMarkup(createElement(RunConnectionStatus, {
        snapshot: { connection, error: connection === "error" ? "网络连接失败" : null,
          lastSyncedAt: null, reconnectAttempt: 1, cursor: 0, view: { status: "running", last_event_cursor: 12 } },
        mode: "production", onReconnect: vi.fn()
      }));
      expect(markup).not.toContain("事件已同步");
      expect(markup).toContain("尚未收到事件");
      if (connection === "closed" || connection === "error" || connection === "retrying") {
        expect(markup).toContain("重新连接");
        expect(markup).toContain("不会重复创建任务或提交审批");
      }
    }
  );

  it("distinguishes a completed stream and finite recording playback from a disconnected live run", () => {
    const snapshot = { connection: "closed" as const, error: null, lastSyncedAt: 1791872400000,
      reconnectAttempt: 0, cursor: 12, view: { status: "completed" as const, last_event_cursor: 12 } };
    const markup = renderToStaticMarkup(createElement(RunConnectionStatus, {
      snapshot, mode: "production", onReconnect: vi.fn()
    }));
    expect(markup).toContain("事件已同步");
    expect(markup).toContain("最后收到事件");
    expect(markup).not.toContain("重新连接");
    const recorded = renderToStaticMarkup(createElement(RunConnectionStatus, {
      snapshot: { ...snapshot, view: { status: "awaiting_approval", last_event_cursor: 12 } }, mode: "recording", onReconnect: vi.fn()
    }));
    expect(recorded).toContain("录制事件已读取");
    expect(recorded).not.toContain("连接已断开");
  });
});
