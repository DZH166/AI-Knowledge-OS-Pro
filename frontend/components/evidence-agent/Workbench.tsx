"use client";

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  DatabaseZap,
  FileCheck2,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { memo, Suspense, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { EvidenceAgentStartError, StartRunInputSchema } from "@/modules/evidence-agent";
import { comparisonRunIntent, researchReadiness, workbenchJourneyHref } from "@/modules/evidence-agent/research-journey";
import {
  clearPendingSubmission, clearWorkbenchDraft, readPendingSubmission, readWorkbenchDraft,
  reconcileWorkbenchScope, savePendingSubmission, saveWorkbenchDraft, sourceCanBeSelected,
  submissionMatchesIntent, type PendingSubmission, type WorkbenchDraft
} from "@/modules/evidence-agent/workbench-session";
import { api } from "@/services/api";
import type { KnowledgeSpace, SourceItem } from "@/types/api";
import styles from "./EvidenceAgent.module.css";
import { ProductTermHelp } from "./ProductTermHelp";
import { ResearchJourneyPanel, type JourneyReadiness } from "./ResearchJourneyPanel";
import { startEvidenceRun } from "./runtime";
import {
  RECORDING_SOURCES,
  RECORDING_SPACES,
  sourceAvailabilityLabel,
  sourceIndexSummary,
  sourceTitle,
  sourceTypeLabel
} from "./source-presenter";

const BUDGETS = {
  quick: { max_steps: 4, max_tool_calls: 6, max_model_calls: 3, max_active_ms: 60_000 },
  standard: { max_steps: 8, max_tool_calls: 12, max_model_calls: 6, max_active_ms: 180_000 },
  deep: { max_steps: 16, max_tool_calls: 24, max_model_calls: 10, max_active_ms: 600_000 }
} as const;

const WORKBENCH_TERMS = ["agent", "rag", "run"] as const;
const DEFAULT_GOAL = "比较现有 RAG 与 Evidence Agent 的可追溯性，并给出有证据约束的升级建议。";
const COMPARISON_GOAL = "比较这三份技术资料，哪个方案更适合当前需求？";

export function Workbench() {
  return <Suspense fallback={<p role="status">正在恢复研究工作台…</p>}><WorkbenchContent /></Suspense>;
}

function WorkbenchContent() {
  const router = useRouter();
  const routerRef = useRef(router);
  routerRef.current = router;
  const searchParams = useSearchParams();
  const query = searchParams.toString();
  const scopeRequest = useRef(0);
  const readinessRequest = useRef(0);
  const submissionInFlight = useRef(false);
  const pendingSubmission = useRef<Partial<Record<"real" | "recording", PendingSubmission>>>({});
  const skipDraftWrite = useRef(true);
  const hasHydrated = useRef(false);
  const modeDrafts = useRef<Partial<Record<"real" | "recording", WorkbenchDraft>>>({});
  const navigationDraft = useRef<{ query: string; draft: WorkbenchDraft } | null>(null);
  const goalRef = useRef<HTMLTextAreaElement>(null);
  const [pendingSubmissions, setPendingSubmissions] = useState(pendingSubmission.current);
  const [blockedModes, setBlockedModes] = useState({ real: false, recording: false });
  const [draftReady, setDraftReady] = useState(false);
  const [storageWarning, setStorageWarning] = useState("");
  const [draftNotice, setDraftNotice] = useState("");
  const [recording, setRecording] = useState(false);
  const [journeyEnabled, setJourneyEnabled] = useState(false);
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  const [dimensions, setDimensions] = useState("方案目标、实施成本、风险与限制");
  const [readiness, setReadiness] = useState<JourneyReadiness>({ state: "checking" });
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [spaceId, setSpaceId] = useState(0);
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [scopeNeedsReview, setScopeNeedsReview] = useState(false);
  const [submissionDetached, setSubmissionDetached] = useState(false);
  const [budgetProfile, setBudgetProfile] = useState<WorkbenchDraft["budgetProfile"]>("standard");
  const [deliverable, setDeliverable] = useState<WorkbenchDraft["deliverable"]>("research_report");
  const [executionMode, setExecutionMode] = useState<WorkbenchDraft["mode"]>("auto");
  const [scopeLoading, setScopeLoading] = useState(true);
  const [scopeError, setScopeError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [sourceQuery, setSourceQuery] = useState("");
  const deferredSourceQuery = useDeferredValue(sourceQuery);
  const currentDraft: WorkbenchDraft = {
    recording, journeyEnabled, goal, dimensions, spaceId, selectedSourceIds,
    scopeNeedsReview, submissionDetached, budgetProfile, deliverable, mode: executionMode
  };
  const latestDraft = useRef(currentDraft);
  latestDraft.current = currentDraft;
  if (draftReady) modeDrafts.current[recording ? "recording" : "real"] = currentDraft;

  const loadScope = useCallback(async (useRecording: boolean, preferredSpaceId = 0, restoredDraft?: WorkbenchDraft) => {
    const request = ++scopeRequest.current;
    setScopeLoading(true);
    setScopeError("");
    try {
      const [spaceData, sourceData] = useRecording
        ? [RECORDING_SPACES, RECORDING_SOURCES]
        : await Promise.all([api.listSpaces(), api.listSources()]);
      if (request !== scopeRequest.current) return;
      const draft = { ...(restoredDraft ?? latestDraft.current), ...latestDraft.current, spaceId: preferredSpaceId };
      const reconciled = reconcileWorkbenchScope(draft, spaceData, sourceData);
      setSpaces(spaceData);
      setSources(sourceData);
      setSpaceId(reconciled.spaceId);
      setSelectedSourceIds(reconciled.selectedSourceIds);
      if (reconciled.removedSourceIds.length > 0 || (preferredSpaceId > 0 && preferredSpaceId !== reconciled.spaceId)) {
        setScopeNeedsReview(true);
        if (pendingSubmission.current[useRecording ? "recording" : "real"]) setSubmissionDetached(true);
      }
      if (preferredSpaceId > 0 && preferredSpaceId !== reconciled.spaceId) {
        const nextDraft = { ...draft, spaceId: reconciled.spaceId, selectedSourceIds: reconciled.selectedSourceIds,
          scopeNeedsReview: true, submissionDetached: draft.submissionDetached || Boolean(pendingSubmission.current[useRecording ? "recording" : "real"]) };
        const href = workbenchJourneyHref({ recording: useRecording, comparison: draft.journeyEnabled,
          spaceId: reconciled.spaceId, explicitScenario: true });
        navigationDraft.current = { query: href.split("?")[1] ?? "", draft: nextDraft };
        if (!saveWorkbenchDraft(nextDraft)) setStorageWarning("当前范围未能保存，刷新可能恢复旧状态。请保留本页或复制研究问题。");
        scopeRequest.current += 1;
        setScopeLoading(true);
        routerRef.current.replace(href, { scroll: false });
      }
    } catch (reason) {
      if (request !== scopeRequest.current) return;
      setSpaces([]);
      setSources([]);
      // Keep the editable scope while the catalog is unavailable; never widen it on a transient failure.
      setScopeError(reason instanceof Error ? reason.message : "无法加载知识空间与来源目录。");
    } finally {
      if (request === scopeRequest.current) setScopeLoading(false);
    }
  }, []);

  const loadReadiness = useCallback(async (useRecording: boolean) => {
    const request = ++readinessRequest.current;
    if (useRecording) {
      setReadiness({ state: "recording" });
      return;
    }
    setReadiness({ state: "checking" });
    try {
      const status = await api.systemStatus({ forceRefresh: true });
      if (request !== readinessRequest.current) return;
      const result = researchReadiness(status);
      setReadiness(result.ready ? { state: "ready" } : { state: "blocked", missing: result.missing });
    } catch {
      if (request === readinessRequest.current) setReadiness({ state: "unknown" });
    }
  }, []);

  useEffect(() => {
    skipDraftWrite.current = true;
    const params = new URLSearchParams(query);
    const useRecording = params.get("demo") === "1";
    const fromNavigation = navigationDraft.current?.query === query ? navigationDraft.current.draft : null;
    navigationDraft.current = null;
    const restored = fromNavigation ?? (hasHydrated.current ? modeDrafts.current[useRecording ? "recording" : "real"] : null)
      ?? readWorkbenchDraft(useRecording);
    const useJourney = params.has("scenario") ? params.get("scenario") === "compare" : restored?.journeyEnabled ?? false;
    const preferredSpaceId = params.has("space_id") ? Number(params.get("space_id")) : restored?.spaceId ?? 0;
    const nextDraft: WorkbenchDraft = restored ?? {
      recording: useRecording, journeyEnabled: useJourney, goal: useJourney ? COMPARISON_GOAL : DEFAULT_GOAL,
      dimensions: "方案目标、实施成本、风险与限制", spaceId: 0, selectedSourceIds: [], scopeNeedsReview: false, submissionDetached: false,
      budgetProfile: "standard", deliverable: "research_report", mode: "auto"
    };
    nextDraft.journeyEnabled = useJourney;
    if (preferredSpaceId !== nextDraft.spaceId && nextDraft.selectedSourceIds.length > 0) nextDraft.scopeNeedsReview = true;
    nextDraft.spaceId = Number.isSafeInteger(preferredSpaceId) && preferredSpaceId > 0 ? preferredSpaceId : 0;
    latestDraft.current = nextDraft;
    setRecording(useRecording);
    setJourneyEnabled(useJourney);
    setGoal(nextDraft.goal);
    setDimensions(nextDraft.dimensions);
    setSpaceId(nextDraft.spaceId);
    setSelectedSourceIds(nextDraft.selectedSourceIds);
    setScopeNeedsReview(nextDraft.scopeNeedsReview);
    setBudgetProfile(nextDraft.budgetProfile);
    setDeliverable(nextDraft.deliverable);
    setExecutionMode(nextDraft.mode);
    setError("");
    setDraftNotice(restored ? "已恢复当前标签页的研究草稿。" : "");
    const realPending = readPendingSubmission(false);
    const recordingPending = readPendingSubmission(true);
    pendingSubmission.current = {
      real: realPending.pending ?? pendingSubmission.current.real,
      recording: recordingPending.pending ?? pendingSubmission.current.recording
    };
    setPendingSubmissions(pendingSubmission.current);
    // A restored pending request is always a deliberate recovery choice, even if the fields happen to match.
    setSubmissionDetached(nextDraft.submissionDetached || Boolean(pendingSubmission.current[useRecording ? "recording" : "real"]));
    setBlockedModes({ real: realPending.blocked, recording: recordingPending.blocked });
    setDraftReady(true);
    hasHydrated.current = true;
    void loadScope(useRecording, nextDraft.spaceId, nextDraft);
    void loadReadiness(useRecording);
    return () => {
      scopeRequest.current += 1;
      readinessRequest.current += 1;
    };
  }, [query, loadReadiness, loadScope]);

  useEffect(() => {
    if (!draftReady) return;
    if (skipDraftWrite.current) { skipDraftWrite.current = false; return; }
    if (!saveWorkbenchDraft(latestDraft.current)) {
      setStorageWarning("浏览器无法保存研究状态；页面仍可使用，但不能保证刷新或返回后恢复。请保留本页，或先复制问题和范围。");
    }
  }, [draftReady, recording, journeyEnabled, goal, dimensions, spaceId, selectedSourceIds, scopeNeedsReview, submissionDetached, budgetProfile, deliverable, executionMode]);

  const visibleSources = useMemo(() => sources.filter((source) => source.space_id === spaceId
    && (!journeyEnabled || source.source_type === "document")), [sources, spaceId, journeyEnabled]);
  const activeSources = useMemo(() => visibleSources.filter((source) => sourceCanBeSelected(source, spaceId, journeyEnabled)), [visibleSources, spaceId, journeyEnabled]);
  const filteredVisibleSources = useMemo(() => {
    const keyword = deferredSourceQuery.trim().toLocaleLowerCase();
    return keyword ? visibleSources.filter((source) => `${sourceTitle(source)} ${sourceTypeLabel(source.source_type)}`.toLocaleLowerCase().includes(keyword)) : visibleSources;
  }, [visibleSources, deferredSourceQuery]);

  function rememberPending(pending: PendingSubmission, useRecording: boolean) {
    pendingSubmission.current = { ...pendingSubmission.current, [useRecording ? "recording" : "real"]: pending };
    setPendingSubmissions(pendingSubmission.current);
    if (!savePendingSubmission(pending)) setStorageWarning("浏览器无法保存待确认请求；本页重试会保留同一编号，但不能保证刷新后恢复。请保留本页并核对运行记录。");
  }

  async function recoverSubmission(pending: PendingSubmission) {
    if (submissionInFlight.current) return;
    submissionInFlight.current = true;
    setSubmitting(true);
    setError("");
    const useRecording = pending.input.provider_mode === "recording";
    rememberPending(pending, useRecording);
    try {
      const result = await startEvidenceRun(pending.input, useRecording, pending.runId);
      rememberPending({ ...pending, runId: result.receipt.run_id }, useRecording);
      if (clearPendingSubmission(useRecording)) {
        pendingSubmission.current = { ...pendingSubmission.current, [useRecording ? "recording" : "real"]: undefined };
        setPendingSubmissions(pendingSubmission.current);
      } else {
        setStorageWarning("任务已确认，但浏览器未能清除本地待确认标记。原任务没有被取消；再次恢复只会打开同一任务。");
      }
      router.push(`/runs/${encodeURIComponent(result.receipt.run_id)}${useRecording ? "?demo=1" : ""}`);
    } catch (reason) {
      if (reason instanceof EvidenceAgentStartError) rememberPending({ ...pending, runId: reason.runId }, useRecording);
      setError(reason instanceof Error ? reason.message : "无法确认研究任务。请保留原请求后重试。");
    } finally {
      setSubmitting(false);
      submissionInFlight.current = false;
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submissionInFlight.current) return;
    if (!spaceId) {
      setError("请先选择一个可用的知识空间。");
      return;
    }
    setError("");
    try {
      if (blockedModes[recording ? "recording" : "real"]) throw new Error("无法读取此前的提交身份。请先核对运行记录，再明确开始新的研究。");
      if (scopeNeedsReview) throw new Error("原证据范围发生了变化，请先重新选择或确认当前范围。");
      if (scopeError) throw new Error("请先重新加载证据目录，避免提交过期范围。");
      if (journeyEnabled && readiness.state === "blocked") throw new Error(`真实研究暂不可用：${readiness.missing.join("、")}未就绪。`);
      const intent = journeyEnabled ? comparisonRunIntent({
        spaceId, question: goal, dimensions, sourceIds: selectedSourceIds,
        budget: BUDGETS[budgetProfile], recording
      }) : {
        schema_version: 1 as const,
        space_id: spaceId,
        goal,
        scope: { source_ids: selectedSourceIds },
        deliverable: { kind: deliverable },
        mode: executionMode,
        budget: BUDGETS[budgetProfile],
        permissions: { read_only: true, allow_scope_expansion: false },
        provider_mode: recording ? "recording" as const : "real" as const
      };
      const pending = pendingSubmission.current[recording ? "recording" : "real"];
      if (pending && (submissionDetached || !submissionMatchesIntent(pending, intent))) throw new Error("此前提交尚未确认，当前草稿已改变或已与原提交解绑。请恢复原研究，或核对运行记录后明确开始新的研究。");
      const next = pending ?? { input: StartRunInputSchema.parse({ ...intent, request_id: crypto.randomUUID() }) };
      await recoverSubmission(next);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "无法开始研究。请检查配置后重试。"
      );
    }
  }

  function changeRecording(nextRecording: boolean) {
    if (!saveWorkbenchDraft(latestDraft.current)) setStorageWarning("当前更改未能保存，刷新可能恢复旧草稿。请保留本页或复制研究问题。");
    const nextDraft = modeDrafts.current[nextRecording ? "recording" : "real"] ?? readWorkbenchDraft(nextRecording) ?? {
      recording: nextRecording, journeyEnabled, goal: journeyEnabled ? COMPARISON_GOAL : DEFAULT_GOAL,
      dimensions: "方案目标、实施成本、风险与限制", spaceId: 0, selectedSourceIds: [], scopeNeedsReview: false,
      submissionDetached: false, budgetProfile: "standard", deliverable: "research_report", mode: "auto"
    };
    // Commit the user's checkbox choice immediately, rather than waiting for the URL transition.
    scopeRequest.current += 1;
    readinessRequest.current += 1;
    setRecording(nextRecording);
    setJourneyEnabled(nextDraft.journeyEnabled);
    setGoal(nextDraft.goal);
    setDimensions(nextDraft.dimensions);
    setSpaceId(nextDraft.spaceId);
    setSelectedSourceIds(nextDraft.selectedSourceIds);
    setScopeNeedsReview(nextDraft.scopeNeedsReview);
    setSubmissionDetached(nextDraft.submissionDetached || Boolean(pendingSubmission.current[nextRecording ? "recording" : "real"]));
    setBudgetProfile(nextDraft.budgetProfile);
    setDeliverable(nextDraft.deliverable);
    setExecutionMode(nextDraft.mode);
    setSpaces([]);
    setSources([]);
    setScopeLoading(true);
    setReadiness(nextRecording ? { state: "recording" } : { state: "checking" });
    setError("");
    navigateDraft(nextDraft);
  }

  function navigateDraft(nextDraft: WorkbenchDraft) {
    // Hide the old catalog immediately: a new-space selection must not precede URL hydration.
    scopeRequest.current += 1;
    setScopeLoading(true);
    const href = workbenchJourneyHref({ recording: nextDraft.recording, comparison: nextDraft.journeyEnabled,
      spaceId: nextDraft.spaceId, explicitScenario: true });
    navigationDraft.current = { query: href.split("?")[1] ?? "", draft: nextDraft };
    modeDrafts.current[nextDraft.recording ? "recording" : "real"] = nextDraft;
    if (!saveWorkbenchDraft(nextDraft)) setStorageWarning("当前更改未能保存，刷新可能恢复旧草稿。请保留本页或复制研究问题。");
    router.replace(href, { scroll: false });
  }

  function toggleJourney() {
    const nextEnabled = !journeyEnabled;
    setError("");
    setJourneyEnabled(nextEnabled);
    setSelectedSourceIds([]);
    setScopeNeedsReview(false);
    markDraftEdited();
    if (nextEnabled && goal === DEFAULT_GOAL) setGoal(COMPARISON_GOAL);
    navigateDraft({ ...latestDraft.current, journeyEnabled: nextEnabled, selectedSourceIds: [], scopeNeedsReview: false,
      submissionDetached: submissionDetached || Boolean(pendingSubmission.current[recording ? "recording" : "real"]),
      goal: nextEnabled && goal === DEFAULT_GOAL ? COMPARISON_GOAL : goal });
  }

  const toggleSource = useCallback((sourceId: number) => {
    if (!selectedSourceIds.includes(sourceId) && selectedSourceIds.length >= 200) {
      setError("一次最多固定 200 个来源，请缩小本次研究范围。");
      return;
    }
    setScopeNeedsReview(false);
    if (pendingSubmission.current[recording ? "recording" : "real"]) setSubmissionDetached(true);
    setSelectedSourceIds((current) => current.includes(sourceId)
      ? current.filter((id) => id !== sourceId)
      : [...current, sourceId]);
  }, [selectedSourceIds, recording]);

  function markDraftEdited() {
    if (pendingSubmission.current[recording ? "recording" : "real"]) setSubmissionDetached(true);
  }

  function clearDraft() {
    const cleared = clearWorkbenchDraft(recording);
    if (!cleared) setStorageWarning("浏览器未能清除已保存的草稿。当前表单已重置，但刷新可能恢复旧草稿。");
    setGoal(journeyEnabled ? COMPARISON_GOAL : DEFAULT_GOAL);
    setDimensions("方案目标、实施成本、风险与限制");
    setSelectedSourceIds([]);
    setScopeNeedsReview(false);
    setSubmissionDetached(Boolean(pendingSubmission.current[recording ? "recording" : "real"]));
    setBudgetProfile("standard");
    setDeliverable("research_report");
    setExecutionMode("auto");
    setDraftNotice(cleared ? "草稿已清除。此前尚未确认的任务没有被取消，仍可恢复原研究。"
      : "当前表单已重置，但草稿清除失败，刷新可能恢复旧状态。此前尚未确认的任务没有被取消，仍可恢复原研究。");
    requestAnimationFrame(() => goalRef.current?.focus());
  }

  function acknowledgeNewResearch() {
    const mode = recording ? "recording" : "real";
    if (!clearPendingSubmission(recording)) {
      setStorageWarning("浏览器未能清除待确认标记。原任务没有被取消；本页状态不能保证刷新后恢复。");
      if (pendingSubmission.current[mode]) { setError("原请求身份仍被保留，请先恢复原研究。"); return; }
    }
    pendingSubmission.current = { ...pendingSubmission.current, [mode]: undefined };
    setPendingSubmissions(pendingSubmission.current);
    setBlockedModes((current) => ({ ...current, [mode]: false }));
    setSubmissionDetached(false);
    setDraftNotice("下次提交会创建新的研究。旧任务没有被取消，仍可在运行记录中查看。");
    setError("");
    requestAnimationFrame(() => goalRef.current?.focus());
  }

  return (
    <div className={styles.page}>
      <header className={`${styles.hero} ${styles.workbenchHero}`}>
        <div className={styles.workbenchHeroCopy}>
          <p className={styles.editorialIndex}>研究空间 / 新任务</p>
          <h1>研究工作台</h1>
          <p className={styles.lead}>
            提出问题，选定资料。让每个结论都能回到原文核对。
          </p>
        </div>
        <aside aria-label="工作台状态与入口" className={styles.workbenchHeroAside}>
          <Link className={styles.secondaryAction} href={`/runs${recording ? "?demo=1" : ""}`}>
            查看运行记录 <ArrowRight aria-hidden="true" size={16} />
          </Link>
          {recording && (
            <div aria-live="polite" className={styles.demoBanner} role="status">
              <Sparkles aria-hidden="true" size={18} />
              <div>
                <strong>演示模式 · 非真实执行</strong>
                <span>使用固定示例资料，不调用模型或生产检索。</span>
              </div>
            </div>
          )}
          <ProductTermHelp terms={WORKBENCH_TERMS} />
        </aside>
      </header>

      <ResearchJourneyPanel
        activeSourceCount={activeSources.length}
        disabled={!draftReady}
        enabled={journeyEnabled}
        onToggle={toggleJourney}
        readiness={readiness}
        selectedSourceCount={selectedSourceIds.length}
        spaceId={spaceId}
        totalSourceCount={visibleSources.length}
      />

      {(pendingSubmissions.real || pendingSubmissions.recording || blockedModes[recording ? "recording" : "real"]) && (
        <section aria-label="待确认研究" className={styles.attentionCard}>
          <h2>{pendingSubmissions.real || pendingSubmissions.recording ? "有研究尚未确认" : "无法确认此前的提交状态"}</h2>
          <p>清除草稿、修改问题或切换模式不会取消原任务。恢复只使用原始问题、范围和预算，不会自动提交。</p>
          {(["real", "recording"] as const).map((mode) => {
            const pending = pendingSubmissions[mode];
            const sourceCount = pending?.input.scope?.source_ids?.length ?? 0;
            return pending ? <div className={styles.field} key={mode}>
              <strong>{mode === "real" ? "真实研究" : "录制研究"}：{pending.input.goal.split("\n")[0]}</strong>
              <small>原范围：{sourceCount ? `${sourceCount} 个来源` : "整个知识空间"} · 原预算：最多 {pending.input.budget?.max_steps ?? 8} 步</small>
              <small>请求编号：{pending.input.request_id}{pending.runId ? ` · 任务编号：${pending.runId}` : " · 创建结果尚未确认"}</small>
              <div className={styles.actionRow}>
                <button className={styles.secondaryAction} disabled={submitting} onClick={() => void recoverSubmission(pending)} type="button">
                  {pending.runId ? "打开已创建的研究" : "恢复原研究"}
                </button>
              </div>
            </div> : null;
          })}
          {blockedModes[recording ? "recording" : "real"] && <p role="alert">无法读取此前的提交身份；请先核对运行记录，避免重复创建任务。</p>}
          <small>开始新研究只解除当前{recording ? "录制" : "真实"}模式的待确认状态，不会取消已有任务。</small>
          <div className={styles.actionRow}>
            <Link className={styles.quietAction} href={`/runs${recording ? "?demo=1" : ""}`}>核对运行记录</Link>
            <button className={styles.quietAction} disabled={submitting} onClick={acknowledgeNewResearch} type="button">已核对记录，开始新的研究</button>
          </div>
        </section>
      )}

      {storageWarning && <p role="status">{storageWarning}</p>}
      {draftNotice && <p aria-live="polite" role="status">{draftNotice}</p>}

      <div className={styles.workbenchGrid}>
        <form onSubmit={(event) => void submit(event)}>
          <fieldset aria-label="研究草稿编辑区" className={styles.formCard} disabled={!draftReady} style={{ margin: 0, minWidth: 0 }}>
          <div className={`${styles.sectionHeading} ${styles.formHeading}`}>
            <div>
              <p className={styles.stepLabel}>问题与资料</p>
              <h2>新研究</h2>
            </div>
            <div className={styles.actionRow}>
              <span className={styles.requiredNote}>* 必填</span>
              <button className={styles.textAction} disabled={submitting} onClick={clearDraft} type="button">清除草稿</button>
            </div>
          </div>

          <div className={`${styles.field} ${styles.goalField} ${journeyEnabled ? styles.comparisonGoalField : ""}`}>
            <label htmlFor="research-goal">研究目标 *</label>
            <textarea
              aria-describedby="goal-help"
              autoComplete="off"
              className={styles.textarea}
              id="research-goal"
              maxLength={4_000}
              name="goal"
              onChange={(event) => { setGoal(event.target.value); markDraftEdited(); }}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="例如：比较 3 份方案，指出冲突证据，并产出决策简报…"
              ref={goalRef}
              required
              value={goal}
            />
            <small id="goal-help">最多 4000 字；{journeyEnabled ? "还会加上比较维度和证据要求，合计不能超出上限。" : "描述需要验证的事实与最终决策。"}系统不会展示或保存模型的隐藏思维过程。按 <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 直接提交。</small>
          </div>

          {journeyEnabled && (
            <div className={styles.field}>
              <label htmlFor="comparison-dimensions">比较维度 *</label>
              <input
                className={styles.input}
                id="comparison-dimensions"
                name="comparison_dimensions"
                maxLength={1_000}
                onChange={(event) => { setDimensions(event.target.value); markDraftEdited(); }}
                placeholder="例如：性能、成本、风险与限制"
                required
                value={dimensions}
              />
              <small>用逗号或顿号分开；系统会要求逐份资料给出证据、冲突和缺口。</small>
            </div>
          )}

              <section aria-labelledby="scope-heading" className={styles.scopePicker}>
                <div className={styles.sectionHeading}>
                  <div>
                    <p className={styles.stepLabel}>本次使用的资料</p>
                    <h2 id="scope-heading">证据范围</h2>
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
              <div aria-live="polite" className={styles.scopeEmpty} role="status">正在加载知识空间与资料版本…</div>
            ) : scopeError ? (
              <div className={styles.scopeEmpty} role="alert">
                <AlertTriangle aria-hidden="true" size={22} />
                <strong>证据目录加载失败</strong>
                <span>{scopeError}</span>
                <button className={styles.quietAction} disabled={scopeLoading} onClick={() => void loadScope(recording, spaceId)} type="button">重试</button>
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
                      setScopeNeedsReview(false);
                      markDraftEdited();
                      const nextDraft = { ...latestDraft.current, spaceId: Number(event.target.value), selectedSourceIds: [], scopeNeedsReview: false,
                        submissionDetached: submissionDetached || Boolean(pendingSubmission.current[recording ? "recording" : "real"]) };
                      navigateDraft(nextDraft);
                    }}
                    required
                    value={spaceId}
                  >
                    {spaces.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                  </select>
                </div>

                {visibleSources.length === 0 ? (
                  <div className={styles.scopeEmpty}>
                    <UploadCloud aria-hidden="true" size={24} />
                    <strong>{journeyEnabled ? "这个空间还没有文档" : "这个空间还没有来源"}</strong>
                    <span>{journeyEnabled ? "上传三份文档，等处理完成后再开始对比。" : "摄取文档、媒体或代码仓库，建立可用版本后再开始研究。"}</span>
                    <Link className={styles.quietAction} href={`/upload?space_id=${spaceId}${journeyEnabled ? "&scenario=compare" : ""}`}>上传资料</Link>
                  </div>
                ) : (
                  <fieldset className={styles.sourceFieldset}>
                    <legend>{journeyEnabled ? "选择至少三份可用资料" : "限定来源（可多选）"}</legend>
                    <div className={styles.searchField}>
                      <Search aria-hidden="true" size={15} />
                      <input aria-label="搜索本次可选资料" autoComplete="off" name="source_search" onChange={(event) => setSourceQuery(event.target.value)} placeholder="搜索标题或资料类型…" type="search" value={sourceQuery} />
                    </div>
                    <div className={styles.scopeSummary}>
                      <span>{selectedSourceIds.length > 0 ? `已固定 ${selectedSourceIds.length} 个来源` : journeyEnabled ? "请明确选择本次的三份资料" : "未选择时使用该空间全部可用来源"}</span>
                      <div className={styles.actionRow}>
                        <button className={styles.textAction} onClick={() => {
                          if (activeSources.length > 200) { setError("一次最多固定 200 个来源，请手动缩小本次研究范围。"); return; }
                          setSelectedSourceIds(activeSources.map((source) => source.id)); setScopeNeedsReview(false); markDraftEdited();
                        }} type="button">全选可用资料</button>
                        <button className={styles.textAction} disabled={selectedSourceIds.length === 0} onClick={() => { setSelectedSourceIds([]); setScopeNeedsReview(false); markDraftEdited(); }} type="button">清空</button>
                      </div>
                    </div>
                    <div aria-busy={sourceQuery !== deferredSourceQuery} className={styles.sourceOptionList}>
                      <SourceOptions sources={filteredVisibleSources} selectedSourceIds={selectedSourceIds} spaceId={spaceId} journeyEnabled={journeyEnabled} onToggle={toggleSource} />
                      {filteredVisibleSources.length === 0 && <p className={styles.noMatches}>没有匹配的资料。<button className={styles.textAction} onClick={() => setSourceQuery("")} type="button">清除搜索</button></p>}
                    </div>
                    <small className={styles.count}>显示 {filteredVisibleSources.length} / {visibleSources.length} 份 · 搜索不会改变已选范围</small>
                  </fieldset>
                )}
              </>
            )}
              </section>

          <details className={styles.advancedSettings} key={journeyEnabled ? "comparison" : "ordinary"} open={journeyEnabled || undefined}>
            <summary>
              <span>{journeyEnabled ? "运行设置" : "来源与运行设置"}</span>
              <small>{BUDGETS[budgetProfile].max_steps} 步上限 · {recording ? "演示" : "真实研究"}</small>
            </summary>
            <div className={styles.advancedSettingsBody}>
              <div className={styles.fieldGrid}>
                {!journeyEnabled && <div className={styles.field}>
                  <label htmlFor="deliverable">交付物</label>
                  <select className={styles.select} value={deliverable} onChange={(event) => { setDeliverable(event.target.value as WorkbenchDraft["deliverable"]); markDraftEdited(); }} id="deliverable" name="deliverable">
                    <option value="answer">带引用回答</option>
                    <option value="research_report">研究简报</option>
                    <option value="comparison">对比报告</option>
                  </select>
                </div>}
                {!journeyEnabled && <div className={styles.field}>
                  <label htmlFor="agent-mode">执行模式</label>
                  <select className={styles.select} value={executionMode} onChange={(event) => { setExecutionMode(event.target.value as WorkbenchDraft["mode"]); markDraftEdited(); }} id="agent-mode" name="mode">
                    <option value="auto">自动选择模式</option>
                    <option value="force_quick">快速检索问答</option>
                    <option value="force_agent">多步证据研究</option>
                  </select>
                </div>}
                <div className={styles.field}>
                  <label htmlFor="budget-profile">预算上限</label>
                  <select className={styles.select} value={budgetProfile} onChange={(event) => { setBudgetProfile(event.target.value as WorkbenchDraft["budgetProfile"]); markDraftEdited(); }} id="budget-profile" name="budget_profile">
                    <option value="quick">轻量 · 最多 4 步</option>
                    <option value="standard">标准 · 最多 8 步</option>
                    <option value="deep">深入 · 最多 16 步</option>
                  </select>
                </div>
              </div>

              <label className={styles.checkboxRow}>
                <input checked={recording} name="recording" onChange={(event) => changeRecording(event.target.checked)} type="checkbox" />
                <span>
                  <strong>使用演示模式</strong>
                  <small>切换后使用示例空间与资料；界面会持续显示非真实执行标记。</small>
                </span>
              </label>
            </div>
          </details>

          {scopeNeedsReview && <div className={styles.scopeEmpty} role="alert">
            <strong>原证据范围需要重新确认</strong>
            <span>部分资料已退役、不可用或不属于当前空间。请重新选择；清空选择的普通研究会使用整个空间。</span>
            <button className={styles.quietAction} onClick={() => setScopeNeedsReview(false)} type="button">确认使用当前证据范围</button>
          </div>}
          {error && <p aria-live="polite" className={styles.errorMessage} role="alert">{error}</p>}
          {!scopeLoading && spaceId > 0 && activeSources.length === 0 && (
            <p className={styles.errorMessage}><FileCheck2 aria-hidden="true" size={15} /> {journeyEnabled ? "当前空间没有处理完成的文档。" : "当前空间没有可用的来源版本。"}</p>
          )}
          {!recording && readiness.state !== "checking" && (
            <p
              className={readiness.state === "blocked" ? styles.readinessBlocked : styles.readinessReady}
              role="status"
            >
              {readiness.state === "blocked" ? (
                <>真实研究暂不可用：{readiness.missing.join("、")}未就绪。<Link href="/system">查看配置</Link></>
              ) : readiness.state === "ready" ? (
                <>真实研究服务已就绪：语言模型、向量生成、向量库与任务队列均可使用。</>
              ) : (
                <>未能确认服务状态；提交前请先在<Link href="/system">模型与服务</Link>检查配置。</>
              )}
            </p>
          )}
          <div className={styles.formSubmitRow}>
            <p className={styles.formAssurance}>
              <span>只读证据</span>
              <span>固定来源版本</span>
              <span>写入前审批</span>
            </p>
            <button
              className={styles.primaryAction}
              disabled={submitting || !draftReady || scopeLoading || Boolean(scopeError) || scopeNeedsReview || blockedModes[recording ? "recording" : "real"] || !spaceId || activeSources.length === 0 || (journeyEnabled && (selectedSourceIds.length < 3 || readiness.state === "blocked"))}
              type="submit"
            >
              {submitting ? "正在创建研究任务…" : journeyEnabled ? "开始对比研究" : "开始研究"}
              {!submitting && <ArrowRight aria-hidden="true" size={17} />}
            </button>
          </div>
          </fieldset>
        </form>

        <aside aria-label="研究护栏" className={styles.guardrailPanel}>
          <details><summary>研究规则：可回溯的结论、有上限的运行、发布前确认</summary>
          <div className={styles.guardrailList}>
            <Guardrail icon={DatabaseZap} title="结论可回溯" description="每个事实结论绑定来源版本与精确位置。" />
            <Guardrail icon={CheckCircle2} title="运行有边界" description="步数、时间与成本均有明确上限。" />
            <Guardrail icon={ShieldCheck} title="人工审批" description="写入、外发与执行动作必须经过批准。" />
          </div>
          </details>
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

const SourceOptions = memo(function SourceOptions({ sources, selectedSourceIds, spaceId, journeyEnabled, onToggle }: {
  sources: readonly SourceItem[]; selectedSourceIds: readonly number[]; spaceId: number; journeyEnabled: boolean; onToggle: (sourceId: number) => void;
}) {
  const selected = new Set(selectedSourceIds);
  return sources.map((source) => {
    const disabled = !sourceCanBeSelected(source, spaceId, journeyEnabled);
    const availability = sourceAvailabilityLabel(source);
    return <label className={styles.sourceOption} data-disabled={disabled} key={source.id}>
      <input aria-label={`选择 ${sourceTitle(source)}`} checked={selected.has(source.id)} disabled={disabled} name="source_ids" onChange={() => onToggle(source.id)} type="checkbox" value={source.id} />
      <span><strong>{sourceTitle(source)}</strong><small>{sourceTypeLabel(source.source_type)} · {disabled ? "没有可用版本" : `版本 ${source.active_revision_id} · ${sourceIndexSummary(source)}`}</small></span>
      <span className={styles.sourceStatus}>{source.status === "retired" ? "已退役" : disabled && availability === "可用" ? "尚不可用" : availability}</span>
    </label>;
  });
});
