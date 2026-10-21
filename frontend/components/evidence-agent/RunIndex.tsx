"use client";

import { AlertTriangle, ArrowRight, CircleGauge, Plus, RotateCw, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EvidenceCatalogClient, type RunView } from "@/modules/evidence-agent";
import styles from "./EvidenceAgent.module.css";
import { listStoredRuns } from "./runtime";
import { runStatusLabel } from "./run-presenter";

type DisplayRun = { view: RunView; mode: "production" | "recording"; createdAt: string | null };

export function RunIndex() {
  const [runs, setRuns] = useState<DisplayRun[]>([]);
  const [recording, setRecording] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const useRecording = new URLSearchParams(window.location.search).get("demo") === "1";
    setRecording(useRecording);
    try {
      if (useRecording) {
        setRuns(listStoredRuns().filter((run) => run.mode === "recording").map((run) => ({ view: run.receipt.view, mode: run.mode, createdAt: run.created_at })));
      } else {
        const catalog = await new EvidenceCatalogClient().listRuns();
        setRuns(catalog.items.map((view) => ({ view, mode: "production", createdAt: null })));
      }
    } catch (reason) {
      setRuns([]);
      setError(reason instanceof Error ? reason.message : "无法加载生产 Run 列表。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>研究记录</p>
          <h1>运行记录</h1>
          <p className={styles.lead}>回到未完成审批、复查证据轨迹，或打开已经发布的研究成果。</p>
        </div>
        <Link className={styles.primaryAction} href={`/workbench${recording ? "?demo=1" : ""}`}>
          <Plus aria-hidden="true" size={17} /> 新研究
        </Link>
      </header>

      {recording && (
        <div className={styles.demoBanner} role="status">
          <ShieldAlert aria-hidden="true" size={18} />
          <div>
            <strong>演示记录 · 本地保存</strong>
            <span>当前列表只读取此浏览器中的示例研究，不代表生产数据。</span>
          </div>
        </div>
      )}

      {loading ? (
        <div aria-live="polite" className={styles.loadingState} role="status"><span>正在加载{recording ? "本地演示" : "生产"} Run…</span></div>
      ) : error ? (
        <section className={styles.emptyCard} role="alert">
          <div>
            <AlertTriangle aria-hidden="true" size={30} />
            <h2>生产 Run 列表加载失败</h2>
            <p>{error} 请确认 API 服务可用后重试；系统不会用演示数据静默替代。</p>
            <button className={styles.primaryAction} onClick={() => void load()} type="button">
              <RotateCw aria-hidden="true" size={16} /> 重新加载
            </button>
          </div>
        </section>
      ) : runs.length ? (
        <section aria-label={recording ? "本地演示研究" : "生产运行"} className={styles.indexGrid}>
          {runs.map((run) => (
            <article className={styles.indexCard} key={run.view.id}>
              <div className={styles.panelHeading}>
                <span className={styles.statusBadge} data-attention={run.view.status.startsWith("awaiting_")}>
                  {runStatusLabel(run.view.status)}
                </span>
                <span className={styles.count}>{run.mode === "recording" ? "演示" : "生产数据"}</span>
              </div>
              <h2>{run.view.goal}</h2>
              <p translate="no">{run.view.id}</p>
              <div className={styles.indexCardFooter}>
                <span className={styles.count}>{run.createdAt ? formatDate(run.createdAt) : `事件位置 ${number(run.view.last_event_cursor)}`}</span>
                <Link className={styles.quietAction} href={`/runs/${encodeURIComponent(run.view.id)}${run.mode === "recording" ? "?demo=1" : ""}`}>
                  打开 Run <ArrowRight aria-hidden="true" size={14} />
                </Link>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className={styles.emptyCard}>
          <div>
            <CircleGauge aria-hidden="true" size={30} />
            <h2>{recording ? "还没有本地演示 Run" : "生产环境还没有 Run"}</h2>
            <p>{recording ? "回到研究工作台，开始一项示例研究。" : "从研究工作台提交目标后，运行记录会出现在这里。"}</p>
            <Link className={styles.primaryAction} href={`/workbench${recording ? "?demo=1" : ""}`}>
              开始第一项研究
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}

const dateFormatter = new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" });
const numberFormatter = new Intl.NumberFormat("zh-CN");
function formatDate(value: string): string { return dateFormatter.format(new Date(value)); }
function number(value: number): string { return numberFormatter.format(value); }
