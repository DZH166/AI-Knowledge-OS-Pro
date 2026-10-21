import { z } from "zod";
import { resolveEvidenceApiBaseUrl } from "@/modules/evidence-agent/api-base-url";
import {
  ExportPayloadSchema, ExportSchema, FeedbackSchema, PageSchema, ReceiptSchema,
  ReviewFeedbackSchema, SubmitFeedbackSchema, type Mode, type ReviewFeedback, type SampleExport, type Status, type SubmitFeedback
} from "./contract";

type Fetch = typeof globalThis.fetch;
type Options = { baseUrl?: string; fetch?: Fetch };
const envelope = <T extends z.ZodType>(schema: T) => z.object({ success: z.literal(true), data: schema }).passthrough();

export class FeedbackIntent {
  private key = "";
  private requestId = "";
  constructor(private readonly createId: () => string = () => crypto.randomUUID()) {}
  for(payload: object): string {
    const next = JSON.stringify(payload);
    if (next !== this.key) { this.key = next; this.requestId = this.createId(); }
    return this.requestId;
  }
}

export class FeedbackClient {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;
  constructor(options: Options = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }
  submit(input: SubmitFeedback, signal?: AbortSignal) {
    return this.request("", ReceiptSchema, { ...json(SubmitFeedbackSchema.parse(input)), signal });
  }
  review(id: number, input: ReviewFeedback, signal?: AbortSignal) {
    return this.request(`/${safeId(id)}/review`, ReceiptSchema, { ...json(ReviewFeedbackSchema.parse(input)), signal });
  }
  get(id: number, signal?: AbortSignal) { return this.request(`/${safeId(id)}`, FeedbackSchema, { signal }); }
  list(filter: { status?: Status; provider_mode?: Mode; after?: number }, signal?: AbortSignal) {
    const query = new URLSearchParams({ limit: "20" });
    if (filter.status) query.set("status", filter.status);
    if (filter.provider_mode) query.set("provider_mode", filter.provider_mode);
    if (filter.after) query.set("after", safeId(filter.after));
    return this.request(`?${query}`, PageSchema, { signal });
  }
  async export(feedbackIds: number[], signal?: AbortSignal): Promise<SampleExport> {
    const ids = z.array(z.number().int().positive()).min(1).max(100).parse(feedbackIds);
    if (new Set(ids).size !== ids.length) throw new Error("导出选择不能重复。");
    const result = await this.request("/cases/export", ExportSchema, { ...json({ feedback_ids: ids }), signal });
    const bytes = new TextEncoder().encode(result.content);
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
    const payload = ExportPayloadSchema.parse(JSON.parse(result.content));
    if (hash !== result.sha256 || payload.cases.length !== result.count || result.count !== ids.length
      || payload.split !== result.split || payload.provider_mode !== result.provider_mode
      || payload.cases.some(item => !ids.includes(item.id) || item.status !== "accepted"
        || item.sample?.split !== result.split || item.provider_mode !== result.provider_mode)
      || new Set(payload.cases.map(item => item.id)).size !== ids.length) {
      throw new Error("导出内容与所选样例或内容指纹不一致，已取消下载。");
    }
    return result;
  }
  private async request<T>(path: string, schema: z.ZodType<T>, init: RequestInit): Promise<T> {
    const response = await this.fetch(`${this.baseUrl}/api/v1/feedback${path}`, { ...init, cache: "no-store",
      headers: { Accept: "application/json", ...init.headers } });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const error = z.object({ error: z.object({ user_message: z.string().optional(), message: z.string().optional() }).passthrough() }).passthrough().safeParse(payload);
      throw new Error(error.success ? (error.data.error.user_message ?? error.data.error.message ?? `请求失败（${response.status}）`)
        : `反馈请求失败（HTTP ${response.status}），请重试。`);
    }
    const parsed = envelope(schema).safeParse(payload);
    if (!parsed.success) throw new Error("反馈响应格式无法验证，没有使用演示数据替代。请刷新重试。");
    return parsed.data.data;
  }
}

function json(value: object): RequestInit { return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) }; }
function safeId(value: number): string {
  if (!Number.isSafeInteger(value) || value < 1) throw new Error("反馈标识无效。");
  return String(value);
}

export function downloadSample(value: SampleExport): void {
  const url = URL.createObjectURL(new Blob([value.content], { type: "application/json;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url; link.download = value.filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
