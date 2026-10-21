import type { RunView } from "@/modules/evidence-agent/contract";
import { isTerminalRunSynchronized, type RunControllerSnapshot } from "@/modules/evidence-agent/run-controller";
import styles from "./EvidenceAgent.module.css";

type ConnectionSnapshot = Pick<RunControllerSnapshot, "connection" | "error" | "lastSyncedAt" | "reconnectAttempt" | "cursor"> & {
  view: Pick<RunView, "status" | "last_event_cursor">;
};

export function RunConnectionStatus({ snapshot, mode, onReconnect }: {
  snapshot: ConnectionSnapshot;
  mode: "production" | "recording";
  onReconnect: () => void;
}) {
  const { connection, lastSyncedAt, reconnectAttempt, error } = snapshot;
  const synchronized = isTerminalRunSynchronized(snapshot.view, snapshot.cursor) && lastSyncedAt !== null;
  const recorded = mode === "recording" && connection === "closed";
  const label = connection === "idle" ? "尚未连接"
    : connection === "connecting" ? "正在连接…"
      : connection === "live" ? "实时连接"
        : connection === "retrying" ? `连接中断，准备第 ${reconnectAttempt} 次重连…`
          : connection === "error" ? "连接异常"
            : recorded ? "录制事件已读取"
              : synchronized ? "事件已同步" : "连接已断开";
  const retry = !recorded && (connection === "error" || connection === "retrying" ||
    (connection === "closed" && !synchronized));

  return <section aria-label="运行连接状态" data-testid="run-connection-status">
    <p aria-live="polite" role="status">
      {label} · {lastSyncedAt === null ? "尚未收到事件" : `最后收到事件：${new Intl.DateTimeFormat("zh-CN", {
        hour: "2-digit", minute: "2-digit", second: "2-digit"
      }).format(lastSyncedAt)}`}
    </p>
    {error && <p className={styles.errorMessage}>{error}</p>}
    {retry && <>
      <p>当前显示最后已接收的进度。重连只读取原任务，不会重复创建任务或提交审批。</p>
      <button className={styles.quietAction} onClick={onReconnect} type="button">重新连接</button>
    </>}
  </section>;
}
