import { z } from "zod";

import { resolveEvidenceApiBaseUrl } from "@/modules/evidence-agent/api-base-url";
import {
  CategoryComparisonSchema,
  ConvertReceiptSchema,
  CreateStudyFromTemplateInputSchema,
  DiffReceiptSchema,
  ExportComparisonReceiptSchema,
  RecommendationBundleSchema,
  StudyCatalogSchema,
  StudyEventCatalogSchema,
  StudyMutationReceiptSchema,
  StudyOverviewSchema,
  StudyTemplateCatalogSchema,
  type CategoryComparison,
  type CreateStudyFromTemplateInput,
  type DiffReceipt,
  type ExportComparisonReceipt,
  type RecommendationBundle,
  type StudyEventCatalog,
  type StudyOverview,
  type StudySummary,
  type StudyTemplate
} from "./contract";


type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type ClientOptions = { baseUrl?: string; fetch?: Fetch };

const successEnvelope = <T extends z.ZodType>(data: T) =>
  z.object({ success: z.literal(true), data, error: z.null(), request_id: z.string().min(1) }).passthrough();

const NextRoundReceiptSchema = z.object({
  study_id: z.string(), round_no: z.number().int().positive(),
  created: z.number().int().nonnegative(), replayed: z.boolean()
}).strict();
const RecoverReceiptSchema = z.object({ recovered_trials: z.number().int().nonnegative() }).strict();
const RetryReceiptSchema = z.object({ trial_id: z.string(), status: z.literal("pending") }).strict();
const TerminalReceiptSchema = z.object({
  study_id: z.string(), status: z.enum(["cancelled", "failed", "completed"]), cancelled: z.boolean()
}).strict();

export class OptimizerTransportError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: unknown
  ) {
    super(message);
    this.name = "OptimizerTransportError";
  }
}

export class OptimizerClient {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async listTemplates(signal?: AbortSignal): Promise<StudyTemplate[]> {
    return (await this.request("/api/v1/optimizer/study-templates", StudyTemplateCatalogSchema, { signal })).items;
  }

  async listStudies(signal?: AbortSignal): Promise<StudySummary[]> {
    return (await this.request("/api/v1/optimizer/studies?limit=100", StudyCatalogSchema, { signal })).items;
  }

  createFromTemplate(input: CreateStudyFromTemplateInput) {
    return this.request(
      "/api/v1/optimizer/studies/from-template",
      StudyMutationReceiptSchema,
      jsonRequest("POST", CreateStudyFromTemplateInputSchema.parse(input))
    );
  }

  getOverview(studyId: string, signal?: AbortSignal): Promise<StudyOverview> {
    return this.request(`/api/v1/optimizer/studies/${safeId(studyId)}/overview`, StudyOverviewSchema, { signal });
  }

  async getEvents(studyId: string, signal?: AbortSignal): Promise<StudyEventCatalog> {
    const items: StudyEventCatalog["items"] = [];
    let after = "";
    for (let page = 0; page < 10; page += 1) {
      const result = await this.request(
        `/api/v1/optimizer/studies/${safeId(studyId)}/events?limit=200${after ? `&after=${safeId(after)}` : ""}`,
        StudyEventCatalogSchema, { signal }
      );
      items.push(...result.items);
      if (result.items.length < 200) return { study_id: result.study_id, items };
      const cursor = result.items.at(-1)!.id;
      if (cursor === after) throw new Error("事件游标未推进，请刷新后重试。");
      after = cursor;
    }
    throw new Error("实验事件超过当前读取上限，请缩小实验规模后重试。");
  }

  getRecommendation(studyId: string, signal?: AbortSignal): Promise<RecommendationBundle> {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/recommendation`,
      RecommendationBundleSchema,
      { signal }
    );
  }

  getDiff(studyId: string, trialId: string, signal?: AbortSignal): Promise<DiffReceipt> {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/trials/${safeId(trialId)}/diff`,
      DiffReceiptSchema,
      { signal }
    );
  }

  getCategories(studyId: string, trialId: string, signal?: AbortSignal): Promise<CategoryComparison> {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/trials/${safeId(trialId)}/categories`,
      CategoryComparisonSchema,
      { signal }
    );
  }

  startStudy(studyId: string) {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/start`,
      StudyMutationReceiptSchema,
      jsonRequest("POST", {})
    );
  }

  cancelStudy(studyId: string) {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/cancel`,
      TerminalReceiptSchema,
      jsonRequest("POST", {})
    );
  }

  failStudy(studyId: string, reason: string) {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/fail`,
      TerminalReceiptSchema,
      jsonRequest("POST", { schema_version: 1, reason })
    );
  }

  recoverStudy(studyId: string) {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/recover`,
      RecoverReceiptSchema,
      jsonRequest("POST", {})
    );
  }

  startNextRound(studyId: string, requestId: string) {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/next-round`,
      NextRoundReceiptSchema,
      jsonRequest("POST", { schema_version: 1, request_id: requestId })
    );
  }

  retryTrial(trialId: string) {
    return this.request(
      `/api/v1/optimizer/trials/${safeId(trialId)}/retry`,
      RetryReceiptSchema,
      jsonRequest("POST", {})
    );
  }

  exportComparison(studyId: string, trialIds: string[], includeCategories: boolean): Promise<ExportComparisonReceipt> {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/export-comparison`,
      ExportComparisonReceiptSchema,
      jsonRequest("POST", { schema_version: 1, trial_ids: trialIds.map(safeIdValue), include_categories: includeCategories })
    );
  }

  convertToDraft(studyId: string, trialId: string, requestId: string) {
    return this.request(
      `/api/v1/optimizer/studies/${safeId(studyId)}/recommendation/${safeId(trialId)}/convert-draft`,
      ConvertReceiptSchema,
      jsonRequest("POST", { schema_version: 1, request_id: requestId, label: null })
    );
  }

  private async request<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      ...init,
      method: init.method ?? "GET",
      headers,
      cache: init.cache ?? "no-store"
    });
    let payload: unknown = null;
    try { payload = await response.json(); } catch { payload = null; }
    if (!response.ok) {
      throw new OptimizerTransportError(`Optimizer request failed with HTTP ${response.status}.`, response.status, payload);
    }
    return successEnvelope(schema).parse(payload).data;
  }
}

function jsonRequest(method: "POST" | "DELETE", payload: object): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  };
}

function safeIdValue(value: string): string {
  if (!/^[A-Za-z0-9_-]{1,36}$/.test(value)) throw new RangeError("Optimizer ids must be bounded safe identifiers.");
  return value;
}

function safeId(value: string): string {
  return encodeURIComponent(safeIdValue(value));
}
