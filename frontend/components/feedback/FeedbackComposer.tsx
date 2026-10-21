"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FeedbackClient, FeedbackIntent } from "@/modules/feedback/client";
import { IssueSchema, issueLabel, modeLabel, type Feedback, type Issue } from "@/modules/feedback/contract";
import styles from "./Feedback.module.css";

export function FeedbackComposer({ artifactId, claim, onClose }: {
  artifactId: string; claim: { id: string; text: string } | null; onClose: () => void;
}) {
  const client = useMemo(() => new FeedbackClient(), []);
  const identity = useRef(new FeedbackIntent());
  const pending = useRef(false);
  const request = useRef<AbortController | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const [issue, setIssue] = useState<Issue>("incorrect_answer");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Feedback | null>(null);
  useEffect(() => { input.current?.focus(); return () => request.current?.abort(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || !comment.trim()) return;
    pending.current = true; setBusy(true); setError("");
    const abort = new AbortController(); request.current = abort;
    const intent = { artifact_id: artifactId, claim_id: claim?.id ?? null, issue, comment: comment.trim() };
    try {
      const result = await client.submit({ ...intent, request_id: identity.current.for(intent) }, abort.signal);
      if (!abort.signal.aborted) setSaved(result.feedback);
    } catch (reason) {
      if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : "反馈保存失败。");
    } finally {
      pending.current = false;
      if (!abort.signal.aborted) setBusy(false);
    }
  }

  return <section className={styles.panel} aria-label="成果反馈" data-testid="feedback-composer">
    <h3>反馈{claim ? "这条结论" : "这份成果"}</h3>
    {claim && <p className={styles.text}>{claim.text}</p>}
    <p className={styles.muted}>保存当时的成果与证据，不修改原答案。你的反馈需要人工审阅，不会自动成为知识库内容。</p>
    {saved ? <div>
      <p role="status">反馈 #{saved.id} 已保存 · {modeLabel[saved.provider_mode]} · 待人工审阅</p>
      <div className={styles.row}><Link className={styles.button} href={`/evaluations/feedback?id=${saved.id}`}>查看并审阅反馈</Link>
        <button className={styles.quiet} type="button" onClick={onClose}>关闭反馈</button></div>
    </div> : <form className={styles.form} onSubmit={submit}>
      <label className={styles.field}>问题类型<select value={issue} disabled={busy} onChange={event => setIssue(IssueSchema.parse(event.target.value))}>
        {IssueSchema.options.map(value => <option key={value} value={value}>{issueLabel[value]}</option>)}
      </select></label>
      <label className={styles.field}>问题说明<textarea ref={input} value={comment} maxLength={2000} required disabled={busy}
        onChange={event => setComment(event.target.value)} placeholder="例如：这条结论遗漏了哪些条件，或哪处引用不支持它。不要填写密钥等敏感信息。" /></label>
      {error && <p role="alert" className={styles.error}>{error}</p>}
      <div className={styles.row}><button className={styles.button} disabled={busy || !comment.trim()}>{busy ? "正在保存…" : "保存反馈"}</button>
        <button className={styles.quiet} disabled={busy} type="button" onClick={onClose}>取消反馈</button></div>
    </form>}
  </section>;
}
