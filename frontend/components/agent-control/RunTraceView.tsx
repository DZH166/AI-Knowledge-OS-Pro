"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentControlClient } from "@/modules/agent-control/client";
import type { RunTrace } from "@/modules/agent-control/contract";
import { formatDateTime, formatDuration, formatNumber } from "@/modules/agent-control/format";
import { failureCategoryLabel, traceEventLabel } from "@/modules/agent-control/presenter";
import { AgentRunShareClient } from "@/modules/agent-run-share/client";
import type { ShareLinkReceipt } from "@/modules/agent-run-share/contract";
import styles from "./AgentControl.module.css";


export function RunTraceView() {
  const params = useParams<{ runId: string }>();
  const runId = decodeURIComponent(params.runId);
  const client = useMemo(() => new AgentControlClient(), []);
  const runShare = useMemo(() => new AgentRunShareClient(), []);
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [shareLink, setShareLink] = useState<ShareLinkReceipt | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [shareError, setShareError] = useState("");
  const [shareCopied, setShareCopied] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      setTrace(await client.getRunTrace(runId, signal));
    } catch (reason) {
      if (signal?.aborted) return;
      setTrace(null);
      setError(reason instanceof Error ? reason.message : "无法加载运行轨迹。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [client, runId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function createShare() {
    setShareBusy(true);
    setShareError("");
    try { setShareLink(await runShare.create(runId, 7)); }
    catch (reason) { setShareError(reason instanceof Error ? reason.message : "无法创建只读分享链接。"); }
    finally { setShareBusy(false); }
  }

  async function revokeShare() {
    if (!shareLink) return;
    setShareBusy(true);
    setShareError("");
    try {
      await runShare.revoke(shareLink.token);
      setShareLink(null);
    } catch (reason) { setShareError(reason instanceof Error ? reason.message : "无法撤销分享链接。"); }
    finally { setShareBusy(false); }
  }

  async function copySharePath() {
    if (!shareLink) return;
    setShareCopied(false);
    setShareError("");
    try {
      await navigator.clipboard.writeText(shareLink.url_path);
      setShareCopied(true);
    } catch {
      setShareError("浏览器未允许复制，请手动选择下方路径。");
    }
  }

  if (loading) {
    return <div aria-live="polite" className={styles.loading} role="status">正在读取持久化运行事实…</div>;
  }
  if (error || !trace) {
    return (
      <section className={styles.error} role="alert">
        <div>
          <h1>无法打开运行轨迹</h1>
          <p>{error || "该 Run 没有可读取的轨迹。"} 系统不会用演示轨迹替代生产数据。</p>
          <div className={styles.actionRow}>
            <button className={styles.button} onClick={() => void load()} type="button">重新加载</button>
            <Link className={styles.quietButton} href={`/runs/${encodeURIComponent(runId)}`}>返回 Run</Link>
          </div>
        </div>
      </section>
    );
  }
  return <RunTraceContent onCopyShare={() => void copySharePath()} onCreateShare={() => void createShare()} onRevokeShare={() => void revokeShare()} shareBusy={shareBusy} shareCopied={shareCopied} shareError={shareError} shareLink={shareLink} trace={trace} />;
}


