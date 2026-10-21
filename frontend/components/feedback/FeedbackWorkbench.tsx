"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FeedbackClient, FeedbackIntent, downloadSample } from "@/modules/feedback/client";
import {
  ModeSchema, SplitSchema, StatusSchema, issueLabel, modeLabel, splitLabel, statusLabel,
  type Feedback, type FeedbackPage, type Mode, type ReviewFeedback, type Split, type Status
} from "@/modules/feedback/contract";
import styles from "./Feedback.module.css";

export function FeedbackWorkbench() {
  const client = useMemo(() => new FeedbackClient(), []);
  const router = useRouter();
  const search = useSearchParams();
  const rawId = search.get("id");
  const selectedId = rawId && /^[1-9]\d*$/.test(rawId) && Number.isSafeInteger(Number(rawId)) ? Number(rawId) : null;
  const [status, setStatus] = useState<Status | "">("");
  const [mode, setMode] = useState<Mode | "">("");
  const [after, setAfter] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [catalog, setCatalog] = useState<FeedbackPage | null>(null);
  const [detail, setDetail] = useState<Feedback | null>(null);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState<number[]>([]);
  const [exportConsent, setExportConsent] = useState(false);
  const [exportMessage, setExportMessage] = useState("");
  const [exportError, setExportError] = useState("");
  const exportPending = useRef(false);
  const exportRequest = useRef<AbortController | null>(null);
  const detailRequest = useRef<AbortController | null>(null);
  const handleBusy = useCallback((value: boolean) => {
    setBusy(value);
    if (value) { detailRequest.current?.abort(); setDetailLoading(false); }
  }, []);
  useEffect(() => () => exportRequest.current?.abort(), []);

  useEffect(() => {
    if (busy) return;
    const abort = new AbortController();
    setLoading(true); setListError("");
    void client.list({ status: status || undefined, provider_mode: mode || undefined, after }, abort.signal)
      .then(value => { if (!abort.signal.aborted) setCatalog(value); })
      .catch(reason => { if (!abort.signal.aborted) { setCatalog(null); setListError(message(reason)); } })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [after, busy, client, mode, refresh, status]);

  useEffect(() => {
    setDetail(null); setDetailError("");
    if (selectedId === null) { setDetailLoading(false); return; }
    const abort = new AbortController();
    detailRequest.current = abort;
    setDetailLoading(true);
    void client.get(selectedId, abort.signal)
      .then(value => { if (!abort.signal.aborted) setDetail(value); })
      .catch(reason => { if (!abort.signal.aborted) setDetailError(message(reason)); })
      .finally(() => { if (!abort.signal.aborted) setDetailLoading(false); });
    return () => abort.abort();
  }, [client, refresh, selectedId]);

  function resetSelection() { setSelection([]); setExportConsent(false); setExportMessage(""); setExportError(""); }
  const selected = catalog?.items.filter(item => selection.includes(item.id)) ?? [];
  const compatible = selected.length > 0 && selected.length === selection.length
    && selected.every(item => item.status === "accepted" && item.sample?.split === selected[0].sample?.split
      && item.provider_mode === selected[0].provider_mode);

  async function exportCases() {
    if (exportPending.current || busy || !compatible || !exportConsent) return;
    exportPending.current = true; setBusy(true); setExportError(""); setExportMessage("");
    const abort = new AbortController(); exportRequest.current = abort;
    try {
      const receipt = await client.export(selection, abort.signal);
      if (!abort.signal.aborted) { downloadSample(receipt); setExportMessage(`已校验并导出 ${receipt.count} 个${splitLabel[receipt.split]}。`); }
    } catch (reason) { if (!abort.signal.aborted) setExportError(message(reason)); }
    finally { exportPending.current = false; if (!abort.signal.aborted) setBusy(false); }
  }

  return <div className={styles.page} data-testid="feedback-workbench">
    <header className={styles.header}><div><p className={styles.muted}>Feedback Review · 反馈审阅</p><h1>把问题变成可检查的样例</h1></div>
      <Link className={styles.quiet} href="/evaluations">返回评测中心</Link></header>
    <p className={styles.notice}>仅限可信本地工作区。接受反馈只保存人工预期，不修改原答案、不写入知识库、不启用策略。新样例尚未接入自动评分，不能当作模型已通过的成绩。</p>
    <div className={styles.filters}>
      <label>反馈状态<select disabled={busy} value={status} onChange={event => {
        setStatus(event.target.value ? StatusSchema.parse(event.target.value) : ""); setAfter(0); resetSelection();
      }}><option value="">全部状态</option>{StatusSchema.options.map(value => <option key={value} value={value}>{statusLabel[value]}</option>)}</select></label>
      <label>运行模式<select disabled={busy} value={mode} onChange={event => {
        setMode(event.target.value ? ModeSchema.parse(event.target.value) : ""); setAfter(0); resetSelection();
      }}><option value="">全部模式</option>{ModeSchema.options.map(value => <option key={value} value={value}>{modeLabel[value]}</option>)}</select></label>
      <button className={styles.quiet} disabled={busy || loading} onClick={() => setRefresh(value => value + 1)}>刷新反馈</button>
    </div>
    <div className={styles.grid}>
      <section className={styles.panel} aria-label="反馈列表">
        <h2>反馈记录</h2>
        {loading && <p role="status">正在读取反馈…</p>}
        {listError && <p role="alert" className={styles.error}>{listError}</p>}
        {!loading && catalog?.items.length === 0 && <p className={styles.muted}>当前没有符合筛选条件的反馈。可以从研究成果页反馈一条结论。</p>}
        <ul className={styles.list}>{catalog?.items.map(item => <li className={styles.item} key={item.id}>
          <span className={styles.badge}>#{item.id} · {statusLabel[item.status]} · {modeLabel[item.provider_mode]}</span>
          <strong>{issueLabel[item.issue]}</strong><span className={styles.text}>{item.comment}</span>
          <button className={styles.quiet} disabled={busy || loading} aria-pressed={selectedId === item.id}
            onClick={() => router.replace(`/evaluations/feedback?id=${item.id}`)}>审阅反馈 #{item.id}</button>
          {item.sample && <label className={styles.check}><input type="checkbox" disabled={busy || loading} checked={selection.includes(item.id)}
            onChange={event => { setSelection(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id));
              setExportConsent(false); setExportMessage(""); setExportError(""); }} />选择样例 #{item.id} · {splitLabel[item.sample.split]}</label>}
        </li>)}</ul>
        <div className={styles.row}>
          {after > 0 && <button disabled={busy || loading} className={styles.quiet} onClick={() => { setAfter(0); resetSelection(); }}>返回第一页</button>}
          {catalog?.next_after && <button disabled={busy || loading} className={styles.quiet} onClick={() => { setAfter(catalog.next_after!); resetSelection(); }}>下一页反馈</button>}
        </div>
        <p className={styles.muted}>当前选择 {selection.length} 个样例。不同用途或运行模式必须分别导出；选择只保留在当前页。</p>
        <label className={styles.check}><input type="checkbox" checked={exportConsent} disabled={busy || !compatible}
          onChange={event => setExportConsent(event.target.checked)} />我知道导出包含原始问题、成果、证据摘录及人工备注，只下载到本机。</label>
        <button className={styles.button} disabled={busy || loading || !compatible || !exportConsent} onClick={() => void exportCases()}>导出所选样例</button>
        {selection.length > 0 && !compatible && <p className={styles.muted}>请选择相同用途与运行模式的已接受样例。</p>}
        {exportMessage && <p role="status">{exportMessage}</p>}{exportError && <p role="alert" className={styles.error}>{exportError}</p>}
      </section>
      <section className={styles.panel} aria-label="反馈详情">
        {rawId && selectedId === null && <p role="alert">反馈标识无效。</p>}
        {detailLoading && <p role="status">正在读取原始快照…</p>}
        {detailError && <p role="alert" className={styles.error}>{detailError}</p>}
        {!rawId && <p className={styles.muted}>选择一条反馈，核对原结论和证据，再决定接受或驳回。</p>}
        {detail && <>
          <h2>反馈 #{detail.id} · {statusLabel[detail.status]}</h2>
          <p className={styles.badge}>{modeLabel[detail.provider_mode]} · {issueLabel[detail.issue]}</p>
          <p className={styles.text}>{detail.comment}</p>
          <SnapshotView item={detail} />
          {detail.status === "pending" ? <ReviewForm key={`${detail.id}:${detail.version}`} item={detail} client={client}
            disabled={busy} onBusy={handleBusy} onSaved={item => { setDetail(item); setRefresh(value => value + 1); resetSelection(); }} /> : <>
            <h3>人工审阅结果</h3><p className={styles.text}>{detail.review?.reason}</p>
            <p className={styles.muted}>操作来源：本地用户（不是已鉴权的多人身份）</p>
            {detail.sample && <><h3>{splitLabel[detail.sample.split]}</h3><p className={styles.text}>{detail.sample.expected_answer}</p>
              <h3>验收要求</h3><p className={styles.text}>{detail.sample.acceptance_criteria}</p>
              <p className={styles.muted}>人工参考预期，尚未自动验证真伪。{detail.sample.reference_evidence_ids.length ? `标注了 ${detail.sample.reference_evidence_ids.length} 条快照内证据。` : "没有标注参考证据。"}</p></>}
          </>}
        </>}
      </section>
    </div>
  </div>;
}

function SnapshotView({ item }: { item: Feedback }) {
  const snapshot = item.snapshot;
  return <div>
    <h3>出错时的任务与结论</h3><p className={styles.text}>{snapshot.goal}</p>
    <blockquote className={styles.snapshot}>{snapshot.claim?.text ?? snapshot.artifact_body}</blockquote>
    <Link className={styles.quiet} href={`/artifacts/${encodeURIComponent(item.artifact_id)}`}>查看原成果与引用</Link>
    <details><summary>完整成果正文</summary><div className={styles.snapshot}>{snapshot.artifact_body}</div></details>
    <dl className={styles.facts}>
      <div><dt>任务 / 版本</dt><dd>{snapshot.run_id} / {snapshot.run_version}</dd></div>
      <div><dt>策略版本</dt><dd>{snapshot.policy_id ?? "未记录策略身份"} / {snapshot.policy_version ?? "—"}</dd></div>
      <div><dt>快照 SHA-256（内容指纹）</dt><dd>{item.snapshot_sha256}</dd></div>
    </dl>
    <h3>当时保存的证据</h3>
    {snapshot.evidence.length === 0 && <p className={styles.muted}>此反馈目标没有关联证据；不会补造原文。</p>}
    {snapshot.evidence.map(evidence => <details key={evidence.id}><summary>证据 {evidence.id} · 来源 {evidence.source_id} / 版本 {evidence.revision_id} / 片段 {evidence.chunk_id}</summary>
      <p className={styles.snapshot}>{evidence.excerpt}</p><p className={styles.muted}>内容指纹：{evidence.content_hash}</p></details>)}
  </div>;
}

function ReviewForm({ item, client, disabled, onBusy, onSaved }: {
  item: Feedback; client: FeedbackClient; disabled: boolean; onBusy: (busy: boolean) => void; onSaved: (item: Feedback) => void;
}) {
  const [decision, setDecision] = useState<"accepted" | "rejected">("accepted");
  const [reason, setReason] = useState("");
  const [answer, setAnswer] = useState("");
  const [criteria, setCriteria] = useState("");
  const [split, setSplit] = useState<Split>("tuning");
  const [references, setReferences] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const identity = useRef(new FeedbackIntent());
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => { request.current?.abort(); onBusy(false); }, [onBusy]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || disabled) return;
    pending.current = true; setBusy(true); onBusy(true); setError("");
    const abort = new AbortController(); request.current = abort;
    const intent = { expected_version: item.version, decision, reason: reason.trim(),
      ...(decision === "accepted" ? { expected_answer: answer.trim(), acceptance_criteria: criteria.trim(), split, reference_evidence_ids: references } : { reference_evidence_ids: [] }) };
    const command: ReviewFeedback = { ...intent, request_id: identity.current.for(intent) };
    try {
      const result = await client.review(item.id, command, abort.signal);
      if (!abort.signal.aborted) onSaved(result.feedback);
    } catch (reason) { if (!abort.signal.aborted) setError(message(reason)); }
    finally { pending.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }

  return <form className={styles.form} onSubmit={submit} aria-label="人工审阅">
    <fieldset className={styles.reviewFields} disabled={busy || disabled}>
    <h3>人工审阅</h3>
    <label className={styles.field}>审阅决定<select disabled={busy} value={decision} onChange={event => setDecision(event.target.value === "accepted" ? "accepted" : "rejected")}>
      <option value="accepted">接受，生成评测样例</option><option value="rejected">驳回，不生成样例</option></select></label>
    <label className={styles.field}>审阅理由<textarea value={reason} disabled={busy} required maxLength={2000} onChange={event => setReason(event.target.value)} /></label>
    {decision === "accepted" && <>
      <label className={styles.field}>人工参考答案<textarea value={answer} disabled={busy} required maxLength={8000} onChange={event => setAnswer(event.target.value)} /></label>
      <label className={styles.field}>验收要求<textarea value={criteria} disabled={busy} required maxLength={2000} onChange={event => setCriteria(event.target.value)} /></label>
      <label className={styles.field}>样例用途<select value={split} disabled={busy} onChange={event => setSplit(SplitSchema.parse(event.target.value))}>
        {SplitSchema.options.map(value => <option value={value} key={value}>{splitLabel[value]}</option>)}</select></label>
      <p className={styles.muted}>调参样例用于改进；留出样例用于阶段验收，不参与日常调参。用途确定后本阶段不允许改写。</p>
      {item.snapshot.evidence.map(evidence => <label className={styles.check} key={evidence.id}><input type="checkbox" disabled={busy}
        checked={references.includes(evidence.id)} onChange={event => setReferences(ids => event.target.checked ? [...ids, evidence.id] : ids.filter(id => id !== evidence.id))} />标注参考证据 {evidence.id}</label>)}
    </>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    <button className={styles.button} disabled={busy || !reason.trim() || (decision === "accepted" && (!answer.trim() || !criteria.trim()))}>
      {busy ? "正在保存审阅…" : decision === "accepted" ? "接受并生成样例" : "确认驳回"}
    </button>
    </fieldset>
  </form>;
}

function message(reason: unknown): string { return reason instanceof Error ? reason.message : "反馈请求失败，请重试。"; }
