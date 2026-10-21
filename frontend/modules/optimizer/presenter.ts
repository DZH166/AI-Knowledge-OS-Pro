export const OPTIMIZER_ACTIONS = {
  start: { label: "启动实验" },
  "next-round": { label: "下一轮" },
  cancel: { label: "取消实验" },
  fail: { label: "终止为失败" },
  retry: { label: "重试失败 Trial" },
  "convert-draft": { label: "转为草稿" },
  recover: { label: "恢复过期任务" }
} as const;

export type WorkbenchAction = keyof typeof OPTIMIZER_ACTIONS;

const OBJECTIVE_LABELS: Record<string, string> = {
  quality_first: "质量优先",
  balanced: "质量与成本平衡",
  cost_first: "成本优先"
};

const STATUS_LABELS: Record<string, string> = {
  pending: "等待",
  running: "运行中",
  completing: "写入结果",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败"
};

export function actionLabel(action: WorkbenchAction | string): string {
  return action in OPTIMIZER_ACTIONS
    ? OPTIMIZER_ACTIONS[action as WorkbenchAction].label
    : "未知操作";
}

export function objectiveLabel(value: string): string {
  return OBJECTIVE_LABELS[value] ?? value;
}

export function statusLabel(value: string): string {
  return STATUS_LABELS[value] ?? value;
}

export function templateLabel(value: string): string {
  return objectiveLabel(value);
}

export function templateDescription(value: string): string {
  if (value === "quality_first") return "扩大检索窗口，优先提高证据覆盖与任务质量。";
  if (value === "cost_first") return "收紧检索窗口与延迟，在硬门通过的前提下降低成本。";
  return "围绕当前配置平衡证据质量、延迟与检索规模。";
}

