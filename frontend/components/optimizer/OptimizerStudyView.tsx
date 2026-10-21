"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { formatDateTime } from "@/modules/agent-control/format";
import { OptimizerClient } from "@/modules/optimizer/client";
import type {
  CategoryComparison,
  DiffReceipt,
  StudyEventCatalog,
  StudyOverview
} from "@/modules/optimizer/contract";
import { actionLabel, objectiveLabel, statusLabel, type WorkbenchAction } from "@/modules/optimizer/presenter";
import styles from "./OptimizerWorkbench.module.css";


const percentFormatter = new Intl.NumberFormat("zh-CN", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1
});
const integerFormatter = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });


export function OptimizerStudyView({ studyId }: { studyId: string }) {
  const client = useMemo(() => new OptimizerClient(), []);
  const [overview, setOverview] = useState<StudyOverview | null>(null);
  const [events, setEvents] = useState<StudyEventCatalog["items"]>([]);
  const [selectedTrialIds, setSelectedTrialIds] = useState<string[]>([]);
  const [comparisonMarkdown, setComparisonMarkdown] = useState("");
  const [diff, setDiff] = useState<DiffReceipt | null>(null);
  const [categories, setCategories] = useState<CategoryComparison | null>(null);
  const [busyAction, setBusyAction] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loadSequence = useRef(0);
  const actionInFlight = useRef(false);
  const pendingRound = useRef<{ round: number; id: string } | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    const sequence = ++loadSequence.current;
    try {
      const [nextOverview, nextEvents] = await Promise.all([
        client.getOverview(studyId, signal),
        client.getEvents(studyId, signal)
      ]);
      if (signal?.aborted || sequence !== loadSequence.current) return;
      setOverview(nextOverview);
      setEvents(nextEvents.items);
    } catch (reason) {
      if (signal?.aborted || sequence !== loadSequence.current) return;
      setError("无法更新实验数据，请点击刷新重试。" + (reason instanceof Error ? reason.message : ""));
    } finally {
      if (!signal?.aborted && sequence === loadSequence.current) setLoading(false);
    }
  }, [client, studyId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (overview?.study.status !== "running" || busyAction) return;
    const controller = new AbortController();
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (disposed) return;
      if (document.visibilityState !== "hidden") await load(controller.signal);
      if (!disposed) timer = setTimeout(() => void poll(), 2_000);
    };
    timer = setTimeout(() => void poll(), 2_000);
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [overview?.study.status, busyAction, load]);

  async function runAction(action: WorkbenchAction) {
    if (!overview || actionInFlight.current) return;
    if (
      (action === "cancel" || action === "fail")
      && !globalThis.confirm(action === "cancel" ? "确认取消这个优化实验？" : "确认将这个优化实验终止为失败？")
    ) return;
    actionInFlight.current = true;
    setBusyAction(action);
    setError("");
    try {
      if (action === "start") await client.startStudy(studyId);
      if (action === "cancel") await client.cancelStudy(studyId);
      if (action === "fail") await client.failStudy(studyId, "operator stopped from optimizer workbench");
      if (action === "recover") await client.recoverStudy(studyId);
      if (action === "next-round") {
        if (pendingRound.current?.round !== overview.study.round_no) {
          pendingRound.current = { round: overview.study.round_no, id: crypto.randomUUID() };
        }
        await client.startNextRound(studyId, pendingRound.current.id);
      }
      if (action === "retry") {
        const failed = overview.trials.find((trial) => trial.status === "failed");
        if (failed) await client.retryTrial(failed.id);
      }
      if (action === "convert-draft") {
        const candidate = overview.recommendation.find((item) => !item.converted);
        if (candidate) await client.convertToDraft(studyId, candidate.trial_id, crypto.randomUUID());
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "操作未完成，请检查实验状态后重试。");
    } finally {
      actionInFlight.current = false;
      setBusyAction("");
    }
  }

  async function compare() {
    setBusyAction("compare");
    setError("");
    try {
      const report = await client.exportComparison(studyId, selectedTrialIds, true);
      setComparisonMarkdown(report.markdown);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法导出 Trial 对比报告。");
    } finally {
      setBusyAction("");
    }
  }

  async function inspectTrial() {
    const trialId = selectedTrialIds[0];
    if (!trialId) return;
    setBusyAction("inspect");
    setError("");
    setDiff(null);
    setCategories(null);
    try {
      const nextDiff = await client.getDiff(studyId, trialId);
      setDiff(nextDiff);
      try { setCategories(await client.getCategories(studyId, trialId)); }
      catch (reason) {
        setError("分类数据读取失败；请重新检查所选候选。" + (reason instanceof Error ? reason.message : ""));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法检查 Trial 详情。");
    } finally {
      setBusyAction("");
    }
  }

  if (loading) return <div aria-live="polite" className={styles.loading} role="status">正在重建实验全景…</div>;
  if (!overview) return <section className={styles.loading} role="alert"><div><h1>无法打开优化实验</h1><p>{error || "实验不存在或返回结构不完整。"}</p><button className={styles.button} onClick={() => void load()} type="button">重新加载</button></div></section>;

  return (
    <OptimizerStudyContent
      busyAction={busyAction}
      categories={categories}
      comparisonMarkdown={comparisonMarkdown}
      diff={diff}
      error={error}
      events={events}
      onAction={(action) => void runAction(action)}
      onCompare={() => void compare()}
      onInspect={() => void inspectTrial()}
      onRefresh={() => { setError(""); void load(); }}
      onSelectionChange={(trialId, checked) => setSelectedTrialIds((current) => checked ? [...current, trialId].slice(-3) : current.filter((item) => item !== trialId))}
      overview={overview}
      selectedTrialIds={selectedTrialIds}
    />
  );
}

