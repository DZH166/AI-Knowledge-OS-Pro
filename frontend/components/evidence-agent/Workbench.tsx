"use client";

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  DatabaseZap,
  FileCheck2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UploadCloud
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/services/api";
import type { KnowledgeSpace, SourceItem } from "@/types/api";
import styles from "./EvidenceAgent.module.css";
import { startEvidenceRun } from "./runtime";
import {
  RECORDING_SOURCES,
  RECORDING_SPACES,
  activeSourceRevision,
  sourceIndexSummary,
  sourceTitle,
  sourceTypeLabel
} from "./source-presenter";

const BUDGETS = {
  quick: { max_steps: 4, max_tool_calls: 6, max_model_calls: 3, max_active_ms: 60_000 },
  standard: { max_steps: 8, max_tool_calls: 12, max_model_calls: 6, max_active_ms: 180_000 },
  deep: { max_steps: 16, max_tool_calls: 24, max_model_calls: 10, max_active_ms: 600_000 }
} as const;

export function Workbench() {
  const router = useRouter();
  const scopeRequest = useRef(0);
  const [recording, setRecording] = useState(false);
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [spaceId, setSpaceId] = useState(0);
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [scopeLoading, setScopeLoading] = useState(true);
  const [scopeError, setScopeError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadScope = useCallback(async (useRecording: boolean, preferredSpaceId = 0) => {
    const request = ++scopeRequest.current;
    setScopeLoading(true);
    setScopeError("");
    try {
      const [spaceData, sourceData] = useRecording
        ? [RECORDING_SPACES, RECORDING_SOURCES]
        : await Promise.all([api.listSpaces(), api.listSources()]);
      if (request !== scopeRequest.current) return;
      const nextSpaceId = spaceData.some((space) => space.id === preferredSpaceId)
        ? preferredSpaceId
        : spaceData[0]?.id ?? 0;
      setSpaces(spaceData);
      setSources(sourceData);
      setSpaceId(nextSpaceId);
      setSelectedSourceIds((current) => current.filter((id) => sourceData.some(
        (source) => source.id === id && source.space_id === nextSpaceId && source.active_revision_id !== null
      )));
    } catch (reason) {
      if (request !== scopeRequest.current) return;
      setSpaces([]);
      setSources([]);
      setSpaceId(0);
      setSelectedSourceIds([]);
      setScopeError(reason instanceof Error ? reason.message : "无法加载知识空间与来源目录。");
    } finally {
      if (request === scopeRequest.current) setScopeLoading(false);
    }
  }, []);

  useEffect(() => {
    const useRecording = new URLSearchParams(window.location.search).get("demo") === "1";
    setRecording(useRecording);
    void loadScope(useRecording);
    return () => {
      scopeRequest.current += 1;
    };
  }, [loadScope]);

  const spaceSources = sources.filter((source) => source.space_id === spaceId);
  const activeSources = spaceSources.filter((source) => source.active_revision_id !== null);

  async function submit(formData: FormData) {
    if (!spaceId) {
      setError("请先选择一个可用的知识空间。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const budgetProfile = String(formData.get("budget_profile") ?? "standard") as keyof typeof BUDGETS;
      const result = await startEvidenceRun(
        {
          schema_version: 1,
          request_id: crypto.randomUUID(),
          space_id: spaceId,
          goal: String(formData.get("goal") ?? ""),
          scope: { source_ids: selectedSourceIds },
          deliverable: { kind: String(formData.get("deliverable")) as "answer" | "research_report" | "comparison" },
          mode: String(formData.get("mode")) as "auto" | "force_quick" | "force_agent",
          budget: BUDGETS[budgetProfile],
          permissions: { read_only: true, allow_scope_expansion: false },
          provider_mode: recording ? "recording" : "real"
        },
        recording
      );
      router.push(`/runs/${encodeURIComponent(result.receipt.run_id)}${recording ? "?demo=1" : ""}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? `${reason.message} 请确认后端服务可用，或启用明确标记的 Recording Demo。`
          : "无法开始研究。请检查配置后重试。"
      );
      setSubmitting(false);
    }
  }

  function changeRecording(nextRecording: boolean) {
    setRecording(nextRecording);
    setSelectedSourceIds([]);
    router.replace(nextRecording ? "/workbench?demo=1" : "/workbench", { scroll: false });
    void loadScope(nextRecording);
  }

  function toggleSource(sourceId: number) {
    setSelectedSourceIds((current) => current.includes(sourceId)
      ? current.filter((id) => id !== sourceId)
      : [...current, sourceId]);
  }

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>Research Workbench</p>
          <h1>开始一次可核验研究</h1>
          <p className={styles.lead}>
            给出目标、选择真实证据范围与预算。溯知会规划研究、记录证据来源，在需要写入或外发前停下来请求你的批准。
          </p>
        </div>
        <Link className={styles.secondaryAction} href={`/runs${recording ? "?demo=1" : ""}`}>
          查看运行记录 <ArrowRight aria-hidden="true" size={16} />
        </Link>
      </header>

      {recording && (
        <div aria-live="polite" className={styles.demoBanner} role="status">
          <Sparkles aria-hidden="true" size={18} />
          <div>
            <strong>Recording Demo · 非真实执行</strong>
            <span>Synthetic scope：下方空间与来源均为确定性演示选项；不会调用模型、检索服务或写入真实资料。</span>
          </div>
        </div>
      )}

      <div className={styles.workbenchGrid}>
        <form action={submit} className={styles.formCard}>
          <div className={styles.sectionHeading}>
            <div>
              <p className={styles.stepLabel}>01 · Objective</p>
              <h2>研究目标与交付物</h2>
            </div>
            <span className={styles.requiredNote}>* 必填</span>
          </div>

          <div className={styles.field}>
            <label htmlFor="research-goal">研究目标 *</label>
            <textarea
              aria-describedby="goal-help"
              autoComplete="off"
              className={styles.textarea}
              defaultValue="比较现有 RAG 与 Evidence Agent 的可追溯性，并给出有证据约束的升级建议。"
              id="research-goal"
              maxLength={12_000}
              name="goal"
              placeholder="例如：比较 3 份方案，指出冲突证据，并产出决策简报…"
              required
            />
            <small id="goal-help">描述需要验证的事实与最终决策；系统不会展示或保存模型的隐藏思维过程。</small>
          </div>

          <section aria-labelledby="scope-heading" className={styles.scopePicker}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.stepLabel}>02 · Evidence Scope</p>
                <h2 id="scope-heading">选择证据范围</h2>
              </div>
              <button
                aria-label="刷新知识空间与来源"
                className={styles.quietAction}
                disabled={scopeLoading}
                onClick={() => void loadScope(recording, spaceId)}
                type="button"
              >
                <RefreshCw aria-hidden="true" size={14} /> 刷新
              </button>
            </div>

            {scopeLoading ? (
              <div aria-live="polite" className={styles.scopeEmpty} role="status">正在加载空间与 active revisions…</div>
            ) : scopeError ? (
              <div className={styles.scopeEmpty} role="alert">
                <AlertTriangle aria-hidden="true" size={22} />
                <strong>证据目录加载失败</strong>
                <span>{scopeError}</span>
                <button className={styles.quietAction} onClick={() => void loadScope(recording, spaceId)} type="button">重试</button>
              </div>
            ) : spaces.length === 0 ? (
              <div className={styles.scopeEmpty}>
                <DatabaseZap aria-hidden="true" size={24} />
                <strong>还没有知识空间</strong>
                <span>创建空间并摄取来源后，才可以启动有边界的研究。</span>
                <Link className={styles.quietAction} href="/knowledge">创建知识空间</Link>
              </div>
            ) : (
              <>
                <div className={styles.field}>
                  <label htmlFor="space-id">知识空间 *</label>
                  <select
                    className={styles.select}
                    id="space-id"
                    name="space_id"
                    onChange={(event) => {
                      setSpaceId(Number(event.target.value));
                      setSelectedSourceIds([]);
                    }}
                    required
                    value={spaceId}
                  >
                    {spaces.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                  </select>
                </div>

                {spaceSources.length === 0 ? (
                  <div className={styles.scopeEmpty}>
                    <UploadCloud aria-hidden="true" size={24} />
                    <strong>这个空间还没有来源</strong>
                    <span>摄取文档、媒体或代码仓库，建立 active revision 后再开始研究。</span>
                    <Link className={styles.quietAction} href={`/upload?space_id=${spaceId}`}>摄取来源</Link>
                  </div>
                ) : (
                  <fieldset className={styles.sourceFieldset}>
                    <legend>限定来源（可多选）</legend>
                    <div className={styles.scopeSummary}>
                      <span>{selectedSourceIds.length > 0 ? `已固定 ${selectedSourceIds.length} 个来源` : "未选择时使用该空间全部 active 来源"}</span>
                      <div className={styles.actionRow}>
                        <button className={styles.textAction} onClick={() => setSelectedSourceIds(activeSources.map((source) => source.id))} type="button">全选 active</button>
                        <button className={styles.textAction} disabled={selectedSourceIds.length === 0} onClick={() => setSelectedSourceIds([])} type="button">清空</button>
                      </div>
                    </div>
                    <div className={styles.sourceOptionList}>
                      {spaceSources.map((source) => {
                        const activeRevision = activeSourceRevision(source);
                        const disabled = activeRevision === null;
                        return (
                          <label className={styles.sourceOption} data-disabled={disabled} key={source.id}>
                            <input
                              aria-label={`选择 ${sourceTitle(source)}`}
                              checked={selectedSourceIds.includes(source.id)}
                              disabled={disabled}
                              name="source_ids"
                              onChange={() => toggleSource(source.id)}
                              type="checkbox"
                              value={source.id}
                            />
                            <span>
                              <strong>{sourceTitle(source)}</strong>
                              <small>{sourceTypeLabel(source.source_type)} · {disabled ? "无 active revision" : `Revision ${source.active_revision_id} · ${sourceIndexSummary(source)}`}</small>
                            </span>
                            <span className={styles.sourceStatus}>{source.status}</span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                )}
              </>
            )}
          </section>

          <div className={styles.fieldGrid}>
            <div className={styles.field}>
              <label htmlFor="deliverable">交付物</label>
              <select className={styles.select} defaultValue="research_report" id="deliverable" name="deliverable">
                <option value="answer">带引用回答</option>
                <option value="research_report">研究简报</option>
                <option value="comparison">对比报告</option>
              </select>
            </div>
            <div className={styles.field}>
              <label htmlFor="agent-mode">执行模式</label>
              <select className={styles.select} defaultValue="auto" id="agent-mode" name="mode">
                <option value="auto">自动路由</option>
                <option value="force_quick">Quick RAG</option>
                <option value="force_agent">Agent Research</option>
              </select>
            </div>
            <div className={styles.field}>
              <label htmlFor="budget-profile">预算上限</label>
              <select className={styles.select} defaultValue="standard" id="budget-profile" name="budget_profile">
                <option value="quick">Quick · 4 步</option>
                <option value="standard">Standard · 8 步</option>
                <option value="deep">Deep · 16 步</option>
              </select>
            </div>
          </div>

          <label className={styles.checkboxRow}>
            <input checked={recording} name="recording" onChange={(event) => changeRecording(event.target.checked)} type="checkbox" />
            <span>
              <strong>使用 Recording Demo</strong>
              <small>切换后使用 synthetic 空间与来源；界面会持续显示非真实执行标记。</small>
            </span>
          </label>

          {error && <p aria-live="polite" className={styles.errorMessage} role="alert">{error}</p>}
          <button
            className={styles.primaryAction}
            disabled={submitting || scopeLoading || !spaceId || activeSources.length === 0}
            type="submit"
          >
            {submitting ? "正在建立 Run…" : "开始研究"}
            {!submitting && <ArrowRight aria-hidden="true" size={17} />}
          </button>
          {!scopeLoading && spaceId > 0 && activeSources.length === 0 && (
            <p className={styles.errorMessage}><FileCheck2 aria-hidden="true" size={15} /> 当前空间没有可固定的 active revision。</p>
          )}
        </form>

        <aside aria-label="研究护栏" className={styles.guardrailPanel}>
          <p className={styles.stepLabel}>Built-in Guardrails</p>
          <h2>默认约束，而非事后补救</h2>
          <Guardrail icon={DatabaseZap} title="Claim → Evidence" description="每个事实性结论必须绑定 revision、hash 与 locator。" />
          <Guardrail icon={CheckCircle2} title="Bounded Run" description="步数、调用、时间与成本都有明确上限；证据不足可以正常结束。" />
          <Guardrail icon={ShieldCheck} title="Human Approval" description="读取默认允许；写入、外发与执行动作必须经过审批。" />
        </aside>
      </div>
    </div>
  );
}

function Guardrail({ icon: Icon, title, description }: { icon: typeof ShieldCheck; title: string; description: string }) {
  return (
    <article className={styles.guardrail}>
      <span aria-hidden="true"><Icon size={18} /></span>
      <div><h3>{title}</h3><p>{description}</p></div>
    </article>
  );
}
