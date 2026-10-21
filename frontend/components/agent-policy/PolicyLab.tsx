"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentPolicyClient } from "@/modules/agent-policy/client";
import type {
  PolicyDetail,
  PolicySummary,
  RetrievalPolicyConfig,
  RetrievalPolicyConfigField
} from "@/modules/agent-policy/contract";
import { RETRIEVAL_POLICY_FIELDS } from "@/modules/agent-policy/contract";
import { policyFieldLabel, policyStatusLabel } from "@/modules/agent-policy/presenter";
import styles from "./PolicyLab.module.css";


const CONFIG_FIELDS = RETRIEVAL_POLICY_FIELDS;

export function PolicyLab() {
  const client = useMemo(() => new AgentPolicyClient(), []);
  const router = useRouter();
  const [active, setActive] = useState<PolicyDetail | null>(null);
  const [items, setItems] = useState<PolicySummary[]>([]);
  const [draftLabel, setDraftLabel] = useState("V5.7 自适应检索候选");
  const [draftConfig, setDraftConfig] = useState<RetrievalPolicyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const [nextActive, catalog] = await Promise.all([
        client.getActivePolicy(signal),
        client.listPolicies({ limit: 100 })
      ]);
      setActive(nextActive);
      setItems(catalog.items);
      setDraftConfig((current) => current ?? nextActive.config);
    } catch (reason) {
      if (signal?.aborted) return;
      setActive(null);
      setItems([]);
      setError(reason instanceof Error ? reason.message : "无法加载策略实验室。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || !draftConfig || !draftLabel.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const receipt = await client.createPolicy({
        request_id: crypto.randomUUID(),
        label: draftLabel.trim(),
        base_policy_id: active.id,
        config: draftConfig
      });
      router.push(`/policies/${encodeURIComponent(receipt.policy_id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法创建策略草稿。");
      setSubmitting(false);
    }
  }

  if (!loading && (!active || !draftConfig)) {
    return <section className={styles.loading} role="alert"><div><h1>无法打开策略实验室</h1><p>{error || "活动策略不可用。"} 系统不会显示演示策略。</p><button className={styles.button} onClick={() => void load()} type="button">重新加载</button></div></section>;
  }
  if (loading || !active || !draftConfig) {
    return <div aria-live="polite" className={styles.loading} role="status">正在读取活动策略…</div>;
  }
  return (
    <>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      <PolicyLabContent
        active={active}
        draftConfig={draftConfig}
        draftLabel={draftLabel}
        items={items}
        onConfigChange={(field, value) => setDraftConfig((current) => current ? { ...current, [field]: value } : current)}
        onCreate={create}
        onLabelChange={setDraftLabel}
        submitting={submitting}
      />
    </>
  );
}

export function PolicyLabContent({
  active,
  draftConfig,
  draftLabel,
  items,
  onConfigChange,
  onCreate,
  onLabelChange,
  submitting
}: {
  active: PolicyDetail;
  draftConfig: RetrievalPolicyConfig;
  draftLabel: string;
  items: PolicySummary[];
  onConfigChange: (field: RetrievalPolicyConfigField, value: number) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onLabelChange: (value: string) => void;
  submitting: boolean;
}) {
  return (
    <div className={styles.page} data-testid="policy-lab-page">
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Policy Lab · 策略实验室</p>
          <h1>先评测，再让新策略影响任务</h1>
          <p className={styles.lead}>每个 Run 固定一份不可变策略。候选版本必须完成固定评测，才能启用；历史版本可以安全回滚。</p>
        </div>
        <div className={styles.actions}>
          <Link className={styles.quietButton} href="/policies/optimizer">打开优化工作台</Link>
          <Link className={styles.quietButton} href="/evaluations">打开评测中心</Link>
          <Link className={styles.quietButton} href="/system/observability">运行时观测</Link>
        </div>
      </header>

      <section aria-label="当前活动策略" className={styles.summaryGrid}>
        <article className={styles.card}>
          <span className={styles.status}>当前活动策略</span>
          <h2>{active.label}</h2>
          <p>版本 {active.version} · 新任务会固定这一版本。</p>
        </article>
        <article className={styles.card}>
          <span className={styles.status}>策略指纹</span>
          <p className={styles.mono} translate="no">{active.config_sha256}</p>
          <p>内容变化会生成新的 SHA-256 指纹。</p>
        </article>
        <article className={styles.card}>
          <span className={styles.status}>历史版本</span>
          <h2>{items.length} 个</h2>
          <p>草稿、活动和退役版本都保留，不静默覆盖。</p>
        </article>
      </section>

      <form className={styles.form} onSubmit={onCreate}>
        <div className={styles.panelHeader}>
          <div><p className={styles.sectionIndex}>01 / Draft</p><h2>创建不可变草稿</h2><p>这里只能修改固定数值参数，不能写 Prompt、代码、命令或路径。</p></div>
        </div>
        <div className={styles.field}>
          <label htmlFor="policy-label">候选策略名称</label>
          <input className={styles.input} id="policy-label" maxLength={120} onChange={(event) => onLabelChange(event.target.value)} value={draftLabel} />
        </div>
        <div className={styles.configGrid}>
          {CONFIG_FIELDS.map((field) => (
            <div className={styles.field} key={field.name}>
              <label htmlFor={`policy-${field.name}`}>{policyFieldLabel(field.name)}</label>
              <input
                className={styles.input}
                id={`policy-${field.name}`}
                max={field.max}
                min={field.min}
                onChange={(event) => onConfigChange(field.name, Number(event.target.value))}
                step="1"
                type="number"
                value={draftConfig[field.name]}
              />
            </div>
          ))}
        </div>
        <div className={styles.actions}>
          <button className={styles.button} disabled={submitting || !draftLabel.trim()} type="submit">{submitting ? "正在创建…" : "创建策略草稿"}</button>
          <span className={styles.mono}>Base Policy v{active.version}</span>
        </div>
      </form>

      <section>
        <div className={styles.panelHeader}><div><p className={styles.sectionIndex}>02 / History</p><h2>策略版本历史</h2><p>打开一个版本，查看差异、模拟、评测、启用或回滚。</p></div></div>
        <div className={styles.catalogGrid}>
          {items.map((item) => (
            <article className={styles.card} key={item.id}>
              <span className={styles.status} data-state={item.status === "retired" ? "retired" : item.status === "draft" ? "warning" : undefined}>{policyStatusLabel(item.status)}</span>
              <div><h2>{item.label}</h2><p>版本 {item.version}</p></div>
              <p className={styles.mono} translate="no">{item.config_sha256}</p>
              <Link className={styles.quietButton} href={`/policies/${encodeURIComponent(item.id)}`}>打开策略版本</Link>
            </article>
          ))}
        </div>
      </section>
      <p className={styles.honesty} role="note">当前策略评测仍是本地确定性架构评测，不代表真实大模型回答质量。</p>
    </div>
  );
}

export { CONFIG_FIELDS };
