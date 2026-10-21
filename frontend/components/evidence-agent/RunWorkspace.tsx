"use client";

import { AlertTriangle, ArrowLeft, Check, FileCheck2, Pause, Play, ShieldAlert, Square } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RunController, type RunView, useEvidenceRun } from "@/modules/evidence-agent";
import styles from "./EvidenceAgent.module.css";
import { ProductTermHelp } from "./ProductTermHelp";
import { ResearchOverview } from "./ResearchOverview";
import { loadEvidenceRun, updateStoredRunView } from "./runtime";
import { readPendingSubmission } from "@/modules/evidence-agent/workbench-session";
import {
  attentionFromEvents,
  evidenceReasonLabel,
  evidenceRelationLabel,
  ledgerFromEvents,
  planFromEvents,
  runStatusLabel,
  timelineFromEvents,
  type LedgerItem,
  type ResearchPlan
} from "./run-presenter";

export function RunWorkspace() {
  const params = useParams<{ runId: string }>();
  const runId = decodeURIComponent(params.runId);
  const [controller, setController] = useState<RunController | null>(null);
  const [mode, setMode] = useState<"production" | "recording">("production");
  const [recordingPersisted, setRecordingPersisted] = useState(true);
  const [pendingMarkerRemains, setPendingMarkerRemains] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [acting, setActing] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [clarificationText, setClarificationText] = useState("");
  const [modifiedTitle, setModifiedTitle] = useState("");
  const [actionError, setActionError] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const cancelTriggerRef = useRef<HTMLButtonElement>(null);
  const snapshot = useEvidenceRun(controller);

  useEffect(() => {
    let active = true;
    const recording = new URLSearchParams(window.location.search).get("demo") === "1";
    void loadEvidenceRun(runId, recording)
      .then((loaded) => {
        if (!active) return;
        setMode(loaded.mode);
        setRecordingPersisted(loaded.persisted);
        setPendingMarkerRemains(readPendingSubmission(loaded.mode === "recording").pending?.runId === runId);
        setController(new RunController(loaded.agent, loaded.receipt));
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : "无法加载 Run。");
      });
    return () => {
      active = false;
    };
  }, [runId]);

  useEffect(() => {
    if (snapshot) updateStoredRunView(runId, snapshot.view, snapshot.cursor);
  }, [runId, snapshot]);

  const timeline = useMemo(() => timelineFromEvents(snapshot?.events ?? []), [snapshot?.events]);
  const ledger = useMemo(() => ledgerFromEvents(snapshot?.events ?? []), [snapshot?.events]);
  const plan = useMemo(() => planFromEvents(snapshot?.events ?? []), [snapshot?.events]);
  const attention = useMemo(
    () => (snapshot ? attentionFromEvents(snapshot.events, snapshot.view.status) : null),
    [snapshot]
  );
  const selectedEvidence = ledger.find((item) => item.id === selectedEvidenceId) ?? ledger[0] ?? null;

  const dismissCancelDialog = useCallback(() => {
    setConfirmCancel(false);
    requestAnimationFrame(() => cancelTriggerRef.current?.focus());
  }, []);

  async function executeAction(action: () => Promise<void>, successAnnouncement: string) {
    setActing(true);
    setActionError("");
    try {
      await action();
      if (mode === "recording") await controller?.connect();
      setAnnouncement(successAnnouncement);
    } catch (error) {
      setActionError(actionErrorMessage(error));
    } finally {
      setActing(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!controller || !attention || attention.kind !== "approval") return;
    await executeAction(async () => {
      await controller.signal(decision, { interaction: "artifact-publication" }, attention.proposalDigest);
    }, decision === "approve" ? "审批已通过，研究继续执行。" : "写入已拒绝，研究按证据不足正常结束。");
  }

  async function provideClarification() {
    const text = clarificationText.trim();
    if (!controller || !attention || attention.kind !== "clarification" || !text) return;
    await executeAction(async () => {
      await controller.signal("provide_input", { text });
      setClarificationText("");
    }, "补充信息已提交，研究从同一 Run 继续执行。");
  }

  async function modifyArtifactTitle() {
    const title = modifiedTitle.trim();
    if (!controller || !attention || attention.kind !== "approval" || !title) return;
    await executeAction(async () => {
      await controller.signal("modify", { title }, attention.proposalDigest);
      setModifiedTitle("");
    }, `成果标题已更新为《${title}》，新的 Proposal Digest（提案指纹）已生成，请重新审批。`);
  }

  async function signalExecution(signal: "pause" | "resume") {
    if (!controller) return;
    await executeAction(async () => {
      await controller.signal(signal);
    }, signal === "pause" ? "Run 已暂停。" : "Run 已恢复并继续执行。");
  }

  async function cancelRun() {
    if (!controller) return;
    await executeAction(async () => {
      await controller.cancel("User cancelled from Run Workspace.");
      setConfirmCancel(false);
    }, "Run 已取消，后续步骤不会继续执行。");
  }

  if (loadError) {
    return (
      <div className={styles.emptyCard} role="alert">
        <div>
          <AlertTriangle aria-hidden="true" size={28} />
          <h1>无法打开这次研究</h1>
          <p>{loadError}</p>
          <Link className={styles.primaryAction} href="/workbench">
            返回研究工作台
          </Link>
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div aria-live="polite" className={styles.loadingState} role="status">
        <span>正在同步 Run 投影…</span>
      </div>
    );
  }

  const terminal = TERMINAL_RUN_STATUSES.has(snapshot.view.status);
  return (
    <div className={styles.page}>
      <p
        aria-atomic="true"
        aria-live="polite"
        className={styles.screenReaderStatus}
        data-testid="run-announcer"
        role="status"
      >
        {announcement}
      </p>
      {mode === "recording" && (
        <div aria-live="polite" className={styles.demoBanner} role="status">
          <ShieldAlert aria-hidden="true" size={18} />
          <div>
            <strong>演示模式 · 非真实执行</strong>
            <span>以下计划、事件与证据使用固定示例数据。</span>
            {!recordingPersisted && <span>浏览器未允许保存录制记录；当前页面会话可查看，刷新后无法保证恢复。</span>}
          </div>
        </div>
      )}
      {pendingMarkerRemains && <p role="status">本地仍有这项研究的待确认标记。原任务已打开，再次恢复只会打开同一任务；该标记不代表任务被取消。</p>}

      <header className={styles.runHeader}>
        <div className={styles.runHeaderTop}>
          <div>
            <p className={styles.kicker}>研究过程</p>
            <h1>{snapshot.view.goal}</h1>
            <div className={styles.runMeta}>
              <span translate="no">运行 {snapshot.view.id}</span>
              <span>·</span>
              <span>版本 {number(snapshot.view.version)}</span>
              <span>·</span>
              <span>事件位置 {number(snapshot.cursor)}</span>
              <span>·</span>
              <span>{costMeasurementLabel(snapshot.view.cost_measurement)}</span>
              <span>·</span>
              <span>{snapshot.connection === "live" ? "实时连接" : snapshot.connection === "error" ? "连接异常" : "事件已同步"}</span>
            </div>
          </div>
          <span
            aria-atomic="true"
            aria-live="polite"
            className={styles.statusBadge}
            data-attention={snapshot.view.status.startsWith("awaiting_")}
            data-terminal={terminal}
            role="status"
          >
            {runStatusLabel(snapshot.view.status)}
          </span>
        </div>
        <div className={styles.actionRow}>
          <Link className={styles.quietAction} href={`/runs${mode === "recording" ? "?demo=1" : ""}`}>
            <ArrowLeft aria-hidden="true" size={15} /> 运行记录
          </Link>
          {mode === "production" ? (
            <Link className={styles.quietAction} href={`/runs/${encodeURIComponent(runId)}/trace`}>
              查看运行轨迹
            </Link>
          ) : null}
          <RunLifecycleControls
            acting={acting}
            cancelButtonRef={cancelTriggerRef}
            confirmCancel={confirmCancel}
            onCancelRequest={() => setConfirmCancel(true)}
            onPause={() => void signalExecution("pause")}
            onResume={() => void signalExecution("resume")}
            status={snapshot.view.status}
          />
        </div>
        {confirmCancel && (
          <CancelRunDialog
            acting={acting}
            onConfirm={() => void cancelRun()}
            onDismiss={dismissCancelDialog}
          />
        )}
        {actionError && <p className={styles.errorMessage} role="alert">{actionError}</p>}
      </header>

      <ProductTermHelp terms={["agent", "run", "evidenceLedger", "revision"]} />

      {attention?.kind === "approval" && (
        <section className={styles.attentionCard} data-testid="attention-panel">
          <p className={styles.stepLabel}>需要你确认</p>
          <h2>需要你的批准</h2>
          <p>{attention.summary}</p>
          <p className={styles.monoBlock} translate="no">
            {attention.riskClass} → {attention.target}
          </p>
          <div className={styles.proposalDigest}>
            <strong>Proposal Digest（提案指纹）</strong>
            <code data-testid="proposal-digest" translate="no">{attention.proposalDigest}</code>
          </div>
          <p>提案指纹绑定本次待发布内容；标题变化会生成新指纹，并让旧批准立即失效。</p>
          <div className={styles.actionRow}>
            <button className={styles.primaryAction} disabled={acting} onClick={() => void decide("approve")} type="button">
              <Check aria-hidden="true" size={16} /> {acting ? "正在提交…" : "批准并继续"}
            </button>
            <button className={styles.quietAction} disabled={acting} onClick={() => void decide("reject")} type="button">
              拒绝写入
            </button>
          </div>
          <form
            className={styles.field}
            onSubmit={(event) => {
              event.preventDefault();
              void modifyArtifactTitle();
            }}
          >
            <label htmlFor="modified-artifact-title">新的成果标题</label>
            <input
              className={styles.input}
              id="modified-artifact-title"
              maxLength={255}
              onChange={(event) => setModifiedTitle(event.target.value)}
              placeholder="输入新的成果标题"
              value={modifiedTitle}
            />
            <small>只修改标题，不改变正文、claim（事实结论）、证据范围或 Artifact ID（产物标识）。</small>
            <div className={styles.actionRow}>
              <button className={styles.quietAction} disabled={acting || !modifiedTitle.trim()} type="submit">
                修改标题并重新审批
              </button>
            </div>
          </form>
        </section>
      )}

      {attention?.kind === "clarification" && (
        <section className={styles.attentionCard} data-testid="clarification-panel">
          <p className={styles.stepLabel}>需要你补充</p>
          <h2>需要补充一个限定条件</h2>
          <p>{attention.question}</p>
          <p className={styles.monoBlock} translate="no">
            requirement:{attention.targetRequirementOrdinal} · gate:{attention.gateId}
          </p>
          <form
            className={styles.field}
            onSubmit={(event) => {
              event.preventDefault();
              void provideClarification();
            }}
          >
            <label htmlFor="clarification-response">补充信息</label>
            <textarea
              className={styles.textarea}
              id="clarification-response"
              maxLength={500}
              onChange={(event) => setClarificationText(event.target.value)}
              placeholder="只补充 Agent 缺少的事实或范围，不需要重写整个目标。"
              required
              rows={3}
              value={clarificationText}
            />
            <div className={styles.actionRow}>
              <button className={styles.primaryAction} disabled={acting || !clarificationText.trim()} type="submit">
                <Check aria-hidden="true" size={16} /> {acting ? "正在提交…" : "补充并继续同一 Run"}
              </button>
            </div>
          </form>
        </section>
      )}

      <ResearchOutcomePanel view={snapshot.view} mode={mode} />

      <ResearchOverview ledger={ledger} view={snapshot.view} />

      {plan ? <ResearchPlanPanel plan={plan} /> : null}

      <div className={styles.runWorkspace}>
        <section className={styles.workspacePanel} data-testid="run-timeline">
          <div className={styles.panelHeading}>
            <h2>研究过程</h2>
            <span className={styles.count}>{number(timeline.length)} 个事件</span>
          </div>
          {timeline.length ? (
            <ol className={styles.timeline}>
              {timeline.map((item) => (
                <li className={styles.timelineItem} data-tone={item.tone} key={item.id}>
                  <span aria-hidden="true" className={styles.timelineDot} />
                  <div className={styles.timelineCopy}>
                    <strong>{item.label}</strong>
                    {item.detail && <span>{item.detail}</span>}
                    <span>位置 {number(item.cursor)}</span>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">等待第一个可公开运行事件…</p>
          )}
        </section>

        <section className={styles.workspacePanel} data-testid="evidence-ledger">
          <div className={styles.panelHeading}>
            <h2>证据账本</h2>
            <span className={styles.count}>{number(ledger.length)} 条证据</span>
          </div>
          {ledger.length ? (
            <div className={styles.ledgerList}>
              {ledger.map((item) => (
                <EvidenceCard item={item} key={item.id} onSelect={() => setSelectedEvidenceId(item.id)} selected={selectedEvidence?.id === item.id} />
              ))}
            </div>
          ) : (
            <div className={styles.inspectorEmpty}>证据尚未入账。Ledger 只显示经过引用身份校验的记录。</div>
          )}
        </section>

        <aside aria-label="证据详情" className={styles.inspectorPanel} data-testid="evidence-inspector">
          <div className={styles.panelHeading}>
            <h2>证据详情</h2>
            <span className={styles.count}>固定引用</span>
          </div>
          {selectedEvidence ? <EvidenceInspector item={selectedEvidence} /> : <div className={styles.inspectorEmpty}>选择一条证据查看 revision、hash 与 locator。</div>}
        </aside>
      </div>
    </div>
  );
}

export function ResearchOutcomePanel({ view, mode }: {
  view: Pick<RunView, "status" | "final_artifact_id" | "termination_reason">;
  mode: "production" | "recording";
}) {
  const gap = view.status === "insufficient_evidence";
  if (!gap && (view.status !== "completed" || !view.final_artifact_id)) return null;
  return <section aria-live="polite" className={styles.outcomeCard}>
    <p className={styles.stepLabel}>研究结果</p>
    <h2>{gap ? "证据不足，Run 已正常结束" : "研究已完成"}</h2>
    <p>{gap ? view.termination_reason ?? "已保留缺口与下一步检索建议，没有生成无依据结论。"
      : mode === "recording" ? "录制样例已结束；可以练习打开引用，但示例结论没有经过真实模型和资料核验。"
        : "成果已经通过结论—证据校验并发布；可以逐条打开引用，核对来源版本和原文位置。"}</p>
    {view.final_artifact_id && <Link className={styles.primaryAction}
      href={`/artifacts/${encodeURIComponent(view.final_artifact_id)}${mode === "recording" ? "?demo=1" : ""}`}>
      <FileCheck2 aria-hidden="true" size={17} /> {gap ? "查看缺口报告" : "查看研究成果"}
    </Link>}
  </section>;
}

export function ResearchPlanPanel({ plan }: { plan: ResearchPlan }) {
  return (
    <section className={styles.planCard} data-testid="research-plan">
      <div className={styles.panelHeading}>
        <h2>研究计划</h2>
        <span className={styles.count}>版本 {number(plan.version)}</span>
      </div>
      <p>Agent 将目标拆成可独立检索、逐项核验的公开事实要求；这里不展示内部推理过程。</p>
      <ol className={styles.planRequirements}>
        {plan.requirements.map((requirement, index) => (
          <li key={`${index}:${requirement}`}>{requirement}</li>
        ))}
      </ol>
      <span className={styles.planStrategy} translate="no">计划方式：{plan.strategy}</span>
    </section>
  );
}

function costMeasurementLabel(value: "reported" | "estimated" | "unknown" | "partial_unknown") {
  const labels = {
    reported: "成本：Provider 上报",
    estimated: "成本：估算",
    unknown: "成本：未知",
    partial_unknown: "成本：部分未知"
  } as const;
  return labels[value];
}

function actionErrorMessage(error: unknown): string {
  return `${error instanceof Error ? error.message : "命令提交失败。"} Run 状态未在本地乐观修改，请同步后重试。`;
}

const TERMINAL_RUN_STATUSES = new Set<RunView["status"]>([
  "completed",
  "insufficient_evidence",
  "cancelled",
  "failed"
]);

type CancelRunDialogProps = {
  acting: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
};

export function CancelRunDialog({ acting, onConfirm, onDismiss }: CancelRunDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const dismissRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    dismissRef.current?.focus();
  }, []);

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onDismiss();
      return;
    }
    if (event.key !== "Tab") return;
    if (event.shiftKey && document.activeElement === confirmRef.current) {
      event.preventDefault();
      dismissRef.current?.focus();
    } else if (!event.shiftKey && document.activeElement === dismissRef.current) {
      event.preventDefault();
      confirmRef.current?.focus();
    }
  }

  return (
    <div
      aria-describedby="cancel-description"
      aria-labelledby="cancel-title"
      aria-modal="true"
      className={styles.attentionCard}
      onKeyDown={handleKeyDown}
      role="alertdialog"
    >
      <h2 id="cancel-title">确认取消这个 Run？</h2>
      <p id="cancel-description">取消会作为可审计命令写入运行记录；不会只是在浏览器里断开连接。</p>
      <div className={styles.actionRow}>
        <button
          className={styles.dangerAction}
          disabled={acting}
          onClick={onConfirm}
          ref={confirmRef}
          type="button"
        >
          确认取消
        </button>
        <button className={styles.quietAction} onClick={onDismiss} ref={dismissRef} type="button">
          继续研究
        </button>
      </div>
    </div>
  );
}

