"use client";

import { AlertTriangle, ArrowLeft, ExternalLink, FileSearch, Quote, RotateCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  EvidenceCatalogClient,
  evidenceSourceHref,
  type Artifact,
  type ArtifactDetail as ProductionArtifact,
  type EvidenceDetail as ProductionEvidence
} from "@/modules/evidence-agent";
import styles from "./EvidenceAgent.module.css";
import { artifactKindLabel } from "./artifact-presenter";
import { createDemoArtifact, demoEvidenceText } from "./demo-artifact";
import { ProductTermHelp } from "./ProductTermHelp";
import { FeedbackComposer } from "@/components/feedback/FeedbackComposer";
import { findCompletedRecordingRunForArtifact, recordingArtifactTitle } from "./runtime";

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
    setProductionEvidence(null);
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
          recordingArtifactTitle(run)
        )
      });
      setArtifactLoading(false);
      return;
    }

    const abort = new AbortController();
    void new EvidenceCatalogClient()
      .getArtifact(artifactId, { signal: abort.signal })
      .then((artifact) => setLoadedArtifact({ mode: "production", value: artifact }))
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
    if (selectedEvidence?.mode !== "production") return;
    const evidenceId = selectedEvidence.id;
    const abort = new AbortController();
    setProductionEvidence(null);
    setEvidenceError("");
    setEvidenceLoading(true);
    void new EvidenceCatalogClient()
      .getEvidence(evidenceId, { signal: abort.signal })
      .then(setProductionEvidence)
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
            <span>这份示例成果展示结论如何回到固定来源。</span>
          </div>
        </div>
      )}
      <ProductTermHelp terms={["artifact", "run", "revision"]} />
      <div className={styles.artifactLayout}>
        <article className={styles.artifactSheet}>
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
            <div className={styles.artifactBody}>{artifact.body}</div>
          </section>

          <section aria-labelledby="verified-claims">
            <h2 id="verified-claims">已核验结论</h2>
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
                          onClick={() => {
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

        <aside
          aria-busy={evidenceLoading}
          aria-label="证据详情"
          aria-live="polite"
          className={styles.inspectorPanel}
          data-testid="evidence-inspector"
        >
          <div className={styles.panelHeading}>
            <h2>证据详情</h2>
            {selectedEvidence && <span className={styles.count}>{selectedEvidence.mode === "recording" ? `版本 ${selectedEvidence.value.revision_id}` : selectedEvidence.id}</span>}
          </div>
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
        </aside>
      </div>
    </div>
  );
}

function DemoEvidenceInspector({ evidence }: { evidence: DemoEvidence }) {
  return (
    <div className={styles.inspectorContent}>
      <h3>{demoEvidenceText[evidence.chunk_id]?.title ?? `Source ${evidence.source_id}`}</h3>
      <p className={styles.excerpt}>{demoEvidenceText[evidence.chunk_id]?.excerpt ?? "Recording 中未包含证据正文。"}</p>
      <EvidenceMetadata
        chunkId={evidence.chunk_id}
        contentHash={evidence.content_hash}
        indexRevisionId={evidence.index_revision_id}
        locator={evidence.locator}
        revisionId={evidence.revision_id}
        sourceId={evidence.source_id}
      />
      <SourceLink
        chunkId={evidence.chunk_id}
        contentHash={evidence.content_hash}
        indexRevisionId={evidence.index_revision_id}
        locator={evidence.locator}
        revisionId={evidence.revision_id}
        sourceId={evidence.source_id}
        sourceType="unknown"
        demo
      />
    </div>
  );
}

function ProductionEvidenceInspector({ evidence }: { evidence: ProductionEvidence }) {
  return (
    <div className={styles.inspectorContent}>
      <h3>证据 {evidence.id} · {evidence.source_type}</h3>
      <p className={styles.excerpt}>{evidence.excerpt_preview || "该证据没有可展示的预览文本。"}</p>
      <EvidenceMetadata
        chunkId={evidence.chunk_id}
        contentHash={evidence.content_hash}
        indexRevisionId={evidence.index_revision_id}
        locator={evidence.locator}
        revisionId={evidence.revision_id}
        sourceId={evidence.source_id}
      />
      <SourceLink
        chunkId={evidence.chunk_id}
        contentHash={evidence.content_hash}
        indexRevisionId={evidence.index_revision_id}
        locator={evidence.locator}
        revisionContentHash={evidence.revision_content_hash}
        revisionId={evidence.revision_id}
        sourceId={evidence.source_id}
        sourceType={evidence.source_type}
      />
    </div>
  );
}

function EvidenceMetadata({
  chunkId,
  contentHash,
  indexRevisionId,
  locator,
  revisionId,
  sourceId
}: {
  chunkId: number;
  contentHash: string;
  indexRevisionId: number;
  locator: Record<string, unknown>;
  revisionId: number;
  sourceId: number;
}) {
  return (
    <dl>
      <dt>来源</dt><dd>{sourceId}</dd>
      <dt>版本</dt><dd>{revisionId}</dd>
      <dt>索引版本</dt><dd>{indexRevisionId}</dd>
      <dt>证据片段</dt><dd>{chunkId}</dd>
      <dt>原文位置</dt><dd>{formatLocator(locator)}</dd>
      <dt>SHA-256</dt><dd>{contentHash}</dd>
    </dl>
  );
}

function formatLocator(locator: Record<string, unknown>): string {
  return Object.entries(locator)
    .map(([key, value]) => `${key}=${Array.isArray(value) ? value.join(",") : String(value)}`)
    .join(" · ");
}

function SourceLink({
  chunkId,
  contentHash,
  indexRevisionId,
  locator,
  revisionContentHash,
  revisionId,
  sourceId,
  sourceType,
  demo = false
}: {
  chunkId: number;
  contentHash: string;
  indexRevisionId?: number;
  locator: Record<string, unknown>;
  revisionContentHash?: string;
  revisionId: number;
  sourceId: number;
  sourceType: string;
  demo?: boolean;
}) {
  return (
    <Link
      className={styles.quietAction}
      href={evidenceSourceHref({
        chunkId,
        contentHash,
        demo,
        indexRevisionId,
        locator,
        revisionContentHash,
        revisionId,
        sourceId,
        sourceType
      })}
    >
      打开固定来源 <ExternalLink aria-hidden="true" size={14} />
    </Link>
  );
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
    body: "溯知会围绕问题整理证据、保留来源版本，并在需要写入成果前请你确认。你可以从每条事实结论回到原始资料，复查它为什么成立。",
    claims: loaded.value.claims.map((claim) => ({
      id: claim.claim_id,
      text: claim.text,
      verificationStatus: "有证据支持",
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
