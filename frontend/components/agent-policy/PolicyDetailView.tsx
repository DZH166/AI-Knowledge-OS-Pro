"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentControlClient } from "@/modules/agent-control/client";
import type { EvaluationSummary } from "@/modules/agent-control/contract";
import { AgentPolicyClient } from "@/modules/agent-policy/client";
import type { PolicyComparison, PolicyDetail, PolicySimulation } from "@/modules/agent-policy/contract";
import { policyFieldLabel, policyStatusLabel, policyValue } from "@/modules/agent-policy/presenter";
import { EvidenceCatalogClient } from "@/modules/evidence-agent/catalog-client";
import type { RunView } from "@/modules/evidence-agent/contract";
import styles from "./PolicyLab.module.css";


type RunOption = Pick<RunView, "id" | "goal" | "status">;

export function PolicyDetailView() {
  const params = useParams<{ policyId: string }>();
  const policyId = decodeURIComponent(params.policyId);
  const policyClient = useMemo(() => new AgentPolicyClient(), []);
  const controlClient = useMemo(() => new AgentControlClient(), []);
  const catalogClient = useMemo(() => new EvidenceCatalogClient(), []);
  const [detail, setDetail] = useState<PolicyDetail | null>(null);
  const [active, setActive] = useState<PolicyDetail | null>(null);
  const [comparison, setComparison] = useState<PolicyComparison | null>(null);
  const [simulation, setSimulation] = useState<PolicySimulation | null>(null);
  const [runs, setRuns] = useState<RunOption[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const [nextDetail, nextActive, runCatalog, evaluationCatalog] = await Promise.all([
        policyClient.getPolicy(policyId, signal),
        policyClient.getActivePolicy(signal),
        catalogClient.listRuns({ limit: 100 }),
        controlClient.listEvaluations({ limit: 100 })
      ]);
      const terminalRuns = runCatalog.items.filter((item) => ["completed", "insufficient_evidence", "failed", "cancelled"].includes(item.status));
      setDetail(nextDetail);
      setActive(nextActive);
      setRuns(terminalRuns);
      setSelectedRunId((current) => current || terminalRuns[0]?.id || "");
      setEvaluations(evaluationCatalog.items);
      setComparison(nextDetail.id === nextActive.id ? null : await policyClient.comparePolicies(nextActive.id, nextDetail.id, signal));
    } catch (reason) {
      if (signal?.aborted) return;
      setDetail(null);
      setActive(null);
      setError(reason instanceof Error ? reason.message : "无法加载策略详情。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [catalogClient, controlClient, policyClient, policyId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function runAction(name: string, action: () => Promise<void>) {
    setBusyAction(name);
    setError("");
    try { await action(); } catch (reason) {
      setError(reason instanceof Error ? reason.message : "策略操作失败。");
    } finally { setBusyAction(""); }
  }

  if (!loading && (!detail || !active)) {
    return <section className={styles.loading} role="alert"><div><h1>无法打开策略版本</h1><p>{error || "策略不存在。"} 系统不会回退到默认或演示策略。</p><div className={styles.actions}><button className={styles.button} onClick={() => void load()} type="button">重新加载</button><Link className={styles.quietButton} href="/policies">返回策略实验室</Link></div></div></section>;
  }
  if (loading || !detail || !active) return <div aria-live="polite" className={styles.loading} role="status">正在读取策略版本…</div>;
  const matchingEvaluation = evaluations.find((item) =>
    item.status === "passed" && item.policy_version_id === detail.id && item.policy_fingerprint === detail.config_sha256
  );
  return (
    <>
      {error ? <p className={styles.error} role="alert">{error} 页面不会改用演示策略。</p> : null}
      <PolicyDetailContent
        active={active}
        busyAction={busyAction}
        comparison={comparison}
        detail={detail}
        evaluations={evaluations}
        onActivate={() => void runAction("activate", async () => {
          if (!matchingEvaluation) throw new Error("必须先完成与该策略指纹一致的固定评测。");
          await policyClient.activatePolicy(detail.id, { request_id: crypto.randomUUID(), expected_active_policy_id: active.id, evaluation_id: matchingEvaluation.id });
          await load();
        })}
        onEvaluate={() => void runAction("evaluate", async () => {
          const receipt = await controlClient.startEvaluation({ request_id: crypto.randomUUID(), label: `${detail.label} · 固定评测`, policy_id: detail.id });
          await controlClient.waitForEvaluation(receipt.evaluation_id);
          await load();
        })}
        onRollback={() => void runAction("rollback", async () => {
          await policyClient.rollbackPolicy(detail.id, { request_id: crypto.randomUUID(), expected_active_policy_id: active.id });
          await load();
        })}
        onRunChange={setSelectedRunId}
        onSimulate={() => void runAction("simulate", async () => {
          if (!selectedRunId) throw new Error("请选择一个已经结束的 Run。");
          setSimulation(await policyClient.simulatePolicy(selectedRunId, detail.id));
        })}
        runs={runs}
        selectedRunId={selectedRunId}
        simulation={simulation}
      />
    </>
  );
}

export function PolicyDetailContent({
  active,
  busyAction,
  comparison,
  detail,
  evaluations,
  onActivate,
  onEvaluate,
  onRollback,
  onRunChange,
  onSimulate,
  runs,
  selectedRunId,
  simulation
}: {
  active: PolicyDetail;
  busyAction: string;
  comparison: PolicyComparison | null;
  detail: PolicyDetail;
  evaluations: EvaluationSummary[];
  onActivate: () => void;
  onEvaluate: () => void;
  onRollback: () => void;
  onRunChange: (runId: string) => void;
  onSimulate: () => void;
  runs: RunOption[];
  selectedRunId: string;
  simulation: PolicySimulation | null;
}) {
  const matchingEvaluations = evaluations.filter((item) =>
    item.policy_version_id === detail.id && item.policy_fingerprint === detail.config_sha256
  );
  const passedEvaluation = matchingEvaluations.find((item) => item.status === "passed");
  const fields = Object.entries(detail.config).filter(([field]) => field !== "schema_version");
  return (
    <div className={styles.page} data-testid="policy-detail-page">
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Policy Version · 策略版本</p>
          <h1>{detail.label}</h1>
          <p className={styles.lead}>版本 {detail.version} · {policyStatusLabel(detail.status)}。配置内容不可原地修改。</p>
        </div>
        <div className={styles.actions}>
          <Link className={styles.quietButton} href="/policies">返回策略实验室</Link>
          <Link className={styles.quietButton} href="/evaluations">评测中心</Link>
        </div>
      </header>

      <section className={styles.summaryGrid} aria-label="策略身份">
        <article className={styles.card}><span className={styles.status} data-state={detail.status === "retired" ? "retired" : detail.status === "draft" ? "warning" : undefined}>{policyStatusLabel(detail.status)}</span><h2>v{detail.version}</h2><p>当前活动版本是 v{active.version}。</p></article>
        <article className={styles.card}><span className={styles.status}>策略指纹</span><p className={styles.mono} translate="no">{detail.config_sha256}</p></article>
        <article className={styles.card}><span className={styles.status}>匹配评测</span><h2>{matchingEvaluations.length} 份</h2><p>{passedEvaluation ? "已有通过评测，可以启用。" : "尚无通过评测。"}</p></article>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>01 / Configuration</p><h2>固定检索参数</h2><p>Top-K 是候选数量；分数与来源上限负责过滤；相邻片段控制上下文宽度。</p></div></div>
        <div className={styles.configGrid}>{fields.map(([field, value]) => (
          <article className={styles.configItem} key={field}><span>{policyFieldLabel(field)}</span><strong>{policyValue(field, Number(value))}</strong><span className={styles.mono}>{field}</span></article>
        ))}</div>
      </section>

      {comparison ? <section className={styles.panel} data-testid="policy-comparison">
        <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>02 / Difference</p><h2>策略字段差异</h2><p>左侧是当前活动策略，右侧是这个版本。</p></div></div>
        {comparison.changes.length ? <div className={styles.deltaGrid}>{comparison.changes.map((change) => (
          <article className={styles.deltaItem} key={change.field}><span>{policyFieldLabel(change.field)}</span><strong>{policyValue(change.field, change.left)} → {policyValue(change.field, change.right)}</strong><span className={styles.mono}>{change.field}</span></article>
        ))}</div> : <p>两个版本配置一致。</p>}
      </section> : null}

      <section className={styles.panel} data-testid="policy-simulation">
        <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>03 / Counterfactual</p><h2>反事实模拟</h2><p>只比较历史决策参数，不重新调用模型、检索或工具，也不会预测新的回答。</p></div></div>
        <div className={styles.actions}>
          <div className={styles.field}>
            <label htmlFor="policy-simulation-run">选择已结束的 Run</label>
            <select className={styles.select} id="policy-simulation-run" onChange={(event) => onRunChange(event.target.value)} value={selectedRunId}>
              <option value="">请选择…</option>
              {runs.map((run) => <option key={run.id} value={run.id}>{run.goal} · {run.status}</option>)}
            </select>
          </div>
          <button className={styles.quietButton} disabled={!selectedRunId || Boolean(busyAction)} onClick={onSimulate} type="button">{busyAction === "simulate" ? "正在模拟…" : "模拟这个策略"}</button>
        </div>
        {simulation ? <div className={styles.deltaGrid} role="status">
          <article className={styles.deltaItem}><span>改变的决策</span><strong>{simulation.changed_decision_count}</strong></article>
          <article className={styles.deltaItem}><span>候选窗口变化</span><strong>{simulation.projected_candidate_window_delta > 0 ? "+" : ""}{simulation.projected_candidate_window_delta}</strong></article>
          <article className={styles.deltaItem}><span>相邻上下文变化</span><strong>{simulation.projected_neighbor_context_delta > 0 ? "+" : ""}{simulation.projected_neighbor_context_delta}</strong></article>
          <p className={styles.honesty}>{simulation.boundary}</p>
        </div> : null}
      </section>

      <section className={styles.panel} data-testid="policy-release-controls">
        <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>04 / Release Control</p><h2>评测、启用与回滚</h2><p>启用必须绑定同一策略指纹的 60 场景通过评测；回滚只允许曾经活动过的退役版本。</p></div></div>
        <ul className={styles.list}>{matchingEvaluations.map((evaluation) => (
          <li key={evaluation.id}><strong>{evaluation.label}</strong><span className={styles.mono} translate="no">{evaluation.id} · {evaluation.status}</span></li>
        ))}</ul>
        <div className={styles.actions}>
          <button className={styles.quietButton} disabled={Boolean(busyAction)} onClick={onEvaluate} type="button">{busyAction === "evaluate" ? "正在运行 60 场景…" : "运行固定 60 场景评测"}</button>
          {detail.status === "draft" ? <button className={styles.button} disabled={!passedEvaluation || Boolean(busyAction)} onClick={onActivate} type="button">{busyAction === "activate" ? "正在启用…" : "启用已通过评测的策略"}</button> : null}
          {detail.status === "retired" && detail.has_been_active ? <button className={styles.button} disabled={Boolean(busyAction)} onClick={onRollback} type="button">{busyAction === "rollback" ? "正在回滚…" : "回滚到这个历史策略"}</button> : null}
        </div>
      </section>
      <p className={styles.honesty} role="note">策略评测证明的是固定架构和回归行为，不代表真实模型回答质量。</p>
    </div>
  );
}
