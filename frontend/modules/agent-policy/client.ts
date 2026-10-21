import { z } from "zod";

import { resolveEvidenceApiBaseUrl } from "@/modules/evidence-agent/api-base-url";
import {
  CreatePolicyInputSchema,
  PolicyCatalogSchema,
  PolicyComparisonSchema,
  PolicyDetailSchema,
  PolicyReceiptSchema,
  PolicySimulationSchema,
  type CreatePolicyInput,
  type PolicyCatalog,
  type PolicyComparison,
  type PolicyDetail,
  type PolicyReceipt,
  type PolicySimulation,
  type PolicyStatus
} from "./contract";


type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type ClientOptions = { baseUrl?: string; fetch?: Fetch };
type ListFilters = { status?: PolicyStatus; limit?: number };

const successEnvelope = <T extends z.ZodType>(data: T) =>
  z.object({ success: z.literal(true), data, error: z.null(), request_id: z.string().min(1) }).passthrough();

export class AgentPolicyTransportError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: unknown
  ) {
    super(message);
    this.name = "AgentPolicyTransportError";
  }
}

export class AgentPolicyClient {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  listPolicies(filters: ListFilters = {}): Promise<PolicyCatalog> {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.limit !== undefined) params.set("limit", boundedLimit(filters.limit));
    const query = params.toString();
    return this.request(`/api/v1/agent-policies${query ? `?${query}` : ""}`, PolicyCatalogSchema);
  }

  getActivePolicy(signal?: AbortSignal): Promise<PolicyDetail> {
    return this.request("/api/v1/agent-policies/active", PolicyDetailSchema, { signal });
  }

  getPolicy(policyId: string, signal?: AbortSignal): Promise<PolicyDetail> {
    return this.request(`/api/v1/agent-policies/${safeId(policyId)}`, PolicyDetailSchema, { signal });
  }

  createPolicy(input: CreatePolicyInput): Promise<PolicyReceipt> {
    const payload = CreatePolicyInputSchema.parse(input);
    return this.request("/api/v1/agent-policies", PolicyReceiptSchema, jsonPost(payload));
  }

  comparePolicies(leftId: string, rightId: string, signal?: AbortSignal): Promise<PolicyComparison> {
    const params = new URLSearchParams({ left_id: safeId(leftId), right_id: safeId(rightId) });
    return this.request(`/api/v1/agent-policies/compare?${params}`, PolicyComparisonSchema, { signal });
  }

  simulatePolicy(runId: string, policyId: string, signal?: AbortSignal): Promise<PolicySimulation> {
    return this.request(
      "/api/v1/agent-policies/simulate",
      PolicySimulationSchema,
      jsonPost({ schema_version: 1, run_id: safeId(runId), policy_id: safeId(policyId) }, signal)
    );
  }

  activatePolicy(
    policyId: string,
    input: { request_id: string; expected_active_policy_id: string; evaluation_id: string }
  ): Promise<PolicyReceipt> {
    return this.request(
      `/api/v1/agent-policies/${safeId(policyId)}/activate`,
      PolicyReceiptSchema,
      jsonPost({
        schema_version: 1,
        request_id: input.request_id,
        expected_active_policy_id: safeId(input.expected_active_policy_id),
        evaluation_id: safeId(input.evaluation_id)
      })
    );
  }

  rollbackPolicy(
    policyId: string,
    input: { request_id: string; expected_active_policy_id: string }
  ): Promise<PolicyReceipt> {
    return this.request(
      `/api/v1/agent-policies/${safeId(policyId)}/rollback`,
      PolicyReceiptSchema,
      jsonPost({
        schema_version: 1,
        request_id: input.request_id,
        expected_active_policy_id: safeId(input.expected_active_policy_id)
      })
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
      throw new AgentPolicyTransportError(
        `Agent policy request failed with HTTP ${response.status}.`,
        response.status,
        payload
      );
    }
    return successEnvelope(schema).parse(payload).data;
  }
}

function jsonPost(payload: object, signal?: AbortSignal): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal
  };
}

function safeId(value: string): string {
  if (!/^[A-Za-z0-9_-]{1,36}$/.test(value)) throw new RangeError("Policy ids must be bounded safe identifiers.");
  return encodeURIComponent(value);
}

function boundedLimit(value: number): string {
  if (!Number.isInteger(value) || value < 1 || value > 100) {
    throw new RangeError("Policy list limit must be an integer between 1 and 100.");
  }
  return String(value);
}
