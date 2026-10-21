"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentControlClient } from "@/modules/agent-control/client";
import type { EvaluationDetail } from "@/modules/agent-control/contract";
import {
  formatDateTime,
  formatDuration,
  formatMetricValue,
  formatNumber,
  formatPercentage
} from "@/modules/agent-control/format";
import {
  evaluationStatusLabel,
  failureCategoryLabel,
  metricLabel
} from "@/modules/agent-control/presenter";
import styles from "./AgentControl.module.css";


export function EvaluationDetailView() {
  const params = useParams<{ evaluationId: string }>();
  const evaluationId = decodeURIComponent(params.evaluationId);
  const router = useRouter();
  const client = useMemo(() => new AgentControlClient(), []);
  const [detail, setDetail] = useState<EvaluationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const initial = await client.getEvaluation(evaluationId, signal);
      setDetail(initial);
      if (initial.summary.status === "queued" || initial.summary.status === "running") {
        setDetail(await client.waitForEvaluation(evaluationId, { signal }));
      }
    } catch (reason) {
      if (signal?.aborted) return;
      setDetail(null);
      setError(reason instanceof Error ? reason.message : "无法加载评测详情。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [client, evaluationId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function rerun() {
    if (!detail) return;
    setRerunning(true);
    setError("");
    try {
      const suffix = " · 重新运行";
      const receipt = await client.startEvaluation({
        request_id: crypto.randomUUID(),
        label: `${detail.summary.label.slice(0, 120 - suffix.length)}${suffix}`
      });
      router.push(`/evaluations/${encodeURIComponent(receipt.evaluation_id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法重新运行评测。");
      setRerunning(false);
    }
  }

  if (loading && !detail) return <div aria-live="polite" className={styles.loading} role="status">正在等待评测结果…</div>;
  if (!detail) {
    return (
      <section className={styles.error} role="alert">
        <div><h1>无法打开评测详情</h1><p>{error || "评测不存在。"} 系统不会回退到演示报告。</p>
          <div className={styles.actionRow}><button className={styles.button} onClick={() => void load()} type="button">重新加载</button><Link className={styles.quietButton} href="/evaluations">返回评测中心</Link></div>
        </div>
      </section>
    );
  }
  return (
    <>
      {error ? <p className={styles.inlineError} role="alert">{error} 当前状态仍保留在页面中。</p> : null}
      <EvaluationDetailContent detail={detail} onRerun={() => void rerun()} rerunning={rerunning} />
    </>
  );
}

export function EvaluationDetailContent({ detail, onRerun, rerunning }: {
  detail: EvaluationDetail;
  onRerun: () => void;
  rerunning: boolean;
}) {
  const failures = detail.cases.filter((item) => !item.passed);
  const complete = detail.summary.status === "passed" || detail.summary.status === "failed";
  return (
    <div className={styles.page} data-testid="evaluation-detail-page">
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Evaluation Snapshot · 评测快照</p>
          <h1>{detail.summary.label}</h1>
          <p className={styles.lead}>{evaluationStatusLabel(detail.summary.status)}。这是一份不可静默改写的历史结果。</p>
        </div>
        <div className={styles.actionRow}>
          <Link className={styles.quietButton} href="/evaluations">返回评测中心</Link>
          <button className={styles.button} disabled={rerunning || !complete} onClick={onRerun} type="button">{rerunning ? "正在创建…" : "重新运行固定评测"}</button>
        </div>
      </header>

      <p className={styles.honestyNote} role="note">{detail.provider_boundary}</p>
      <section aria-label="评测结果概览" className={styles.summaryGrid}>
        <article className={styles.summaryCard}>
          <span className={styles.status} data-state={detail.summary.status === "failed" ? "error" : detail.summary.status === "passed" ? "ok" : "warning"}>状态</span>
          <strong>{evaluationStatusLabel(detail.summary.status)}</strong>
          <p>{formatDateTime(detail.summary.created_at)}</p>
        </article>
        <article className={styles.summaryCard}>
          <span className={styles.status}>案例通过率</span>
          <strong>{formatPercentage(detail.summary.case_pass_rate)}</strong>
          <p>{formatNumber(detail.summary.case_count)} 个固定案例</p>
        </article>
        <article className={styles.summaryCard}>
          <span className={styles.status} data-state={detail.summary.external_provider_calls === 0 ? "ok" : "error"}>外部调用</span>
          <strong>{detail.summary.external_provider_calls ?? "未核验"}</strong>
          <p>必须为 0，才是本地确定性评测。</p>
        </article>
      </section>

      {detail.summary.status === "queued" || detail.summary.status === "running" ? (
        <section aria-live="polite" className={styles.loading} role="status">后台正在运行固定 60 场景评测，页面会自动更新…</section>
      ) : null}

      {complete ? (
        <>
          <section className={styles.panel} data-testid="evaluation-metrics">
            <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>01 / Metrics</p><h2>核心指标</h2><p>指标只来自固定数据集和本地 Recording Adapter（录制适配器）。</p></div></div>
            <div className={styles.metricGrid}>
              {Object.entries(detail.metrics).map(([key, value]) => (
                <article className={styles.metricItem} key={key}><span>{metricLabel(key)}</span><strong>{formatMetricValue(key, value)}</strong><span className={styles.meta}>{key}</span></article>
              ))}
            </div>
          </section>

          <div className={styles.twoColumns}>
            <section className={styles.panel} data-testid="evaluation-gates">
              <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>02 / Gates</p><h2>质量门禁</h2></div></div>
              <div className={styles.gateGrid}>{Object.entries(detail.hard_gates).map(([key, passed]) => (
                <article className={styles.gateItem} data-passed={passed} key={key}><strong>{passed ? "通过" : "失败"}</strong><span className={styles.meta}>{key}</span></article>
              ))}</div>
            </section>
            <section className={styles.panel} data-testid="evaluation-categories">
              <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>03 / Coverage</p><h2>场景覆盖</h2></div></div>
              <div className={styles.categoryGrid}>{Object.entries(detail.category_counts).map(([key, count]) => (
                <article className={styles.categoryItem} key={key}><strong>{formatNumber(count)} 个</strong><span className={styles.meta}>{key}</span></article>
              ))}</div>
            </section>
          </div>

          <section className={styles.panel} data-testid="evaluation-failures">
            <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>04 / Failure Triage</p><h2>{failureCategoryLabel(detail.triage.category)}</h2><p>{detail.triage.summary}</p></div><span className={styles.status} data-state={failures.length ? "error" : "ok"}>{failures.length} 个失败案例</span></div>
            {failures.length ? <CaseTable cases={failures} /> : <p>没有失败案例。</p>}
            {detail.triage.category !== "none" ? <p><strong>建议：</strong>{detail.triage.suggested_action}</p> : null}
          </section>

          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>05 / Provenance</p><h2>评测来源指纹</h2><p>这些指纹用来判断两份评测是否真的基于同一份代码和数据。</p></div></div>
            <div className={styles.twoColumns}>
              <div className={styles.monoBlock} translate="no">Policy<br />{detail.summary.policy_fingerprint}</div>
              <div className={styles.monoBlock} translate="no">Dataset<br />{detail.summary.dataset_sha256 ?? "not recorded"}</div>
              <div className={styles.monoBlock} translate="no">Evaluator<br />{detail.evaluator_sha256 ?? "not recorded"}</div>
              <div className={styles.monoBlock} translate="no">Schema<br />{detail.report_schema_version ?? "not recorded"}</div>
            </div>
            {detail.summary.policy_version_id ? <div className={styles.actionRow}><Link className={styles.quietButton} href={`/policies/${encodeURIComponent(detail.summary.policy_version_id)}`}>打开对应策略版本</Link></div> : null}
            <details className={styles.disclosure}>
              <summary>查看全部 {detail.cases.length} 个案例</summary>
              <CaseTable cases={detail.cases} />
            </details>
          </section>
        </>
      ) : null}
    </div>
  );
}


function CaseTable({ cases }: { cases: EvaluationDetail["cases"] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className={styles.visuallyHidden}>固定评测案例的预期状态、实际状态、召回率与耗时</caption>
        <thead><tr><th scope="col">案例</th><th scope="col">类别</th><th scope="col">结果</th><th scope="col">失败原因</th><th scope="col">预期 / 实际</th><th scope="col">来源召回</th><th scope="col">耗时</th></tr></thead>
        <tbody>{cases.map((item) => (
          <tr key={item.case_id}>
            <td className={styles.meta}>{item.case_id}</td><td>{item.category}</td><td>{item.passed ? "通过" : "失败"}</td><td className={styles.meta}>{item.failure_reason ?? "—"}</td>
            <td>{item.expected_status} / {item.actual_status}</td><td data-numeric="true">{formatPercentage(item.source_recall)}</td><td data-numeric="true">{formatDuration(item.latency_ms)}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
