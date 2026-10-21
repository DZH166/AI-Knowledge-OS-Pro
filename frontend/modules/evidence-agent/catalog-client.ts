import { z } from "zod";

import {
  ArtifactCatalogSchema,
  ArtifactDetailSchema,
  EvidenceDetailSchema,
  RunCatalogSchema,
  type ArtifactCatalog,
  type ArtifactDetail,
  type EvidenceDetail,
  type RunCatalog,
  type RunView
} from "./contract";
import { EvidenceAgentTransportError } from "./http-sse-adapter";
import { resolveEvidenceApiBaseUrl } from "./api-base-url";

type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type CatalogClientOptions = { baseUrl?: string; fetch?: Fetch };
type RunStatus = RunView["status"];
export type ArtifactCatalogFilters = {
  spaceId?: number;
  sourceId?: number;
  runId?: string;
  limit?: number;
};

const envelope = <T extends z.ZodType>(data: T) =>
  z.object({ success: z.literal(true), data, error: z.null(), request_id: z.string().min(1) }).passthrough();

export class EvidenceCatalogClient {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;

  constructor(options: CatalogClientOptions = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  listRuns(filters: { spaceId?: number; status?: RunStatus; limit?: number } = {}): Promise<RunCatalog> {
    const params = new URLSearchParams();
    if (filters.spaceId !== undefined) params.set("space_id", String(filters.spaceId));
    if (filters.status) params.set("status", filters.status);
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    const query = params.toString();
    return this.get(`/api/v1/evidence-runs${query ? `?${query}` : ""}`, RunCatalogSchema);
  }

  listArtifacts(filters: ArtifactCatalogFilters = {}): Promise<ArtifactCatalog> {
    const params = new URLSearchParams();
    if (filters.spaceId !== undefined) params.set("space_id", String(filters.spaceId));
    if (filters.sourceId !== undefined) params.set("source_id", String(filters.sourceId));
    if (filters.runId) params.set("run_id", filters.runId);
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    const query = params.toString();
    return this.get(`/api/v1/artifacts${query ? `?${query}` : ""}`, ArtifactCatalogSchema);
  }

  getArtifact(artifactId: string, options: { signal?: AbortSignal } = {}): Promise<ArtifactDetail> {
    return this.get(`/api/v1/artifacts/${encodeURIComponent(artifactId)}`, ArtifactDetailSchema, options.signal);
  }

  getEvidence(evidenceId: string, options: { signal?: AbortSignal } = {}): Promise<EvidenceDetail> {
    return this.get(`/api/v1/evidence/${encodeURIComponent(evidenceId)}`, EvidenceDetailSchema, options.signal);
  }

  private async get<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
    const response = await this.fetch(`${this.baseUrl}${path}`, { method: "GET", headers: { Accept: "application/json" }, signal });
    if (!response.ok) {
      let payload: unknown = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      throw new EvidenceAgentTransportError(`Evidence catalog request failed with HTTP ${response.status}.`, response.status, payload);
    }
    const payload: unknown = await response.json();
    return envelope(schema).parse(payload).data;
  }
}

export function artifactCatalogFiltersFromSearch(search: string): ArtifactCatalogFilters {
  const rawSourceId = new URLSearchParams(search).get("source_id");
  if (rawSourceId === null) return {};
  const sourceId = Number(rawSourceId);
  return Number.isSafeInteger(sourceId) && sourceId > 0 ? { sourceId } : {};
}

export function sourceArtifactCatalogHref(sourceId: number, demo = false): string {
  if (!Number.isSafeInteger(sourceId) || sourceId <= 0) {
    throw new RangeError("Source artifact links require a positive integer source id.");
  }
  const params = new URLSearchParams();
  if (demo) params.set("demo", "1");
  params.set("source_id", String(sourceId));
  return `/artifacts?${params.toString()}`;
}
