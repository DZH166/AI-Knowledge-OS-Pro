import type { RunView } from "@/modules/evidence-agent";
import type { LedgerItem } from "./run-presenter";
import styles from "./EvidenceAgent.module.css";

const PHASE_LABELS: Record<RunView["phase"], string> = {
  route: "确定路径", plan: "制定计划", retrieve: "检索资料", assess: "核验证据",
  synthesize: "整理结论", verify: "核验结论", persist_artifact: "保存成果"
};
const PHASE_GROUP: Record<RunView["phase"], number> = {
  route: 0, plan: 0, retrieve: 1, assess: 2, synthesize: 3, verify: 3, persist_artifact: 4
};
const STEPS = ["研究计划", "检索资料", "核验证据", "整理结论", "保存成果"];
const WAITING_LABELS: Partial<Record<RunView["status"], string>> = {
  queued: "排队等待执行", awaiting_input: "等待补充信息", awaiting_approval: "等待你的批准", paused: "研究已暂停"
};
const RELATIONS = [
  { key: "supports", label: "支持结论" }, { key: "contradicts", label: "存在冲突" },
  { key: "contextual", label: "背景资料" }, { key: "candidate", label: "待核验" },
  { key: "excluded", label: "已排除" }
] as const;

type OverviewView = Pick<RunView, "phase" | "status" | "budget_limits" | "budget_usage">;

export function ResearchOverview({ view, ledger }: { view: OverviewView; ledger: readonly Pick<LedgerItem, "relation">[] }) {
  const counts = new Map<string, number>();
  for (const evidence of ledger) counts.set(evidence.relation, (counts.get(evidence.relation) ?? 0) + 1);
  const stopped = ["completed", "insufficient_evidence", "failed", "cancelled"].includes(view.status);
  const waiting = WAITING_LABELS[view.status];
  const executing = !stopped && !waiting;
  const steps = view.budget_usage.steps;
  const limit = view.budget_limits.max_steps;
  const knownBudget = Number.isFinite(steps) && Number.isFinite(limit) && limit > 0;
  return <section aria-label="研究状态概览" className={styles.researchOverview}>
    <div className={styles.phaseOverview}>
      <div className={styles.panelHeading}><h2>{stopped ? "最后上报阶段" : waiting ? "研究阶段记录" : "当前执行阶段"}</h2><span className={styles.count}>{waiting ?? PHASE_LABELS[view.phase]}</span></div>
      <ol aria-label="研究阶段，非完成百分比" className={styles.phaseSteps}>
        {STEPS.map((label, index) => <li aria-current={executing && index === PHASE_GROUP[view.phase] ? "step" : undefined} data-current={executing && index === PHASE_GROUP[view.phase]} key={label}><span aria-hidden="true">{index + 1}</span>{label}</li>)}
      </ol>
      <p className={styles.overviewNote}>研究可能返回检索补充证据；阶段位置不代表完成比例。</p>
      {waiting && <p className={styles.overviewNote}>最近上报阶段：{PHASE_LABELS[view.phase]}。等待状态不表示该阶段仍在执行。</p>}
    </div>
    <div className={styles.evidenceOverview}>
      <div className={styles.panelHeading}><h2>证据分布</h2><span className={styles.count}>{ledger.length} 条记录</span></div>
      <div aria-hidden="true" className={styles.evidenceDistribution}>
        {RELATIONS.map(({ key }) => (counts.get(key) ?? 0) > 0 ? <span data-relation={key} key={key} style={{ flexGrow: counts.get(key) }} /> : null)}
      </div>
      <dl className={styles.distributionLegend}>{RELATIONS.map(({ key, label }) => <div data-relation={key} key={key}><dt>{label}</dt><dd>{counts.get(key) ?? 0}</dd></div>)}</dl>
      <p className={styles.overviewNote}>支持与冲突证据才被采用；背景、待核验与排除项不计入结论。</p>
      {knownBudget ? <label className={styles.budgetMeter}>步骤预算 <meter max={limit} min={0} value={Math.min(steps, limit)} /> <span>{steps} / {limit} 步</span></label> : <p className={styles.overviewNote}>步骤预算尚未上报。</p>}
    </div>
  </section>;
}
