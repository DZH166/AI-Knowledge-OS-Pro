export type MetricDisplay = "decimal" | "percentage";

export type EvaluationMetricMetadata = {
  label: string;
  display: MetricDisplay;
};

export const EVALUATION_METRICS: Readonly<Record<string, EvaluationMetricMetadata>> = {
  case_pass_rate: { label: "案例通过率", display: "percentage" },
  mean_source_recall: { label: "平均来源召回率", display: "percentage" },
  citation_completeness: { label: "引用完整率", display: "percentage" },
  immutable_evidence_identity_rate: { label: "固定证据身份完整率", display: "percentage" },
  unauthorized_action_rate: { label: "未授权操作率", display: "percentage" },
  recovery_scenario_pass_rate: { label: "恢复场景通过率", display: "percentage" },
  multi_hop_agent_lift_pp: { label: "多步研究提升", display: "decimal" },
  fusion_recall_at_10: { label: "混合检索前 10 条召回率", display: "percentage" },
  fusion_ndcg_at_10: { label: "混合检索排序质量", display: "percentage" }
};
