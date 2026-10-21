"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentPolicyClient } from "@/modules/agent-policy/client";
import { formatDateTime } from "@/modules/agent-control/format";
import { OptimizerClient } from "@/modules/optimizer/client";
import type { StudySummary, StudyTemplate } from "@/modules/optimizer/contract";
import { objectiveLabel, statusLabel, templateDescription, templateLabel } from "@/modules/optimizer/presenter";
import styles from "./OptimizerWorkbench.module.css";


type ActivePolicyContext = { id: string; label: string; version: number; configSha256: string };
type LimitField = "maxCandidates" | "maxEvaluations";

export function OptimizerLab() {
  const optimizer = useMemo(() => new OptimizerClient(), []);
  const policies = useMemo(() => new AgentPolicyClient(), []);
  const router = useRouter();
  const [activePolicy, setActivePolicy] = useState<ActivePolicyContext | null>(null);
  const [templates, setTemplates] = useState<StudyTemplate[]>([]);
  const [studies, setStudies] = useState<StudySummary[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState("balanced");
  const [label, setLabel] = useState("V5.7 检索优化实验");
  const [maxCandidates, setMaxCandidates] = useState(4);
  const [maxEvaluations, setMaxEvaluations] = useState(8);
  const [seed, setSeed] = useState(42);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const [active, nextTemplates, nextStudies] = await Promise.all([
        policies.getActivePolicy(signal),
        optimizer.listTemplates(signal),
        optimizer.listStudies(signal)
      ]);
      setActivePolicy({ id: active.id, label: active.label, version: active.version, configSha256: active.config_sha256 });
      setTemplates(nextTemplates);
      setStudies(nextStudies);
      const selected = nextTemplates.find((item) => item.key === "balanced") ?? nextTemplates[0];
      if (selected) {
        setSelectedTemplate(selected.key);
        setMaxCandidates(selected.max_candidates);
        setMaxEvaluations(selected.max_evaluations);
        setSeed(selected.seed);
      }
    } catch (reason) {
      if (signal?.aborted) return;
      setActivePolicy(null);
      setTemplates([]);
      setStudies([]);
      setError(reason instanceof Error ? reason.message : "无法加载检索优化工作台。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [optimizer, policies]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  function changeTemplate(key: string) {
    const template = templates.find((item) => item.key === key);
    setSelectedTemplate(key);
    if (template) {
      setMaxCandidates(template.max_candidates);
      setMaxEvaluations(template.max_evaluations);
      setSeed(template.seed);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activePolicy || !label.trim()) return;
    setBusy(true);
    setError("");
    try {
      const receipt = await optimizer.createFromTemplate({
        schema_version: 1,
        request_id: crypto.randomUUID(),
        label: label.trim(),
        base_policy_id: activePolicy.id,
        template_key: selectedTemplate as "quality_first" | "balanced" | "cost_first",
        overrides: { seed, max_candidates: maxCandidates, max_evaluations: maxEvaluations }
      });
      router.push(`/policies/optimizer/${encodeURIComponent(receipt.study_id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法创建优化实验。");
      setBusy(false);
    }
  }

  if (loading) return <div aria-live="polite" className={styles.loading} role="status">正在读取优化器事实…</div>;
  if (!activePolicy || templates.length === 0) {
    return <section className={styles.loading} role="alert"><div><h1>无法打开优化工作台</h1><p>{error || "活动策略或实验模板不可用。"} 系统不会展示模拟实验。</p><button className={styles.button} onClick={() => void load()} type="button">重新加载</button></div></section>;
  }

  return (
    <>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      <OptimizerLabContent
        activePolicy={activePolicy}
        busy={busy}
        label={label}
        maxCandidates={maxCandidates}
        maxEvaluations={maxEvaluations}
        onCreate={create}
        onLabelChange={setLabel}
        onLimitChange={(field, value) => field === "maxCandidates" ? setMaxCandidates(value) : setMaxEvaluations(value)}
        onSeedChange={setSeed}
        onTemplateChange={changeTemplate}
        seed={seed}
        selectedTemplate={selectedTemplate}
        studies={studies}
        templates={templates}
      />
    </>
  );
}

export function OptimizerLabContent({
  activePolicy, templates, studies, selectedTemplate, label, maxCandidates, maxEvaluations, seed, busy,
  onCreate, onLabelChange, onLimitChange, onSeedChange, onTemplateChange
}: {
  activePolicy: ActivePolicyContext;
  templates: StudyTemplate[];
  studies: StudySummary[];
  selectedTemplate: string;
  label: string;
  maxCandidates: number;
  maxEvaluations: number;
  seed: number;
  busy: boolean;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onLabelChange: (value: string) => void;
  onLimitChange: (field: LimitField, value: number) => void;
  onSeedChange: (value: number) => void;
  onTemplateChange: (value: string) => void;
}) {
  const template = templates.find((item) => item.key === selectedTemplate) ?? templates[0];
  return (
    <div className={styles.page} data-testid="optimizer-lab-page">
      <header className={styles.hero}>
        <div><p className={styles.eyebrow}>Offline Retrieval Optimizer · 离线检索优化器</p><h1>让检索策略先经过实验，再进入人工评审</h1><p className={styles.lead}>系统在固定 60 场景评测中比较候选策略，只推荐经过验证的结果。它不会自动启用策略，也不代表真实大模型质量。</p></div>
        <div className={styles.actions}><Link className={styles.quietButton} href="/policies">返回策略实验室</Link><Link className={styles.quietButton} href="/evaluations">查看评测记录</Link></div>
      </header>

      <section aria-label="优化器当前上下文" className={styles.summaryGrid}>
        <article className={styles.card}><span className={styles.status}>活动策略</span><h2>{activePolicy.label}</h2><p>版本 {activePolicy.version}，所有候选都以它作为对照。</p></article>
        <article className={styles.card}><span className={styles.status}>策略指纹</span><p className={styles.mono} translate="no">{activePolicy.configSha256}</p><p>每次评测必须返回完全相同的 SHA-256。</p></article>
        <article className={styles.card}><span className={styles.status}>实验历史</span><h2>{studies.length} 个 Study</h2><p>Study 是一次可恢复、可审计的优化实验。</p></article>
      </section>

      <form className={styles.form} onSubmit={onCreate}>
        <div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>01 / Create</p><h2>创建优化实验</h2><p>模板固定搜索范围和权重；这里只允许收窄候选数、评测数和随机种子。</p></div></div>
        <div className={styles.fields}>
          <div className={styles.field} data-wide="true"><label htmlFor="optimizer-label">实验名称</label><input autoComplete="off" className={styles.input} id="optimizer-label" maxLength={120} name="optimizer-label" onChange={(event) => onLabelChange(event.target.value)} placeholder="例如：多跳证据召回优化…" value={label} /></div>
          <div className={styles.field} data-wide="true"><label htmlFor="optimizer-template">实验模板</label><select className={styles.select} id="optimizer-template" name="optimizer-template" onChange={(event) => onTemplateChange(event.target.value)} value={selectedTemplate}>{templates.map((item) => <option key={item.key} value={item.key}>{templateLabel(item.key)}</option>)}</select></div>
          <div className={styles.field}><label htmlFor="optimizer-candidates">候选总预算</label><input autoComplete="off" className={styles.input} id="optimizer-candidates" inputMode="numeric" max={4} min={1} name="optimizer-candidates" onChange={(event) => onLimitChange("maxCandidates", Number(event.target.value))} type="number" value={maxCandidates} /></div>
          <div className={styles.field}><label htmlFor="optimizer-evaluations">评测总预算</label><input autoComplete="off" className={styles.input} id="optimizer-evaluations" inputMode="numeric" max={8} min={1} name="optimizer-evaluations" onChange={(event) => onLimitChange("maxEvaluations", Number(event.target.value))} type="number" value={maxEvaluations} /></div>
          <div className={styles.field}><label htmlFor="optimizer-seed">确定性 Seed</label><input autoComplete="off" className={styles.input} id="optimizer-seed" inputMode="numeric" max={2147483647} min={0} name="optimizer-seed" onChange={(event) => onSeedChange(Number(event.target.value))} type="number" value={seed} /></div>
        </div>
        <div className={`${styles.card} ${styles.spacedCard}`}><strong>{templateLabel(template.key)}</strong><p>{templateDescription(template.key)}</p><ul className={styles.templateFacts}><li><span>目标</span><strong>{objectiveLabel(template.objective)}</strong></li><li><span>质量 / 成本权重</span><strong>{template.weights.quality_weight_permille} / {template.weights.cost_weight_permille}</strong></li></ul></div>
        <div className={`${styles.toolbar} ${styles.spacedToolbar}`}><button className={styles.button} disabled={busy || !label.trim()} type="submit">{busy ? "正在创建…" : "创建优化实验"}</button><span className={styles.mono}>Base Policy v{activePolicy.version}</span></div>
      </form>

      <section><div className={styles.sectionHeader}><div><p className={styles.sectionIndex}>02 / History</p><h2>实验历史</h2><p>打开 Study 查看轮次、Trial、Pareto 前沿、推荐理由和事件证据。</p></div></div>{studies.length ? <div className={styles.catalog}>{studies.map((item) => <article className={styles.card} key={item.id}><span className={styles.status} data-state={item.status === "failed" ? "error" : item.status === "running" ? "warning" : undefined}>{statusLabel(item.status)}</span><h2>{item.label}</h2><p>{objectiveLabel(item.objective)} · 已创建 {item.budget_usage.created_trials} 个候选</p><span className={styles.mono}>{formatDateTime(item.created_at)}</span><Link className={styles.quietButton} href={`/policies/optimizer/${encodeURIComponent(item.id)}`}>打开实验</Link></article>)}</div> : <div className={styles.card}><h2>还没有优化实验</h2><p>选择一个模板创建第一轮候选。</p></div>}</section>
      <p className={styles.honesty} role="note">当前优化器使用本地确定性固定评测。Provider（模型服务提供方）调用数必须为 0，推荐结果不能自动激活。</p>
    </div>
  );
}
