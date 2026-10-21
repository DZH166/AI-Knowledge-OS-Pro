"use client";

import { AlertTriangle, ArrowRight, FileCheck2, RotateCw, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  EvidenceCatalogClient,
  artifactCatalogFiltersFromSearch
} from "@/modules/evidence-agent/catalog-client";
import type { ArtifactSummary } from "@/modules/evidence-agent/contract";
import styles from "./EvidenceAgent.module.css";
import { createDemoArtifact } from "./demo-artifact";
import { listStoredRuns } from "./runtime";

type DisplayArtifact = ArtifactSummary & { mode: "production" | "recording" };

export function ArtifactIndex() {
  const [artifacts, setArtifacts] = useState<DisplayArtifact[]>([]);
  const [recording, setRecording] = useState(false);
  const [sourceId, setSourceId] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const search = window.location.search;
    const query = new URLSearchParams(search);
    const filters = artifactCatalogFiltersFromSearch(search);
    const useRecording = query.get("demo") === "1";
    setRecording(useRecording);
    setSourceId(filters.sourceId);
    try {
      if (useRecording) {
        const recordingArtifacts = listStoredRuns().flatMap((run) => {
          const artifactId = run.receipt.view.final_artifact_id;
          if (run.mode !== "recording" || run.receipt.view.status !== "completed" || !artifactId) return [];
          const artifact = createDemoArtifact(run.receipt.run_id, artifactId, run.created_at);
          if (filters.sourceId && !artifact.claims.some((claim) =>
            claim.evidence_refs.some((reference) => reference.source_id === filters.sourceId)
          )) return [];
          return [{
            id: artifact.artifact_id,
            producing_run_id: artifact.producing_run_id,
            kind: artifact.kind,
            title: artifact.title,
            status: "published",
            mode: "recording" as const
          }];
        });
        setArtifacts(recordingArtifacts);
      } else {
        const catalog = await new EvidenceCatalogClient().listArtifacts(filters);
        setArtifacts(catalog.items.map((item) => ({ ...item, mode: "production" })));
      }
    } catch (reason) {
      setArtifacts([]);
      setError(reason instanceof Error ? reason.message : "无法加载生产 Artifact 列表。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>{sourceId ? `Artifacts · Source ${sourceId}` : "Artifacts"}</p>
          <h1>{sourceId ? "来源派生成果" : "研究成果"}</h1>
          <p className={styles.lead}>
            {sourceId
              ? `只呈现引用 Source ${sourceId} 证据的交付物；筛选沿 claim-evidence provenance 反向解析。`
              : "只呈现经过 claim-evidence 校验的交付物；每条事实结论都能回到固定 revision 与 locator。"}
          </p>
        </div>
      </header>

      {recording && (
        <div className={styles.demoBanner} role="status">
          <ShieldAlert aria-hidden="true" size={18} />
          <div>
            <strong>Recording Demo · 本地成果</strong>
            <span>当前列表只显示本浏览器演示流程发布的确定性 Artifact。</span>
          </div>
        </div>
      )}

      {loading ? (
        <div aria-live="polite" className={styles.loadingState} role="status"><span>正在加载{recording ? "本地演示" : "生产"}成果…</span></div>
      ) : error ? (
        <section className={styles.emptyCard} role="alert">
          <div>
            <AlertTriangle aria-hidden="true" size={30} />
            <h2>生产 Artifact 列表加载失败</h2>
            <p>{error} 请确认 API 服务可用后重试；系统不会回退到演示成果。</p>
            <button className={styles.primaryAction} onClick={() => void load()} type="button">
              <RotateCw aria-hidden="true" size={16} /> 重新加载
            </button>
          </div>
        </section>
      ) : artifacts.length ? (
        <section aria-label={recording ? "本地 Recording Demo 成果" : sourceId ? `Source ${sourceId} 的生产成果` : "生产成果"} className={styles.indexGrid}>
          {artifacts.map((artifact) => (
            <article className={styles.indexCard} key={artifact.id}>
              <div className={styles.panelHeading}>
                <span className={styles.statusBadge}>{artifact.status === "published" ? "已发布" : artifact.status}</span>
                <span className={styles.count}>{artifact.mode === "recording" ? "Recording Demo" : "Production API"}</span>
              </div>
              <h2>{artifact.title}</h2>
              <p>{artifact.kind} · Run {artifact.producing_run_id}</p>
              <div className={styles.indexCardFooter}>
                <span className={styles.count}>claim-evidence artifact</span>
                <Link className={styles.quietAction} href={`/artifacts/${encodeURIComponent(artifact.id)}${artifact.mode === "recording" ? "?demo=1" : ""}`}>
                  打开成果 <ArrowRight aria-hidden="true" size={14} />
                </Link>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className={styles.emptyCard}>
          <div>
            <FileCheck2 aria-hidden="true" size={30} />
            <h2>{recording ? "还没有本地演示成果" : sourceId ? `Source ${sourceId} 还没有派生成果` : "生产环境还没有已发布成果"}</h2>
            <p>{recording ? "完成 Recording Demo 的审批后，确定性 Artifact 会出现在这里。" : sourceId ? "当研究结论引用该来源的证据后，Artifact 会自动出现在这里。" : "研究完成或以证据不足正常结束后，服务端 Artifact 会出现在这里。"}</p>
            <Link className={styles.primaryAction} href={`/workbench${recording ? "?demo=1" : ""}`}>开始研究</Link>
          </div>
        </section>
      )}
    </div>
  );
}
