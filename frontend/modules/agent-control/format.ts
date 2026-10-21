import { EVALUATION_METRICS } from "./metric-catalog";

const integerFormatter = new Intl.NumberFormat("zh-CN");
const percentageFormatter = new Intl.NumberFormat("zh-CN", {
  style: "percent",
  maximumFractionDigits: 2
});
const decimalFormatter = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 4,
  signDisplay: "auto"
});
const shortDateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "short"
});
const preciseDateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "medium"
});

export function formatNumber(value: number): string {
  return integerFormatter.format(value);
}

export function formatPercentage(value: number | null): string {
  return value === null ? "未记录" : percentageFormatter.format(value);
}

export function formatDateTime(value: string, options: { includeSeconds?: boolean } = {}): string {
  const formatter = options.includeSeconds ? preciseDateTimeFormatter : shortDateTimeFormatter;
  return formatter.format(new Date(value));
}

export function formatDuration(milliseconds: number): string {
  return milliseconds < 1_000
    ? `${formatNumber(milliseconds)} ms`
    : `${decimalFormatter.format(milliseconds / 1_000)} s`;
}

export function formatMetricValue(metric: string, value: number): string {
  return EVALUATION_METRICS[metric]?.display === "percentage"
    ? percentageFormatter.format(value)
    : decimalFormatter.format(value);
}
