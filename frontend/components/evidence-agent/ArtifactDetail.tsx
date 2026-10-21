"use client";

import { AlertTriangle, ArrowLeft, ExternalLink, FileSearch, Quote, RotateCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  EvidenceCatalogClient,
  type Artifact,
  type ArtifactDetail as ProductionArtifact,
  type EvidenceDetail as ProductionEvidence
} from "@/modules/evidence-agent";
import styles from "./EvidenceAgent.module.css";
import { artifactKindLabel } from "./artifact-presenter";
import { createDemoArtifact, demoEvidenceText } from "./demo-artifact";
import { isRecordedComparisonInput } from "@/modules/evidence-agent/recording-fixture";
import { ProductTermHelp } from "./ProductTermHelp";
import { FeedbackComposer } from "@/components/feedback/FeedbackComposer";
import { findCompletedRecordingRunForArtifact, recordingArtifactTitle } from "./runtime";
import { ArtifactBody } from "./ArtifactBody";
import presentationStyles from "./EvidencePresentation.module.css";
import { EvidenceDetail } from "./EvidenceDetail";
import { EvidencePanel } from "./EvidencePanel";

type DemoEvidence = Artifact["claims"][number]["evidence_refs"][number];
type LoadedArtifact =
  | { mode: "recording"; value: Artifact }
  | { mode: "production"; value: ProductionArtifact };
type SelectedEvidence =
  | { mode: "recording"; id: string; value: DemoEvidence }
  | { mode: "production"; id: string };
type DisplayReference = { id: string; label: string; demoEvidence?: DemoEvidence };
type DisplayClaim = { id: string; text: string; verificationStatus: string; references: DisplayReference[] };

const ARTIFACT_STATUS_LABELS: Record<string, string> = { final: "已完成", published: "已发布" };
const CLAIM_VERIFICATION_LABELS: Record<string, string> = {
  contradicted: "存在冲突",
  supported: "有证据支持",
  unsupported: "证据不足"
};

