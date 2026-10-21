"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentControlClient } from "@/modules/agent-control/client";
import type {
  EvaluationComparison,
  EvaluationStatus,
  EvaluationSummary
} from "@/modules/agent-control/contract";
import {
  formatDateTime,
  formatMetricValue,
  formatNumber,
  formatPercentage
} from "@/modules/agent-control/format";
import {
  comparisonVerdictLabel,
  evaluationStatusLabel,
  metricLabel
} from "@/modules/agent-control/presenter";
import styles from "./AgentControl.module.css";


export function EvaluationIndex() {
  const client = useMemo(() => new AgentControlClient(), []);
  const router = useRouter();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<EvaluationSummary[]>([]);
  const [comparisonItems, setComparisonItems] = useState<EvaluationSummary[]>([]);
  const [label, setLabel] = useState("V5.7 固定回归评测");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState<EvaluationComparison | null>(null);
  const [error, setError] = useState("");
  const leftId = safeSearchId(searchParams.get("left"));
  const rightId = safeSearchId(searchParams.get("right"));
  const statusFilter = safeEvaluationStatus(searchParams.get("status"));

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [all, filteredByStatus] = await Promise.all([
        client.listEvaluations({ limit: 100 }),
        statusFilter
          ? client.listEvaluations({ status: statusFilter, limit: 100 })
          : Promise.resolve(null)
      ]);
      const filtered = filteredByStatus ?? all;
      setComparisonItems(all.items);
      setItems(filtered.items);
    } catch (reason) {
      setItems([]);
      setComparisonItems([]);
      setError(reason instanceof Error ? reason.message : "无法加载评测历史。");
    } finally {
      setLoading(false);
    }
  }, [client, statusFilter]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setComparison(null); }, [leftId, rightId]);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!label.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const receipt = await client.startEvaluation({
        request_id: crypto.randomUUID(),
        label: label.trim()
      });
      router.push(`/evaluations/${encodeURIComponent(receipt.evaluation_id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法启动固定评测。");
      setSubmitting(false);
    }
  }

  function select(side: "left" | "right", value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(side, value); else next.delete(side);
    router.replace(`/evaluations${next.size ? `?${next}` : ""}`);
  }

  function filterByStatus(value: string) {
    const next = new URLSearchParams(searchParams.toString());
    const status = safeEvaluationStatus(value);
    if (status) next.set("status", status); else next.delete("status");
    router.replace(`/evaluations${next.size ? `?${next}` : ""}`);
  }

  async function compare() {
    if (!leftId || !rightId || leftId === rightId) return;
    setComparing(true);
    setError("");
    try {
      setComparison(await client.compareEvaluations(leftId, rightId));
    } catch (reason) {
      setComparison(null);
      setError(reason instanceof Error ? reason.message : "无法比较评测快照。");
    } finally {
      setComparing(false);
    }
  }

  return (
    <div className={styles.page} data-testid="evaluation-index-page">
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Evaluation Studio · 智能体评测中心</p>
          <h1>每次升级，先证明没有退步</h1>
          <p className={styles.lead}>运行固定 60 场景评测，保留历史快照，再比较策略、检索、引用和恢复能力的变化。</p>
        </div>
        <div className={styles.actionRow}>
          <Link className={styles.quietButton} href="/runs">返回运行记录</Link>
          <Link className={styles.quietButton} href="/policies">策略实验室</Link>
        </div>
      </header>

      <form className={styles.startForm} onSubmit={start}>
        <div className={styles.field}>
          <label htmlFor="evaluation-label">这次评测叫什么</label>
          <input
            autoComplete="off"
            className={styles.input}
            id="evaluation-label"
            maxLength={120}
            name="evaluation_label"
            onChange={(event) => setLabel(event.target.value)}
            placeholder="例如：检索策略修改前基线…"
            value={label}
          />
        </div>
        <button className={styles.button} disabled={submitting || !label.trim()} type="submit">
          {submitting ? "正在提交…" : "运行固定评测"}
        </button>
      </form>

      <p className={styles.honestyNote} role="note">
        当前只运行本地确定性评测：不读取真实模型密钥，不调用付费 API，也不代表真实模型回答质量。
      </p>
      {error ? <p className={styles.inlineError} role="alert">{error}</p> : null}

      {loading ? (
        <div aria-live="polite" className={styles.loading} role="status">正在加载评测历史…</div>
      ) : (
        <EvaluationCatalogView
          comparing={comparing}
          comparison={comparison}
          comparisonItems={comparisonItems}
          items={items}
          leftId={leftId}
          onCompare={() => void compare()}
          onSelect={select}
          onStatusFilter={filterByStatus}
          rightId={rightId}
          statusFilter={statusFilter}
        />
      )}
    </div>
  );
}


export function EvaluationCatalogView({
  comparing,
  comparison,
  comparisonItems,
  items,
  leftId,
  onCompare,
  onSelect,
  onStatusFilter,
  rightId,
  statusFilter
}: {
  comparing: boolean;
  comparison: EvaluationComparison | null;
  comparisonItems: EvaluationSummary[];
  items: EvaluationSummary[];
  leftId: string;
  onCompare: () => void;
  onSelect: (side: "left" | "right", value: string) => void;
  onStatusFilter: (value: string) => void;
  rightId: string;
  statusFilter: EvaluationStatus | "";
}) {
  const completed = comparisonItems.filter((item) => item.status === "passed" || item.status === "failed");
  return (
    <>
      <section className={styles.panel} data-testid="evaluation-comparison">
        <div className={styles.panelHeader}>
          <div>
            <p className={styles.sectionIndex}>01 / Compare</p>
            <h2>比较两次评测</h2>
            <p>左边是基线，右边是修改后。数据集不同会明确显示“不可比较”。</p>
          </div>
        </div>
        <div className={styles.comparisonControls}>
          <div className={styles.field}>
            <label htmlFor="evaluation-left">基线快照</label>
            <select className={styles.select} id="evaluation-left" name="left_evaluation" onChange={(event) => onSelect("left", event.target.value)} value={leftId}>
              <option value="">请选择…</option>
              {completed.map((item) => <option key={item.id} value={item.id}>{item.label} · {evaluationStatusLabel(item.status)}</option>)}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="evaluation-right">修改后快照</label>
            <select className={styles.select} id="evaluation-right" name="right_evaluation" onChange={(event) => onSelect("right", event.target.value)} value={rightId}>
              <option value="">请选择…</option>
              {completed.map((item) => <option key={item.id} value={item.id}>{item.label} · {evaluationStatusLabel(item.status)}</option>)}
            </select>
          </div>
          <button className={styles.button} disabled={comparing || !leftId || !rightId || leftId === rightId} onClick={onCompare} type="button">
            {comparing ? "正在比较…" : "开始比较"}
          </button>
        </div>
        {comparison ? <ComparisonResult comparison={comparison} /> : null}
      </section>

      <section>
        <div className={styles.panelHeader}>
          <div><p className={styles.sectionIndex}>02 / History</p><h2>评测历史</h2><p>{items.length} 个符合当前条件的持久化快照。</p></div>
          <div className={styles.filterField}>
            <label htmlFor="evaluation-status-filter">按状态筛选</label>
            <select
              className={styles.select}
              id="evaluation-status-filter"
              name="status_filter"
              onChange={(event) => onStatusFilter(event.target.value)}
              value={statusFilter}
            >
              <option value="">全部状态</option>
              <option value="queued">排队中</option>
              <option value="running">运行中</option>
              <option value="passed">已通过</option>
              <option value="failed">未通过</option>
            </select>
          </div>
        </div>
        {items.length ? (
          <div className={styles.catalogGrid}>
            {items.map((item) => (
              <article className={styles.catalogCard} key={item.id}>
                <div className={styles.catalogCardFooter}>
                  <span className={styles.status} data-state={item.status === "failed" ? "error" : item.status === "passed" ? "ok" : "warning"}>
                    {evaluationStatusLabel(item.status)}
                  </span>
                  <span className={styles.meta}>{formatDateTime(item.created_at)}</span>
                </div>
                <div><h2>{item.label}</h2><p className={styles.meta} translate="no">{item.id}</p></div>
                <p>{item.case_count ? `${formatNumber(item.case_count)} 个案例 · 通过率 ${formatPercentage(item.case_pass_rate)}` : "等待评测结果写回。"}</p>
                <div className={styles.catalogCardFooter}>
                  <span className={styles.meta}>外部调用 {item.external_provider_calls ?? "未核验"}</span>
                  <Link className={styles.quietButton} href={`/evaluations/${encodeURIComponent(item.id)}`}>打开评测详情</Link>
                </div>
              </article>
            ))}
          </div>
        ) : <div className={styles.loading}>还没有评测记录。运行第一份固定评测后，历史会保存在这里。</div>}
      </section>
    </>
  );
}


function ComparisonResult({ comparison }: { comparison: EvaluationComparison }) {
  return (
    <div className={styles.comparisonResult} role="status">
      <span className={styles.status} data-state={comparison.verdict === "regressed" ? "error" : comparison.verdict === "incomparable" ? "warning" : "ok"}>
        {comparisonVerdictLabel(comparison.verdict)}
      </span>
      <h3>{comparison.compatible ? "两个快照可以直接比较" : "两个快照不能直接下质量结论"}</h3>
      <p>
        Policy Fingerprint（策略指纹）{comparison.policy_changed ? "已变化：这次对比包含策略改动。" : "一致：两次使用同一套策略定义。"}
      </p>
      <div className={styles.twoColumns}>
        <div className={styles.monoBlock} translate="no">Baseline Policy<br />{comparison.left_policy_fingerprint}</div>
        <div className={styles.monoBlock} translate="no">Changed Policy<br />{comparison.right_policy_fingerprint}</div>
      </div>
      {comparison.incompatibility_reasons.length ? <p>{comparison.incompatibility_reasons.join(" / ")}</p> : null}
      {comparison.metric_deltas.length ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption className={styles.visuallyHidden}>基线评测与修改后评测的指标变化</caption>
            <thead><tr><th scope="col">指标</th><th scope="col">基线</th><th scope="col">修改后</th><th scope="col">变化</th></tr></thead>
            <tbody>{comparison.metric_deltas.map((item) => (
              <tr key={item.metric}>
                <td>{metricLabel(item.metric)}</td>
                <td data-numeric="true">{formatMetricValue(item.metric, item.left)}</td>
                <td data-numeric="true">{formatMetricValue(item.metric, item.right)}</td>
                <td data-numeric="true">{item.delta > 0 ? "+" : ""}{formatMetricValue(item.metric, item.delta)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : null}
      {comparison.gate_changes.length ? (
        <ul className={styles.factList}>
          {comparison.gate_changes.map((change) => (
            <li key={change.gate}>
              <strong>{change.gate}</strong>
              <span>{change.left ? "通过" : "失败"} → {change.right ? "通过" : "失败"}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {comparison.new_failure_case_ids.length ? <p>新增失败：{comparison.new_failure_case_ids.join("、")}</p> : null}
      {comparison.resolved_failure_case_ids.length ? <p>已修复：{comparison.resolved_failure_case_ids.join("、")}</p> : null}
    </div>
  );
}


function safeSearchId(value: string | null): string {
  return value && /^[A-Za-z0-9_-]{1,36}$/.test(value) ? value : "";
}

function safeEvaluationStatus(value: string | null): EvaluationStatus | "" {
  return value === "queued" || value === "running" || value === "passed" || value === "failed"
    ? value
    : "";
}
