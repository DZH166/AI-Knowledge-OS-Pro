import { ArtifactSchema } from "@/modules/evidence-agent";
import { RECORDING_FIXTURE } from "@/modules/evidence-agent/recording-fixture";

export function createDemoArtifact(
  runId: string,
  artifactId: string,
  createdAt: string,
  title = "Evidence Agent 升级决策简报",
  options: { comparison?: boolean } = {}
) {
  const contractSource = RECORDING_FIXTURE.sources.contract;
  const runtimeSource = RECORDING_FIXTURE.sources.runtime;
  const reviewSource = RECORDING_FIXTURE.sources.review;
  return ArtifactSchema.parse({
    schema_version: 1,
    artifact_id: artifactId,
    producing_run_id: runId,
    kind: options.comparison ? "comparison" : "research_report",
    title,
    claims: [
      {
        claim_id: "claim-demo-1",
        kind: "factual",
        text: "Agent 产出的每个事实性结论都必须绑定不可变 revision、内容哈希与精确 locator。",
        evidence_refs: [
          {
            source_id: contractSource.sourceId,
            revision_id: contractSource.revisionId,
            index_revision_id: contractSource.indexRevisionId,
            chunk_id: contractSource.chunkId,
            content_hash: contractSource.contentHash,
            relation: "supports",
            locator: contractSource.locator
          }
        ]
      },
      {
        claim_id: "claim-demo-2",
        kind: "factual",
        text: "预算耗尽或证据不足是可审计的正常研究结果，而不是伪装成成功回答或系统异常。",
        evidence_refs: [
          {
            source_id: runtimeSource.sourceId,
            revision_id: runtimeSource.revisionId,
            index_revision_id: runtimeSource.indexRevisionId,
            chunk_id: runtimeSource.chunkId,
            content_hash: runtimeSource.contentHash,
            relation: "supports",
            locator: runtimeSource.locator
          }
        ]
      },
      ...(options.comparison ? [{
        claim_id: "claim-demo-3",
        kind: "factual",
        text: "人工复核可以标记证据不足的结论和证据缺口，不会悄悄改写原资料或启用策略。",
        evidence_refs: [{
          source_id: reviewSource.sourceId,
          revision_id: reviewSource.revisionId,
          index_revision_id: reviewSource.indexRevisionId,
          chunk_id: reviewSource.chunkId,
          content_hash: reviewSource.contentHash,
          relation: "supports",
          locator: reviewSource.locator
        }]
      }] : [])
    ],
    gaps: [
      {
        gap_id: "gap-demo-1",
        requirement: "用真实业务语料复测召回与引用正确率",
        reason: "当前演示只用于说明产品流程，不代表真实模型质量。",
        next_queries: ["运行 60+ 固定评测集", "对比 baseline、retrieval 与 agent 三组指标"]
      }
    ],
    created_at: createdAt
  });
}

export const demoEvidenceText: Record<number, { title: string; excerpt: string }> = {
  [RECORDING_FIXTURE.sources.contract.chunkId]: {
    title: RECORDING_FIXTURE.sources.contract.title,
    excerpt: RECORDING_FIXTURE.sources.contract.excerpt
  },
  [RECORDING_FIXTURE.sources.runtime.chunkId]: {
    title: RECORDING_FIXTURE.sources.runtime.title,
    excerpt: RECORDING_FIXTURE.sources.runtime.excerpt
  },
  [RECORDING_FIXTURE.sources.review.chunkId]: {
    title: RECORDING_FIXTURE.sources.review.title,
    excerpt: RECORDING_FIXTURE.sources.review.excerpt
  }
};
