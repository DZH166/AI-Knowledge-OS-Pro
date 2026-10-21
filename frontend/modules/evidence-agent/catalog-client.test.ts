import { describe, expect, it, vi } from "vitest";

import {
  EvidenceCatalogClient,
  artifactCatalogFiltersFromSearch,
  sourceArtifactCatalogHref
} from "./catalog-client";

const run = {
  schema_version: 1,
  id: "run-production-1",
  space_id: 1,
  goal: "核验生产列表",
  requested_mode: "auto",
  effective_mode: "force_agent",
  status: "running",
  phase: "retrieve",
  version: 3,
  execution_epoch: 0,
  scope_snapshot: { space_id: 1, revisions: [] },
  budget_limits: { max_steps: 8 },
  budget_usage: { steps: 2 },
  cost_measurement: "reported",
  provider_mode: "real",
  last_event_cursor: 7,
  final_artifact_id: null,
  termination_reason: null,
  outcome: null
} as const;

const artifact = {
  schema_version: 1,
  id: "artifact-production-1",
  producing_run_id: "run-production-1",
  kind: "research_report",
  title: "Production evidence report",
  body_markdown: "A supported claim [1]",
  status: "final",
  claims: [
    {
      id: "claim-production-1",
      ordinal: 1,
      text: "A supported production claim",
      kind: "factual",
      verification_status: "supported",
      evidence_ids: ["evidence-production-1"]
    }
  ]
} as const;

const evidence = {
  schema_version: 1,
  id: "evidence-production-1",
  run_id: "run-production-1",
  source_id: 2,
  revision_id: 3,
  index_revision_id: 4,
  chunk_id: 5,
  source_type: "document",
  locator: { kind: "pdf_page", page: 6 },
  revision_content_hash: "a".repeat(64),
  content_hash: "b".repeat(64),
  excerpt_preview: "supporting production excerpt",
  claim_ids: ["claim-production-1"]
} as const;

function envelope(data: unknown): Response {
  return new Response(JSON.stringify({ success: true, data, error: null, request_id: "request-catalog" }), {
    headers: { "content-type": "application/json" }
  });
}

describe("EvidenceCatalogClient", () => {
  it("round-trips a library source link into artifact catalog filters", () => {
    const href = sourceArtifactCatalogHref(42);

    expect(href).toBe("/artifacts?source_id=42");
    expect(artifactCatalogFiltersFromSearch(new URL(href, "https://example.test").search)).toEqual({
      sourceId: 42
    });
    expect(artifactCatalogFiltersFromSearch("?source_id=0")).toEqual({});
    expect(artifactCatalogFiltersFromSearch("?source_id=not-an-id")).toEqual({});
  });

  it("loads and validates the production run catalog from the fixed endpoint", async () => {
    const calls: string[] = [];
    const client = new EvidenceCatalogClient({ fetch: async (input) => {
      calls.push(String(input));
      return envelope({ schema_version: 1, items: [run] });
    } });

    const catalog = await client.listRuns();

    expect(calls).toEqual(["/api/v1/evidence-runs"]);
    expect(catalog.items[0]).toEqual(run);
  });

  it("rejects a malformed production catalog instead of rendering untrusted data", async () => {
    const client = new EvidenceCatalogClient({ fetch: async () => envelope({ schema_version: 1, items: [{ ...run, version: "3" }] }) });

    await expect(client.listRuns()).rejects.toThrow();
  });

  it("loads the fixed artifact summary catalog", async () => {
    const calls: string[] = [];
    const client = new EvidenceCatalogClient({ fetch: async (input) => {
      calls.push(String(input));
      return envelope({
        schema_version: 1,
        items: [{ id: "artifact-1", producing_run_id: "run-1", kind: "research_report", title: "核验报告", status: "published" }]
      });
    } });

    const catalog = await client.listArtifacts();

    expect(calls).toEqual(["/api/v1/artifacts"]);
    expect(catalog.items).toHaveLength(1);
  });

  it("maps a source artifact filter to the production endpoint query", async () => {
    const calls: string[] = [];
    const client = new EvidenceCatalogClient({ fetch: async (input) => {
      calls.push(String(input));
      return envelope({ schema_version: 1, items: [] });
    } });

    await client.listArtifacts({ spaceId: 1, sourceId: 2, runId: "run source", limit: 7 });

    expect(calls).toEqual([
      "/api/v1/artifacts?space_id=1&source_id=2&run_id=run+source&limit=7"
    ]);
  });

  it("uses the configured backend origin with default fetch", async () => {
    const calls: string[] = [];
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://evidence-api.example.test/");
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return envelope({ schema_version: 1, items: [] });
    });
    try {
      await new EvidenceCatalogClient().listArtifacts();
      expect(calls).toEqual(["https://evidence-api.example.test/api/v1/artifacts"]);
    } finally {
      vi.unstubAllGlobals();
      vi.unstubAllEnvs();
    }
  });

  it("follows a claim evidence id through the fixed artifact and evidence detail endpoints", async () => {
    const calls: string[] = [];
    const client = new EvidenceCatalogClient({ fetch: async (input) => {
      calls.push(String(input));
      return calls.length === 1 ? envelope(artifact) : envelope(evidence);
    } });

    const loadedArtifact = await client.getArtifact(artifact.id);
    const loadedEvidence = await client.getEvidence(loadedArtifact.claims[0].evidence_ids[0]);

    expect(calls).toEqual([
      "/api/v1/artifacts/artifact-production-1",
      "/api/v1/evidence/evidence-production-1"
    ]);
    expect(loadedEvidence).toMatchObject({
      revision_id: 3,
      index_revision_id: 4,
      locator: { kind: "pdf_page", page: 6 },
      content_hash: "b".repeat(64)
    });
  });

  it("rejects malformed artifact detail payloads", async () => {
    const client = new EvidenceCatalogClient({ fetch: async () => envelope({ ...artifact, claims: [{ ...artifact.claims[0], evidence_ids: [] }] }) });

    await expect(client.getArtifact(artifact.id)).rejects.toThrow();
  });

  it("rejects evidence without immutable provenance", async () => {
    const client = new EvidenceCatalogClient({ fetch: async () => envelope({ ...evidence, content_hash: "not-a-sha256" }) });

    await expect(client.getEvidence(evidence.id)).rejects.toThrow();
  });
});
