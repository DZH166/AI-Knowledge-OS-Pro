import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { evidenceSourceHref, type EvidenceDetail as PersistedEvidence } from "@/modules/evidence-agent";
import styles from "./EvidenceAgent.module.css";

export type EvidenceDetailProps = {
  title: string; excerpt: string;
  reference: Pick<PersistedEvidence, "source_id" | "revision_id" | "index_revision_id" | "chunk_id" | "content_hash" | "locator">;
  sourceType?: string; revisionContentHash?: string; demo?: boolean; relationLabel?: string; reason?: string;
};

export function EvidenceDetail({ title, excerpt, reference, sourceType = "unknown", revisionContentHash, demo = false,
  relationLabel, reason }: EvidenceDetailProps) {
  return <div className={styles.inspectorContent}>
    <h3>{title}</h3>
    <p className={styles.excerpt}>{excerpt || "该证据没有可展示的预览文本。"}</p>
    <dl>
      <dt>来源</dt><dd>{reference.source_id}</dd>
      <dt>版本</dt><dd>{reference.revision_id}</dd>
      <dt>索引版本</dt><dd>{reference.index_revision_id}</dd>
      <dt>证据片段</dt><dd>{reference.chunk_id}</dd>
      <dt>原文位置</dt><dd>{Object.entries(reference.locator).map(([key, value]) =>
        `${key}=${Array.isArray(value) ? value.join(",") : String(value)}`).join(" · ")}</dd>
      <dt>SHA-256</dt><dd>{reference.content_hash}</dd>
      {relationLabel && <><dt>证据关系</dt><dd>{relationLabel}</dd></>}
      {reason && <><dt>判定原因</dt><dd>{reason}</dd></>}
    </dl>
    <Link className={styles.quietAction} href={evidenceSourceHref({ sourceId: reference.source_id,
      revisionId: reference.revision_id, indexRevisionId: reference.index_revision_id, chunkId: reference.chunk_id,
      contentHash: reference.content_hash, locator: reference.locator, sourceType, revisionContentHash, demo })}>
      打开固定来源 <ExternalLink aria-hidden="true" size={14} />
    </Link>
  </div>;
}
