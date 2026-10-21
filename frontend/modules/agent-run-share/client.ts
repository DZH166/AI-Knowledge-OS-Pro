import { z } from "zod";

import { resolveEvidenceApiBaseUrl } from "@/modules/evidence-agent/api-base-url";
import { backendErrorDetails, backendErrorMessage } from "@/services/backend-error";
import {
  RevokeShareReceiptSchema,
  ShareLinkReceiptSchema,
  type ShareLinkReceipt
} from "./contract";


type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type ClientOptions = { baseUrl?: string; fetch?: Fetch };

const successEnvelope = <T extends z.ZodType>(data: T) =>
  z.object({ success: z.literal(true), data, error: z.null(), request_id: z.string().min(1) }).passthrough();

export class AgentRunShareTransportError extends Error {
  readonly code: string | null;
  readonly retryable: boolean;

  constructor(message: string, readonly status: number, readonly payload: unknown) {
    super(message);
    this.name = "AgentRunShareTransportError";
    const details = backendErrorDetails(payload);
    this.code = details.code;
    this.retryable = details.retryable;
  }
}

export class AgentRunShareClient {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  create(runId: string, expiresInDays = 7): Promise<ShareLinkReceipt> {
    return this.request(
      `/api/v1/agent-runs/${safeId(runId)}/share`,
      ShareLinkReceiptSchema,
      jsonRequest({ schema_version: 1, expires_in_days: expiresInDays })
    );
  }

  revoke(token: string) {
    return this.request(
      `/api/v1/agent-runs/shared/${safeToken(token)}`,
      RevokeShareReceiptSchema,
      { method: "DELETE" }
    );
  }

  async listActive(runId: string, signal?: AbortSignal): Promise<ShareLinkReceipt[]> {
    return (await this.request(
      `/api/v1/agent-runs/${safeId(runId)}/shares`,
      z.object({ items: z.array(ShareLinkReceiptSchema).max(100) }).strict(),
      { method: "GET", signal }
    )).items;
  }

  private async request<T>(path: string, schema: z.ZodType<T>, init: RequestInit): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    const response = await this.fetch(`${this.baseUrl}${path}`, { ...init, headers, cache: "no-store" });
    let payload: unknown = null;
    try { payload = await response.json(); } catch { payload = null; }
    if (!response.ok) {
      throw new AgentRunShareTransportError(
        backendErrorMessage(payload, `Agent Run share request failed with HTTP ${response.status}.`),
        response.status,
        payload
      );
    }
    return successEnvelope(schema).parse(payload).data;
  }
}

function jsonRequest(payload: object): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  };
}

function safeId(value: string): string {
  if (!/^[A-Za-z0-9_-]{1,36}$/.test(value)) throw new Error("Unsafe Agent Run identifier.");
  return encodeURIComponent(value);
}

function safeToken(value: string): string {
  if (!/^[a-fA-F0-9]{64}$/.test(value)) throw new Error("Unsafe share token.");
  return encodeURIComponent(value);
}
