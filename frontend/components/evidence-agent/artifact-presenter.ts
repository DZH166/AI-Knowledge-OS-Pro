const ARTIFACT_KIND_LABELS: Readonly<Record<string, string>> = {
  answer: "带引用回答",
  comparison: "对比报告",
  research_report: "研究报告"
};

export function artifactKindLabel(kind: string): string {
  return ARTIFACT_KIND_LABELS[kind] ?? kind;
}
