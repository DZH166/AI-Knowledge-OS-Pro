import styles from "./EvidenceAgent.module.css";

const PRODUCT_TERMS = {
  agent: {
    label: "Agent",
    chinese: "证据研究智能体",
    description: "在目标、证据范围与预算约束下，规划并执行研究步骤。"
  },
  rag: {
    label: "RAG",
    chinese: "检索增强生成",
    description: "先从资料中检索相关证据，再基于证据生成回答。"
  },
  run: {
    label: "Run",
    chinese: "研究运行",
    description: "一次可保存、暂停、恢复和审计的研究执行记录。"
  },
  evidenceLedger: {
    label: "Evidence Ledger",
    chinese: "证据账本",
    description: "记录支持、冲突、排除证据与未覆盖缺口的可审计清单。"
  },
  revision: {
    label: "Revision",
    chinese: "来源版本",
    description: "来源在某一时点固定且不可变的内容快照。"
  },
  proposalDigest: {
    label: "Proposal Digest",
    chinese: "提案指纹",
    description: "由待审批内容计算的摘要；内容变化会生成新值，并让旧批准失效。"
  },
  artifact: {
    label: "Artifact",
    chinese: "研究成果",
    description: "由同一 Run 生成、带结论与证据来源的可交付产物。"
  }
} as const;

export type ProductTerm = keyof typeof PRODUCT_TERMS;

export function ProductTermHelp({ terms }: { terms: readonly ProductTerm[] }) {
  return (
    <details aria-label="产品术语说明" className={styles.termHelp}>
      <summary>术语说明</summary>
      <dl className={styles.termList}>
        {terms.map((term) => {
          const copy = PRODUCT_TERMS[term];
          return (
            <div key={term}>
              <dt><span translate="no">{copy.label}</span>（{copy.chinese}）</dt>
              <dd>{copy.description}</dd>
            </div>
          );
        })}
      </dl>
    </details>
  );
}
