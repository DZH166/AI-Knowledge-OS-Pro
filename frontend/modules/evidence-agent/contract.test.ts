import { describe, expect, it } from "vitest";

import {
  ArtifactSchema,
  EvidenceReferenceSchema,
  ResearchOutcomeSchema,
  RunCommandSchema,
  RunEventSchema,
  RunViewSchema,
  RunStatusSchema,
  StartRunInputSchema
} from "./contract";

describe("Evidence Agent runtime contract", () => {
  it("rejects an artifact whose factual claim has no immutable evidence reference", () => {
    const result = ArtifactSchema.safeParse({
      schema_version: 1,
      artifact_id: "artifact-1",
      producing_run_id: "run-1",
      kind: "research_report",
      title: "Active revision findings",
      claims: [
        {
          claim_id: "claim-1",
          kind: "factual",
          text: "Only the active revision participates in retrieval.",
          evidence_refs: []
        }
      ],
      gaps: [],
      created_at: "2026-08-15T09:00:00.000Z"
    });

    expect(result.success).toBe(false);
  });

  it("requires every factual claim reference to bind source, immutable revision, locator, hash, and support relation", () => {
    const artifact = {
      schema_version: 1,
      artifact_id: "artifact-1",
      producing_run_id: "run-1",
      kind: "research_report",
      title: "Active revision findings",
      claims: [
        {
          claim_id: "claim-1",
          kind: "factual",
          text: "Only the active revision participates in retrieval.",
          evidence_refs: [
            {
              source_id: 1,
              revision_id: 2,
              index_revision_id: 3,
              chunk_id: 31,
              content_hash: "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
              relation: "supports",
              locator: { kind: "page", page_number: 12 }
            }
          ]
        }
      ],
      gaps: [],
      created_at: "2026-08-15T09:00:00.000Z"
    } as const;

    expect(ArtifactSchema.safeParse(artifact).success).toBe(true);
    expect(
      ArtifactSchema.safeParse({
        ...artifact,
        claims: [
          {
            ...artifact.claims[0],
            evidence_refs: [{ ...artifact.claims[0].evidence_refs[0], revision_id: undefined }]
          }
        ]
      }).success
    ).toBe(false);
  });

  it("accepts canonical persisted locator kinds in live Evidence Ledger events", () => {
    expect(
      EvidenceReferenceSchema.safeParse({
        source_id: 11,
        revision_id: 21,
        index_revision_id: 31,
        chunk_id: 41,
        content_hash: "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
        locator: {
          kind: "document_page",
          document_id: 9,
          page_number: 12,
          heading_path: "Agent/Evidence"
        }
      }).success
    ).toBe(true);
  });

  it("parses insufficient evidence as a normal research outcome with a gap artifact", () => {
    const result = ResearchOutcomeSchema.safeParse({
      kind: "insufficient_evidence",
      stop_reason: "budget_exhausted",
      artifact: {
        schema_version: 1,
        artifact_id: "artifact-gap-1",
        producing_run_id: "run-1",
        kind: "evidence_gap_report",
        title: "Evidence still needed",
        claims: [],
        gaps: [
          {
            gap_id: "gap-1",
            requirement: "Confirm which revision was active during the incident.",
            reason: "No retained source covers the requested date.",
            next_queries: ["Locate the deployment manifest for 2026-08-14"]
          }
        ],
        created_at: "2026-08-15T09:00:00.000Z"
      }
    });

    expect(result.success).toBe(true);
  });

  it("requires an idempotency key for cancellation commands", () => {
    expect(
      RunCommandSchema.safeParse({ request_id: "command-1", expected_version: 1, signal: "cancel" }).success
    ).toBe(true);
    expect(RunCommandSchema.safeParse({ expected_version: 1, signal: "cancel" }).success).toBe(false);
  });

  it("uses the public event schema version and complete run status vocabulary", () => {
    expect(RunStatusSchema.safeParse("queued").success).toBe(true);
    expect(RunStatusSchema.safeParse("routing").success).toBe(true);
    expect(
      RunEventSchema.safeParse({
        schema_version: 1,
        event_id: "event-1",
        cursor: 1,
        run_id: "run-1",
        run_version: 1,
        change: { type: "status_changed", status: "queued" }
      }).success
    ).toBe(true);
    expect(
      RunEventSchema.safeParse({
        schema_version: "v5",
        event_id: "event-legacy",
        cursor: 1,
        run_id: "run-1",
        run_version: 1,
        change: { type: "status_changed", status: "queued" }
      }).success
    ).toBe(false);
  });

  it("matches the approved OpenRun and immutable evidence identity wire shapes", () => {
    expect(
      StartRunInputSchema.safeParse({
        schema_version: 1,
        request_id: "request-1",
        space_id: 7,
        goal: "核验每个结论",
        scope: { source_ids: [11, 12] },
        deliverable: { kind: "research_report" },
        mode: "auto",
        budget: { max_steps: 8, max_tool_calls: 12, max_model_calls: 6 },
        permissions: { read_only: true, allow_scope_expansion: false },
        provider_mode: "recording"
      }).success
    ).toBe(true);

    expect(
      EvidenceReferenceSchema.safeParse({
        source_id: 11,
        revision_id: 21,
        index_revision_id: 31,
        chunk_id: 41,
        content_hash: "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
        locator: { kind: "page", page_number: 12 }
      }).success
    ).toBe(true);
  });

  it("accepts a versioned modify command with a replacement title", () => {
    expect(
      RunCommandSchema.safeParse({
        schema_version: 1,
        request_id: "modify-title-1",
        expected_version: 7,
        signal: "modify",
        response: { title: "人工复核后的研究报告" },
        proposal_digest: "a".repeat(64)
      }).success
    ).toBe(true);
  });

  it("preserves the backend cost measurement instead of treating unknown spend as zero", () => {
    const result = RunViewSchema.safeParse({
      schema_version: 1,
      id: "run-cost-1",
      space_id: 7,
      goal: "核验成本状态",
      requested_mode: "auto",
      effective_mode: "force_quick",
      status: "completed",
      phase: "persist_artifact",
      version: 2,
      execution_epoch: 0,
      scope_snapshot: { space_id: 7, revisions: [] },
      budget_limits: { max_steps: 4 },
      budget_usage: { cost_unknown_calls: 1 },
      cost_measurement: "partial_unknown",
      provider_mode: "real",
      last_event_cursor: 3,
      final_artifact_id: "artifact-cost-1",
      termination_reason: null,
      outcome: { kind: "artifact", artifact_id: "artifact-cost-1" }
    });

    expect(result.success).toBe(true);
    if (result.success) expect(result.data.cost_measurement).toBe("partial_unknown");
  });
});