type RunLifecycleControlsProps = {
  acting: boolean;
  cancelButtonRef?: RefObject<HTMLButtonElement | null>;
  confirmCancel: boolean;
  onCancelRequest: () => void;
  onPause: () => void;
  onResume: () => void;
  status: RunView["status"];
};

export function RunLifecycleControls({
  acting,
  cancelButtonRef,
  confirmCancel,
  onCancelRequest,
  onPause,
  onResume,
  status
}: RunLifecycleControlsProps) {
  return (
    <>
      {status === "running" ? (
        <button className={styles.quietAction} disabled={acting} onClick={onPause} type="button">
          <Pause aria-hidden="true" size={15} /> 暂停 Run
        </button>
      ) : null}
      {status === "paused" ? (
        <button className={styles.quietAction} disabled={acting} onClick={onResume} type="button">
          <Play aria-hidden="true" size={15} /> 继续 Run
        </button>
      ) : null}
      {!TERMINAL_RUN_STATUSES.has(status) && !confirmCancel ? (
        <button
          className={styles.dangerAction}
          disabled={acting}
          onClick={onCancelRequest}
          ref={cancelButtonRef}
          type="button"
        >
          <Square aria-hidden="true" size={14} /> 取消 Run
        </button>
      ) : null}
    </>
  );
}

