import { z } from "zod";

import { resolveEvidenceApiBaseUrl } from "@/modules/evidence-agent/api-base-url";
import {
  EvaluationCatalogSchema,
  EvaluationComparisonSchema,
  EvaluationDetailSchema,
  EvaluationReceiptSchema,
  RunTraceSchema,
  StartEvaluationInputSchema,
  type EvaluationCatalog,
  type EvaluationComparison,
  type EvaluationDetail,
  type EvaluationReceipt,
  type EvaluationStatus,
  type RunTrace,
  type StartEvaluationInput
} from "./contract";


type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type Sleep = (milliseconds: number, signal?: AbortSignal) => Promise<void>;
type ClientOptions = {
  baseUrl?: string;
  fetch?: Fetch;
  now?: () => number;
  sleep?: Sleep;
};
type ListFilters = { status?: EvaluationStatus; limit?: number };
type WaitOptions = { timeoutMs?: number; intervalMs?: number; signal?: AbortSignal };

const successEnvelope = <T extends z.ZodType>(data: T) =>
  z.object({ success: z.literal(true), data, error: z.null(), request_id: z.string().min(1) }).passthrough();

export class AgentControlTransportError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: unknown
  ) {
    super(message);
    this.name = "AgentControlTransportError";
  }
}

export class AgentControlClient {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;
  private readonly now: () => number;
  private readonly sleep: Sleep;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.now = options.now ?? Date.now;
    this.sleep = options.sleep ?? sleep;
  }

  startEvaluation(input: StartEvaluationInput): Promise<EvaluationReceipt> {
    const payload = StartEvaluationInputSchema.parse(input);
    return this.request("/api/v1/agent-evaluations", EvaluationReceiptSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }

  listEvaluations(filters: ListFilters = {}): Promise<EvaluationCatalog> {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    const query = params.toString();
    return this.request(`/api/v1/agent-evaluations${query ? `?${query}` : ""}`, EvaluationCatalogSchema);
  }

  getEvaluation(evaluationId: string, signal?: AbortSignal): Promise<EvaluationDetail> {
    return this.request(
      `/api/v1/agent-evaluations/${safeId(evaluationId)}`,
      EvaluationDetailSchema,
      { signal }
    );
  }

  compareEvaluations(leftId: string, rightId: string, signal?: AbortSignal): Promise<EvaluationComparison> {
    const params = new URLSearchParams({ left_id: safeId(leftId), right_id: safeId(rightId) });
    return this.request(`/api/v1/agent-evaluations/compare?${params}`, EvaluationComparisonSchema, { signal });
  }

  getRunTrace(runId: string, signal?: AbortSignal): Promise<RunTrace> {
    return this.request(`/api/v1/evidence-runs/${safeId(runId)}/trace`, RunTraceSchema, { signal });
  }

  async waitForEvaluation(evaluationId: string, options: WaitOptions = {}): Promise<EvaluationDetail> {
    const timeoutMs = boundedInteger(options.timeoutMs ?? 1_020_000, 1_000, 1_200_000, "timeoutMs");
    const intervalMs = boundedInteger(options.intervalMs ?? 750, 100, 10_000, "intervalMs");
    const startedAt = this.now();
    while (true) {
      if (options.signal?.aborted) throw options.signal.reason ?? new DOMException("Aborted", "AbortError");
      const detail = await this.getEvaluation(evaluationId, options.signal);
      if (detail.summary.status === "passed" || detail.summary.status === "failed") return detail;
      const elapsed = this.now() - startedAt;
      if (elapsed >= timeoutMs) {
        throw new AgentControlTransportError("Timed out waiting for evaluation completion.", 408, {
          evaluation_id: evaluationId,
          timeout_ms: timeoutMs
        });
      }
      await this.sleep(Math.min(intervalMs, timeoutMs - elapsed), options.signal);
    }
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
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      throw new AgentControlTransportError(
        `Agent control request failed with HTTP ${response.status}.`,
        response.status,
        payload
      );
    }
    return successEnvelope(schema).parse(payload).data;
  }
}

function safeId(value: string): string {
  if (!/^[A-Za-z0-9_-]{1,36}$/.test(value)) throw new RangeError("Agent control ids must be bounded safe identifiers.");
  return encodeURIComponent(value);
}

function boundedInteger(value: number, minimum: number, maximum: number, label: string): number {
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new RangeError(`${label} must be an integer between ${minimum} and ${maximum}.`);
  }
  return value;
}

function sleep(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
      return;
    }
    const finish = () => {
      signal?.removeEventListener("abort", abort);
      resolve();
    };
    const timeout = globalThis.setTimeout(finish, milliseconds);
    const abort = () => {
      globalThis.clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });
  });
}