export function OptimizerStudyContent({
  overview, events, selectedTrialIds, comparisonMarkdown, busyAction, error,
  diff = null, categories = null, onAction, onCompare, onSelectionChange, onInspect = () => undefined,
  onRefresh = () => undefined
}: {
  overview: StudyOverview;
  events: StudyEventCatalog["items"];
  selectedTrialIds: string[];
  comparisonMarkdown: string;
  busyAction: string;
  error: string;
  diff?: DiffReceipt | null;
  categories?: CategoryComparison | null;
  onAction: (action: WorkbenchAction) => void;
  onCompare: () => void;
  onSelectionChange: (trialId: string, checked: boolean) => void;
  onInspect?: () => void;
  onRefresh?: () => void;
}) {
  const study = overview.study;
  const frontierIds = new Set(overview.frontier.map((item) => item.trial_id));
  const availableActions = overview.actions.filter((item) => item.available);
  return (
    <div className={styles.page} data-testid="optimizer-study-page" data-study-status={study.status}>
      <div aria-live="polite" className={styles.toolbar}>
        <span>{study.status === "running" ? "后台正在运行，进度每 2 秒更新。" : "显示已保存的实验结果。"}</span>
        <button className={styles.quietButton} disabled={Boolean(busyAction)} onClick={onRefresh} type="button">刷新实验</button>
      </div>
      <header className={styles.hero}><div><p className={styles.eyebrow}>Experiment Workbench · 实验工作台</p><h1>{study.label}</h1><p className={styles.lead}>页面只显示持久化 Study、Trial、评测和事件事实。按钮是否可用完全由后端状态机决定。</p></div><div className={styles.actions}><Link className={styles.quietButton} href="/policies/optimizer">返回实验列表</Link><Link className={styles.quietButton} href={`/policies/${encodeURIComponent(study.base_policy_id)}`}>打开基准策略</Link></div></header>
      {error ? <p aria-live="polite" className={styles.error} role="alert">{error}</p> : null}

      <section aria-label="实验摘要" className={styles.summaryGrid}>
        <article className={styles.card}><span className={styles.status} data-state={study.status === "failed" ? "error" : study.status === "running" ? "warning" : undefined}>{statusLabel(study.status)}</span><h2>第 {study.round_no} 轮</h2><p>{objectiveLabel(study.objective)}</p></article>
        <article className={styles.card}><span className={styles.status}>候选预算</span><h2>{study.budget_usage.created_trials} / {study.budget.max_candidates}</h2><p>max_candidates 是整个 Study 的累计上限。</p></article>
        <article className={styles.card}><span className={styles.status}>评测预算</span><h2>{study.budget_usage.started_evaluations} / {study.budget.max_evaluations}</h2><p>确定性评测必须保持 0 次外部 Provider 调用。</p></article>
      </section>

      <section className={styles.panel}><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>01 / Actions</p><h2>状态机允许的操作</h2><p>不可用的动作不会由前端自行猜测或强行调用。</p></div></div><div className={styles.toolbar}>{availableActions.map((item) => <button className={item.action === "convert-draft" ? styles.button : styles.quietButton} disabled={Boolean(busyAction)} key={item.action} onClick={() => onAction(item.action)} title={item.reason} type="button">{busyAction === item.action ? "正在处理…" : actionLabel(item.action)}</button>)}</div><ul className={styles.factList}>{overview.actions.map((item) => <li key={item.action}><strong>{actionLabel(item.action)}</strong><span>{item.reason}</span></li>)}</ul></section>

      <section><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>02 / Rounds</p><h2>轮次摘要</h2></div></div><div className={styles.roundGrid}>{overview.rounds.map((round) => <article className={styles.card} key={round.round_no}><span className={styles.status}>Round {round.round_no}</span><h2>{round.completed} / {round.total} 已完成</h2><p>失败 {round.failed} · 取消 {round.cancelled}</p><span className={styles.mono}>最佳分数 {round.best_score_millis ?? "尚无"}</span></article>)}</div></section>

      <section className={styles.panel}><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>03 / Trials</p><h2>候选 Trial</h2><p>勾选 2–3 个已完成 Trial 生成确定性对比报告；勾选 1 个查看策略差异与分类表现。</p></div><div className={styles.toolbar}><button className={styles.quietButton} disabled={selectedTrialIds.length !== 1 || Boolean(busyAction)} onClick={onInspect} type="button">检查所选 Trial</button><button className={styles.button} disabled={selectedTrialIds.length < 2 || selectedTrialIds.length > 3 || Boolean(busyAction)} onClick={onCompare} type="button">{busyAction === "compare" ? "正在生成…" : "导出对比"}</button></div></div><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>选择</th><th>Trial</th><th>轮次</th><th>状态</th><th>分数</th><th>通过率</th><th>证据召回</th><th>延迟</th><th>资格</th><th>结果</th></tr></thead><tbody>{overview.trials.map((trial) => <tr key={trial.id}><td><label className={styles.checkbox}><input aria-label={`选择 Trial ${trial.ordinal}`} checked={selectedTrialIds.includes(trial.id)} disabled={trial.status !== "completed"} onChange={(event) => onSelectionChange(trial.id, event.target.checked)} type="checkbox" /><span>#{trial.ordinal}</span></label></td><td className={styles.mono} translate="no">{trial.id}</td><td data-numeric="true">{trial.round_no}</td><td>{statusLabel(trial.status)}</td><td data-numeric="true">{trial.score_millis ?? "—"}</td><td data-numeric="true">{formatMetric(trial.metrics?.case_pass_rate)}</td><td data-numeric="true">{formatMetric(trial.metrics?.mean_source_recall)}</td><td data-numeric="true">{trial.metrics ? `${integerFormatter.format(trial.metrics.latency_ms)} ms` : "—"}</td><td>{trial.eligible ? "通过硬门" : "不具备资格"}{frontierIds.has(trial.id) ? " · Pareto" : ""}</td><td>{trial.draft_policy_id ? <Link href={`/policies/${encodeURIComponent(trial.draft_policy_id)}`}>打开草稿</Link> : trial.failure_code ?? "—"}</td></tr>)}</tbody></table></div></section>

      {diff ? <section className={styles.panel}><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>04 / Diff</p><h2>与当前活动策略的字段差异</h2></div></div>{diff.changes.length ? <ul className={styles.factList}>{diff.changes.map((change) => <li key={change.field}><strong>{change.field}</strong><span>{change.left} → {change.right}</span></li>)}</ul> : <p>配置没有字段变化。</p>}{categories ? <div><h3>分类表现</h3><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>类别</th><th>胜</th><th>平</th><th>负</th><th>结论</th></tr></thead><tbody>{categories.items.map((item) => <tr key={item.category}><td>{item.category}</td><td>{item.wins}</td><td>{item.ties}</td><td>{item.losses}</td><td>{item.verdict}</td></tr>)}</tbody></table></div></div> : <p>该 Trial 暂无完整分类案例事实。</p>}</section> : null}

      <section><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>05 / Recommendation</p><h2>推荐候选</h2><p>Pareto Frontier（帕累托前沿）表示没有被其他候选在全部指标上全面超过。</p></div></div>{overview.recommendation.length ? <div className={styles.recommendationGrid}>{overview.recommendation.map((item) => <article className={styles.card} key={item.trial_id}><span className={styles.status}>推荐 #{item.rank}</span><h2>Trial {item.trial_id}</h2><p>{item.rationale_first_line}</p><span className={styles.mono}>score {item.score_millis ?? "—"}</span>{item.draft_policy_id ? <Link className={styles.quietButton} href={`/policies/${encodeURIComponent(item.draft_policy_id)}`}>打开已转换草稿</Link> : null}</article>)}</div> : <div className={styles.card}><h2>暂无可推荐候选</h2><p>等待 Trial 完成并通过全部 Hard Gate（硬性安全门）。</p></div>}</section>

      <section className={styles.panel}><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>06 / Report</p><h2>Trial 对比报告</h2></div></div>{comparisonMarkdown ? <div aria-label="Trial 对比 Markdown 报告" className={styles.report} role="region">{comparisonMarkdown.split("\n").map((line, index) => <div key={`${index}:${line}`}>{line || " "}</div>)}</div> : <p>选择 2–3 个已完成 Trial 后生成报告。</p>}</section>

      <section className={styles.panel}><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>07 / Events</p><h2>实验事件证据</h2><p>事件按持久化顺序展示，不重新运行算法。</p></div><span className={styles.status}>{events.length} 个事件</span></div>{events.length ? <ol className={styles.eventList}>{events.map((event) => <li key={event.id}><strong>{event.event_type}</strong><span>Round {event.round_no} · {formatDateTime(event.created_at, { includeSeconds: true })}</span>{publicEventFacts(event.payload).map((fact) => <span className={styles.mono} key={fact} translate="no">{fact}</span>)}</li>)}</ol> : <p>暂无事件。</p>}</section>
      <p className={styles.honesty} role="note">Optimizer（优化器）只生成、评测和推荐候选；转换操作最多创建 Draft（草稿），不会自动激活。</p>
    </div>
  );
}

function publicEventFacts(payload: Record<string, unknown>): string[] {
  return Object.entries(payload).flatMap(([key, value]) => {
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return [`${key}=${value}`];
    if (Array.isArray(value) && value.every((item) => typeof item === "string")) return [`${key}=${value.join(",")}`];
    return [];
  });
}

function formatMetric(value: number | undefined): string {
  return value === undefined ? "—" : percentFormatter.format(value);
}