export function EvidenceCard({ item, onSelect, selected = false }: { item: LedgerItem; onSelect: () => void; selected?: boolean }) {
  const reason = evidenceReasonLabel(item.reason);
  return (
    <article className={styles.ledgerCard} data-relation={item.relation} data-selected={selected}>
      <button aria-label={`检查证据 ${item.sourceTitle}`} aria-pressed={selected} onClick={onSelect} type="button">
        <strong>{item.sourceTitle}</strong>
      </button>
      <blockquote>“{item.excerpt}”</blockquote>
      <span className={styles.relation}>{evidenceRelationLabel(item.relation)}</span>
      {reason ? <p className={styles.relationReason}>{reason}</p> : null}
      <div className={styles.ledgerMeta} translate="no">
        <span>revision:{item.reference.revision_id}</span>
        <span>chunk:{item.reference.chunk_id}</span>
      </div>
    </article>
  );
}

function EvidenceInspector({ item }: { item: LedgerItem }) {
  return (
    <div className={styles.inspectorContent}>
      <h3>{item.sourceTitle}</h3>
      <p className={styles.excerpt}>{item.excerpt}</p>
      <dl>
        <dt>来源</dt>
        <dd>{item.reference.source_id}</dd>
        <dt>版本</dt>
        <dd>{item.reference.revision_id}</dd>
        <dt>证据片段</dt>
        <dd>{item.reference.chunk_id}</dd>
        <dt>原文位置</dt>
        <dd>{formatLocator(item.reference.locator)}</dd>
        <dt>SHA-256</dt>
        <dd>{item.reference.content_hash}</dd>
        <dt>证据关系</dt>
        <dd>{evidenceRelationLabel(item.relation)}</dd>
        {item.reason ? <><dt>判定原因</dt><dd>{evidenceReasonLabel(item.reason)}</dd></> : null}
      </dl>
    </div>
  );
}

function formatLocator(locator: LedgerItem["reference"]["locator"]): string {
  if (locator.kind === "page" || locator.kind === "document_page") return `page:${locator.page_number}`;
  if (locator.kind === "pdf_page") return `page:${locator.page ?? locator.page_number}`;
  if (locator.kind === "time" || locator.kind === "media_time") return `${locator.start_ms}–${locator.end_ms ?? "?"}ms`;
  if (locator.kind === "code" || locator.kind === "code_range") return `${locator.file_path}:${locator.line_start}-${locator.line_end ?? locator.line_start}`;
  if (locator.kind === "region") return `region:${locator.region.join(",")}`;
  if (locator.kind === "image_region") return "image region";
  if (locator.kind === "text") return `text:${locator.start_offset ?? 0}-${locator.end_offset ?? "?"}`;
  return "document chunk";
}

const numberFormatter = new Intl.NumberFormat("zh-CN");
function number(value: number): string {
  return numberFormatter.format(value);
}