export function ArtifactDetail() {
  const params = useParams<{ artifactId: string }>();
  const artifactId = params.artifactId;
  const [loadedArtifact, setLoadedArtifact] = useState<LoadedArtifact | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(true);
  const [artifactError, setArtifactError] = useState("");
  const [artifactReload, setArtifactReload] = useState(0);
  const [recording, setRecording] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<SelectedEvidence | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const citationTriggerRef = useRef<HTMLElement | null>(null);
  const [productionEvidence, setProductionEvidence] = useState<ProductionEvidence | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");
  const [evidenceReload, setEvidenceReload] = useState(0);
  const [feedbackTarget, setFeedbackTarget] = useState<{ id: string; text: string } | null | undefined>(undefined);

  useEffect(() => {
    const useRecording = new URLSearchParams(window.location.search).get("demo") === "1";
    setRecording(useRecording);
    setLoadedArtifact(null);
    setSelectedEvidence(null);
    setEvidenceOpen(false);
    setProductionEvidence(null);
    setEvidenceLoading(false);
    setEvidenceError("");
    setArtifactError("");
    setArtifactLoading(true);
    setFeedbackTarget(undefined);

    if (useRecording) {
      const run = findCompletedRecordingRunForArtifact(artifactId);
      if (!run) {
        setArtifactError("该 Recording Artifact 不存在，或对应 Run 尚未完成发布。");
        setArtifactLoading(false);
        return;
      }
      setLoadedArtifact({
        mode: "recording",
        value: createDemoArtifact(
          run.receipt.run_id,
          artifactId,
          run.created_at,
          recordingArtifactTitle(run),
          { comparison: isRecordedComparisonInput(run.input) }
        )
      });
      setArtifactLoading(false);
      return;
    }

    const abort = new AbortController();
    void new EvidenceCatalogClient()
      .getArtifact(artifactId, { signal: abort.signal })
      .then((artifact) => { if (!abort.signal.aborted) setLoadedArtifact({ mode: "production", value: artifact }); })
      .catch((reason) => {
        if (!abort.signal.aborted) {
          setArtifactError(reason instanceof Error ? reason.message : "无法加载 Artifact。");
        }
      })
      .finally(() => {
        if (!abort.signal.aborted) setArtifactLoading(false);
      });
    return () => abort.abort();
  }, [artifactId, artifactReload]);

  useEffect(() => {
    if (selectedEvidence?.mode !== "production") { setEvidenceLoading(false); return; }
    const evidenceId = selectedEvidence.id;
    const abort = new AbortController();
    setProductionEvidence(null);
    setEvidenceError("");
    setEvidenceLoading(true);
    void new EvidenceCatalogClient()
      .getEvidence(evidenceId, { signal: abort.signal })
      .then((evidence) => { if (!abort.signal.aborted) setProductionEvidence(evidence); })
      .catch((reason) => {
        if (!abort.signal.aborted) {
          setEvidenceError(reason instanceof Error ? reason.message : "无法加载 Evidence。");
        }
      })
      .finally(() => {
        if (!abort.signal.aborted) setEvidenceLoading(false);
      });
    return () => abort.abort();
  }, [evidenceReload, selectedEvidence]);

  if (artifactLoading) {
    return <div aria-live="polite" className={styles.loadingState} role="status"><span>正在验证 Artifact 契约…</span></div>;
  }

  if (artifactError || !loadedArtifact) {
    return (
      <section className={styles.emptyCard} role="alert">
        <div>
          <AlertTriangle aria-hidden="true" size={30} />
          <h1>无法加载研究成果</h1>
          <p>{artifactError || "Artifact 响应为空。"} 系统不会用演示数据替代生产结果。</p>
          <div className={styles.actionRow}>
            <button className={styles.primaryAction} onClick={() => setArtifactReload((value) => value + 1)} type="button">
              <RotateCw aria-hidden="true" size={16} /> 重新加载
            </button>
            <Link className={styles.secondaryAction} href={`/artifacts${recording ? "?demo=1" : ""}`}>
              返回成果列表
            </Link>
          </div>
        </div>
      </section>
    );
  }

  const artifact = presentArtifact(loadedArtifact);

  return (
    <div className={styles.page}>
      {recording && (
        <div className={styles.demoBanner} role="status">
          <FileSearch aria-hidden="true" size={18} />
          <div>
            <strong>演示模式 · 非真实执行</strong>
            <span>固定录制样例，不根据输入的问题生成结论，也不代表真实模型质量。</span>
          </div>
        </div>
      )}
      <ProductTermHelp terms={["artifact", "run", "revision"]} />
      <div className={styles.artifactLayout}>
        <article className={`${styles.artifactSheet} ${presentationStyles.sheet}`}>
          <header>
            <p className={styles.kicker}>{recording ? "演示成果" : "已核验成果 · 生产数据"}</p>
            <h1>{artifact.title}</h1>
            <p className={styles.lead}>{artifact.meta} · {artifact.claims.length} 条事实结论</p>
            <div className={styles.actionRow}>
              <Link className={styles.quietAction} href={`/runs/${encodeURIComponent(artifact.producingRunId)}${recording ? "?demo=1" : ""}`}>
                查看研究过程 <ExternalLink aria-hidden="true" size={14} />
              </Link>
              {!recording && <button className={styles.quietAction} type="button" onClick={() => setFeedbackTarget(null)}>反馈这份成果</button>}
            </div>
          </header>

          <section aria-labelledby="artifact-body">
            <h2 id="artifact-body">研究正文</h2>
            <ArtifactBody markdown={artifact.body} />
          </section>

          <section aria-labelledby="verified-claims">
            <h2 id="verified-claims">{recording ? "录制样例结论" : "已核验结论"}</h2>
            {artifact.claims.length ? (
              <div className={styles.claimList}>
                {artifact.claims.map((claim, claimIndex) => (
                  <article className={styles.claim} key={claim.id}>
                    <div className={styles.panelHeading}>
                      <span className={styles.statusBadge}>{claim.verificationStatus}</span>
                      <span className={styles.count}>结论 {claimIndex + 1}</span>
                    </div>
                    <p>{claim.text}</p>
                    <div className={styles.actionRow}>
                      {claim.references.map((reference, referenceIndex) => (
                        <button
                          aria-label={`查看证据 ${claimIndex + 1}.${referenceIndex + 1}`}
                          aria-pressed={selectedEvidence?.id === reference.id}
                          className={styles.citationButton}
                          key={reference.id}
                          onClick={(event) => {
                            citationTriggerRef.current = event.currentTarget;
                            setEvidenceOpen(true);
                            setEvidenceError("");
                            setProductionEvidence(null);
                            setEvidenceLoading(!reference.demoEvidence);
                            setSelectedEvidence(reference.demoEvidence
                              ? { mode: "recording", id: reference.id, value: reference.demoEvidence }
                              : { mode: "production", id: reference.id });
                          }}
                          type="button"
                        >
                          <Quote aria-hidden="true" size={13} /> [{claimIndex + 1}.{referenceIndex + 1}] {reference.label}
                        </button>
                      ))}
                      {!recording && <button className={styles.quietAction} type="button" onClick={() => setFeedbackTarget({ id: claim.id, text: claim.text })}>
                        反馈这条结论
                      </button>}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className={styles.inspectorEmpty}>该成果没有事实性 claim；这可能是正常的证据缺口报告。</p>
            )}
          </section>

          {feedbackTarget !== undefined && !recording && <FeedbackComposer key={`${artifactId}:${feedbackTarget?.id ?? "whole"}`}
            artifactId={artifactId} claim={feedbackTarget} onClose={() => setFeedbackTarget(undefined)} />}

          {artifact.gaps.length > 0 && (
            <section aria-labelledby="evidence-gaps">
              <h2 id="evidence-gaps">证据缺口与下一步</h2>
              <ul className={styles.gapList}>
                {artifact.gaps.map((gap) => (
                  <li key={gap.id}><strong>{gap.requirement}</strong>：{gap.reason} 下一步：{gap.nextQueries.join("；")}。</li>
                ))}
              </ul>
            </section>
          )}

          <Link className={styles.secondaryAction} href={`/artifacts${recording ? "?demo=1" : ""}`}>
            <ArrowLeft aria-hidden="true" size={16} /> 返回成果列表
          </Link>
        </article>

        <EvidencePanel busy={evidenceLoading} open={evidenceOpen} returnFocusRef={citationTriggerRef}
          onClose={() => { setEvidenceOpen(false); setSelectedEvidence(null); setEvidenceLoading(false); setEvidenceError(""); setProductionEvidence(null); }}
          className={styles.inspectorPanel}
        >
          {selectedEvidence && <span className={styles.count}>{selectedEvidence.mode === "recording" ? `版本 ${selectedEvidence.value.revision_id}` : selectedEvidence.id}</span>}
          {!selectedEvidence ? (
            <div className={styles.inspectorEmpty}>选择任一引用，查看它绑定的 revision、chunk、hash 与来源定位。</div>
          ) : selectedEvidence.mode === "recording" ? (
            <DemoEvidenceInspector evidence={selectedEvidence.value} />
          ) : evidenceLoading ? (
            <div className={styles.inspectorEmpty} role="status">正在验证 Evidence 契约…</div>
          ) : evidenceError ? (
            <div className={styles.inspectorEmpty} role="alert">
              <div>
                <strong>Evidence 加载失败</strong>
                <p>{evidenceError}</p>
                <button className={styles.quietAction} onClick={() => setEvidenceReload((value) => value + 1)} type="button">
                  <RotateCw aria-hidden="true" size={14} /> 重试证据
                </button>
              </div>
            </div>
          ) : productionEvidence ? (
            <ProductionEvidenceInspector evidence={productionEvidence} />
          ) : (
            <div className={styles.inspectorEmpty}>Evidence 响应为空。</div>
          )}
        </EvidencePanel>
      </div>
    </div>
  );
}

function DemoEvidenceInspector({ evidence }: { evidence: DemoEvidence }) {
  return <EvidenceDetail title={demoEvidenceText[evidence.chunk_id]?.title ?? `来源 ${evidence.source_id}`}
    excerpt={demoEvidenceText[evidence.chunk_id]?.excerpt ?? "录制样例中未包含证据正文。"} reference={evidence} demo />;
}

function ProductionEvidenceInspector({ evidence }: { evidence: ProductionEvidence }) {
  return <EvidenceDetail title={`证据 ${evidence.id} · ${evidence.source_type}`} excerpt={evidence.excerpt_preview}
    reference={evidence} sourceType={evidence.source_type} revisionContentHash={evidence.revision_content_hash} />;
}

function presentArtifact(loaded: LoadedArtifact): {
  title: string;
  producingRunId: string;
  meta: string;
  body: string;
  claims: DisplayClaim[];
  gaps: Array<{ id: string; requirement: string; reason: string; nextQueries: string[] }>;
} {
  if (loaded.mode === "production") {
    return {
      title: loaded.value.title,
      producingRunId: loaded.value.producing_run_id,
      meta: `${artifactKindLabel(loaded.value.kind)} · ${artifactStatusLabel(loaded.value.status)}`,
      body: loaded.value.body_markdown,
      claims: loaded.value.claims.map((claim) => ({
        id: claim.id,
        text: claim.text,
        verificationStatus: claimVerificationLabel(claim.verification_status),
        references: claim.evidence_ids.map((evidenceId) => ({ id: evidenceId, label: `证据 ${evidenceId}` }))
      })),
      gaps: []
    };
  }

  return {
    title: loaded.value.title,
    producingRunId: loaded.value.producing_run_id,
    meta: `${formatDate(loaded.value.created_at)} · ${artifactKindLabel(loaded.value.kind)}`,
    body: loaded.value.kind === "comparison"
      ? "这是一份固定的三资料对比录制样例，不会根据你输入的问题实时生成答案。下方三条示例结论各自绑定一份来源；可以打开引用练习核对原文。录制样例不会保存反馈；真实研究需要配置模型并上传自己的资料。"
      : "溯知会围绕问题整理证据、保留来源版本，并在需要写入成果前请你确认。你可以从每条事实结论回到原始资料，复查它为什么成立。",
    claims: loaded.value.claims.map((claim) => ({
      id: claim.claim_id,
      text: claim.text,
      verificationStatus: "录制样例引用",
      references: claim.evidence_refs.map((reference) => ({
        id: `demo-${claim.claim_id}-${reference.revision_id}-${reference.chunk_id}`,
        label: `来源版本 ${reference.revision_id}`,
        demoEvidence: reference
      }))
    })),
    gaps: loaded.value.gaps.map((gap) => ({
      id: gap.gap_id,
      requirement: gap.requirement,
      reason: gap.reason,
      nextQueries: gap.next_queries
    }))
  };
}

function artifactStatusLabel(status: string): string {
  return ARTIFACT_STATUS_LABELS[status] ?? status;
}

function claimVerificationLabel(status: string): string {
  return CLAIM_VERIFICATION_LABELS[status] ?? status;
}

const dateFormatter = new Intl.DateTimeFormat("zh-CN", { dateStyle: "long", timeStyle: "short" });
function formatDate(value: string): string {
  return dateFormatter.format(new Date(value));
}