export function RunTraceContent({
  trace,
  shareLink = null,
  shareBusy = false,
  shareCopied = false,
  shareError = "",
  onCopyShare = () => undefined,
  onCreateShare = () => undefined,
  onRevokeShare = () => undefined
}: {
  trace: RunTrace;
  shareLink?: ShareLinkReceipt | null;
  shareBusy?: boolean;
  shareCopied?: boolean;
  shareError?: string;
  onCopyShare?: () => void;
  onCreateShare?: () => void;
  onRevokeShare?: () => void;
}) {
  const replayHealthy = trace.replay.sequence_contiguous &&
    trace.replay.trace_id_consistent &&
    trace.replay.stored_state_matches;
  const budgetKeys = Array.from(new Set([
    ...Object.keys(trace.budget_limits),
    ...Object.keys(trace.budget_usage)
  ])).sort();

  return (
    <div className={styles.page} data-testid="run-trace-page">
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Agent Run Trace · 运行轨迹</p>
          <h1>这次研究是怎么跑出来的</h1>
          <p className={styles.lead}>
            这里重放数据库里已经发生的事实，不会重新调用模型、工具或外部服务。私有事件只显示“已脱敏”。
          </p>
        </div>
        <div className={styles.actionRow}>
          <Link className={styles.quietButton} href={`/runs/${encodeURIComponent(trace.run_id)}`}>返回 Run</Link>
          <Link className={styles.button} href="/evaluations">打开评测中心</Link>
          {!shareLink ? <button className={styles.quietButton} disabled={shareBusy} onClick={onCreateShare} type="button">{shareBusy ? "正在创建…" : "创建只读分享"}</button> : null}
        </div>
      </header>

      {shareError ? <p aria-live="polite" className={styles.inlineError} role="alert">{shareError}</p> : null}
      {shareLink ? <section className={styles.panel} data-testid="run-share-panel"><div className={styles.panelHeader}><div><p className={styles.sectionIndex}>Share / 只读分享</p><h2>7 天有效的运行轨迹链接</h2><p>访问者只能读取同一份脱敏 Run Trace，不能执行、恢复或修改任务。</p></div><div className={styles.actionRow}><button className={styles.quietButton} onClick={onCopyShare} type="button">复制分享路径</button><button className={styles.quietButton} disabled={shareBusy} onClick={onRevokeShare} type="button">撤销分享</button></div></div>{shareCopied ? <p aria-live="polite" role="status">分享路径已复制。</p> : null}<div className={styles.monoBlock} translate="no">{shareLink.url_path}<br />Expires {formatDateTime(shareLink.expires_at, { includeSeconds: true })}</div></section> : null}

      <section aria-label="运行轨迹结论" className={styles.summaryGrid}>
        <article className={styles.summaryCard} data-wide="true">
          <span className={styles.status} data-state={replayHealthy ? "ok" : "error"}>
            {replayHealthy ? "记录一致" : "需要检查"}
          </span>
          <strong>{replayHealthy ? "重放结果与数据库终态一致" : "轨迹完整性检查未全部通过"}</strong>
          <p>事件顺序、Trace ID（轨迹编号）和最终状态必须同时一致。</p>
          <ul className={styles.factList}>
            <li><strong>事件顺序</strong><span>{trace.replay.sequence_contiguous ? "连续" : "存在缺口"}</span></li>
            <li><strong>Trace ID</strong><span>{trace.replay.trace_id_consistent ? "全部一致" : "存在混用"}</span></li>
            <li><strong>最终状态</strong><span>{trace.replay.stored_state_matches ? "重放与存储一致" : "不一致"}</span></li>
            <li><strong>检查点</strong><span>{formatNumber(trace.replay.checkpoint_count)} 个</span></li>
            {trace.warnings.map((warning) => <li key={warning}><strong>警告</strong><span className={styles.meta}>{warning}</span></li>)}
          </ul>
        </article>
        <article className={styles.summaryCard}>
          <span className={styles.status} data-state={trace.triage.category === "none" ? "ok" : "warning"}>
            Failure Triage · 失败归因
          </span>
          <strong>{failureCategoryLabel(trace.triage.category)}</strong>
          <p>{trace.triage.summary}</p>
        </article>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <p className={styles.sectionIndex}>01 / Identity</p>
            <h2>运行身份与重放指纹</h2>
            <p>两个编号分别用于定位 Run 和串联同一次运行中的所有事件。</p>
          </div>
          <span className={styles.status}>{trace.status}</span>
        </div>
        <div className={styles.twoColumns}>
          <div className={styles.monoBlock} translate="no">Run {trace.run_id}<br />Trace {trace.trace_id}</div>
          <div className={styles.monoBlock} translate="no">Replay SHA-256<br />{trace.replay.digest}</div>
        </div>
        <ul className={styles.factList}>
          <li><strong>研究目标</strong><span>{trace.goal}</span></li>
          <li><strong>模式</strong><span>{trace.requested_mode} → {trace.effective_mode ?? "尚未决定"}</span></li>
          <li><strong>Provider 边界</strong><span>{trace.provider_mode} · 不代表真实模型评测</span></li>
          <li><strong>活动耗时</strong><span>{formatDuration(trace.active_elapsed_ms)}</span></li>
          <li><strong>开始时间</strong><span>{formatDateTime(trace.started_at ?? trace.created_at, { includeSeconds: true })}</span></li>
          <li><strong>结束时间</strong><span>{trace.finished_at ? formatDateTime(trace.finished_at, { includeSeconds: true }) : "尚未结束"}</span></li>
        </ul>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <p className={styles.sectionIndex}>02 / Policy & Budget</p>
            <h2>策略版本和预算</h2>
            <p>策略决定“为什么选这个工具”，预算限制“最多可以执行多少步”。</p>
          </div>
        </div>
        <div className={styles.twoColumns}>
          <div>
            <h3>策略事实</h3>
            <ul className={styles.policyList}>
              {trace.policies.length ? trace.policies.map((policy) => (
                <li className={styles.policyItem} key={`${policy.policy_id}:${policy.version}:${policy.source}:${policy.config_sha256 ?? "legacy"}`}>
                  <strong>{policy.policy_id} · v{policy.version}</strong>
                  <span className={styles.meta}>{policy.source}</span>
                  {policy.config_sha256 ? <span className={styles.meta} translate="no">SHA-256 {policy.config_sha256}</span> : null}
                  {policy.source === "run_snapshot" ? <Link className={styles.quietButton} href={`/policies/${encodeURIComponent(policy.policy_id)}`}>打开固定策略</Link> : null}
                </li>
              )) : <li className={styles.policyItem}>当前轨迹没有单独记录策略版本。</li>}
            </ul>
          </div>
          <div>
            <h3>预算使用</h3>
            <ul className={styles.budgetList}>
              {budgetKeys.length ? budgetKeys.map((key) => (
                <li className={styles.budgetItem} key={key}>
                  <strong>{key}</strong>
                  <span>
                    {formatNumber(trace.budget_usage[key] ?? 0)} / {trace.budget_limits[key] === undefined ? "未记录上限" : formatNumber(trace.budget_limits[key])}
                  </span>
                </li>
              )) : <li className={styles.budgetItem}>没有记录预算字段。</li>}
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.panel} data-testid="run-trace-timeline">
        <div className={styles.panelHeader}>
          <div>
            <p className={styles.sectionIndex}>03 / Timeline</p>
            <h2>按顺序发生的事件</h2>
            <p>事件来自持久化 Journal（事件日志）；私有内容不进入页面。</p>
          </div>
          <span className={styles.status}>{formatNumber(trace.events.length)} 个事件</span>
        </div>
        <ol className={styles.timeline}>
          {trace.events.map((event) => (
            <li className={styles.timelineItem} key={`${event.sequence}:${event.event_type}`}>
              <span className={styles.timelineTime}>+{formatDuration(event.elapsed_ms)}</span>
              <div className={styles.timelineBody}>
                <h3>{formatNumber(event.sequence)}. {traceEventLabel(event.event_type)}</h3>
                <span className={styles.meta}>Run v{event.run_version} · delta {formatDuration(event.delta_ms)}</span>
                {event.redacted ? (
                  <div className={styles.redacted} data-testid="redacted-event">私有事件已脱敏，不展示 prompt 或完整载荷。</div>
                ) : event.facts.length ? (
                  <details>
                    <summary>查看允许公开的事实</summary>
                    <ul>{event.facts.map((fact) => <li key={fact} className={styles.meta}>{fact}</li>)}</ul>
                  </details>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <div className={styles.twoColumns}>
        <section className={styles.panel} data-testid="run-trace-tools">
          <div className={styles.panelHeader}>
            <div><p className={styles.sectionIndex}>04 / Tools</p><h2>工具调用摘要</h2></div>
          </div>
          <ul className={styles.callList}>
            {trace.tool_calls.length ? trace.tool_calls.map((call) => (
              <li className={styles.callItem} key={call.id}>
                <strong>{call.tool_name} · v{call.tool_version}</strong>
                <span>{call.status} · {call.duration_ms === null ? "未记录耗时" : formatDuration(call.duration_ms)}</span>
                <span className={styles.meta}>arguments SHA-256 {call.arguments_digest}</span>
                {call.error_code ? <span className={styles.meta}>error {call.error_code}</span> : null}
              </li>
            )) : <li className={styles.callItem}>没有工具调用。</li>}
          </ul>
        </section>
        <section className={styles.panel} data-testid="run-trace-models">
          <div className={styles.panelHeader}>
            <div><p className={styles.sectionIndex}>05 / Models</p><h2>模型调用摘要</h2></div>
          </div>
          <ul className={styles.callList}>
            {trace.model_calls.length ? trace.model_calls.map((call) => (
              <li className={styles.callItem} key={call.id}>
                <strong>{call.operation} · {call.status}</strong>
                <span>{call.provider}/{call.model} · {formatDuration(call.latency_ms)}</span>
                <span className={styles.meta}>{call.input_tokens} input / {call.output_tokens} output tokens · {call.usage_estimated ? "估算用量" : "Provider 报告用量"}</span>
              </li>
            )) : <li className={styles.callItem}>没有模型调用；Quick 路径可能为 0。</li>}
          </ul>
        </section>
      </div>

      {trace.triage.category !== "none" ? (
        <section className={styles.panel} data-testid="run-trace-triage">
          <div className={styles.panelHeader}>
            <div><p className={styles.sectionIndex}>06 / Next Action</p><h2>失败后下一步怎么做</h2></div>
            <span className={styles.status} data-state="warning">{trace.triage.retryable ? "可以重试" : "先人工处理"}</span>
          </div>
          <p>{trace.triage.suggested_action}</p>
          <ul className={styles.factList}>{trace.triage.supporting_facts.map((fact) => <li key={fact} className={styles.meta}>{fact}</li>)}</ul>
        </section>
      ) : null}
    </div>
  );
}
