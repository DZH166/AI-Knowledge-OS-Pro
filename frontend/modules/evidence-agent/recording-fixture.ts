import type { StartRunInput } from "./contract";

const CONTRACT_HASH = "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae";
const RUNTIME_HASH = "4c94485e0c21ae6c41ce1dfe7b6bf9e287a9fe5dca2af30172935fe7bc6ba099";

export const RECORDING_FIXTURE = {
  spaces: {
    research: 9_001,
    architecture: 9_002
  },
  sources: {
    contract: {
      sourceId: 9_101,
      revisionId: 9_201,
      indexRevisionId: 9_301,
      chunkId: 9_401,
      sourceType: "document",
      title: "Evidence Agent contract.pdf",
      excerpt: "Every factual claim binds to an immutable revision, content hash, and locator.",
      contentHash: CONTRACT_HASH,
      revisionContentHash: "b".repeat(64),
      locator: { kind: "page" as const, page_number: 12 }
    },
    runtime: {
      sourceId: 9_102,
      revisionId: 9_202,
      indexRevisionId: 9_302,
      chunkId: 9_402,
      sourceType: "document",
      title: "Bounded Agent runtime.md",
      excerpt: "The run stops normally when evidence remains insufficient or the explicit budget is exhausted.",
      contentHash: RUNTIME_HASH,
      revisionContentHash: "e".repeat(64),
      locator: { kind: "text" as const, start_offset: 220, end_offset: 341 }
    },
    review: {
      sourceId: 9_104,
      revisionId: 9_204,
      indexRevisionId: 9_304,
      chunkId: 9_404,
      sourceType: "document",
      title: "Human review workflow.md",
      excerpt: "A reviewer can flag an unsupported claim and record the evidence gap without silently changing the source or policy.",
      contentHash: "d".repeat(64),
      revisionContentHash: "f".repeat(64),
      locator: { kind: "text" as const, start_offset: 40, end_offset: 169 }
    },
    code: {
      sourceId: 9_103,
      revisionId: 9_203,
      indexRevisionId: 9_303,
      chunkId: 9_403,
      sourceType: "code_repository",
      title: "agent-runtime",
      excerpt: "export async function advanceRun(): Promise<void> { /* bounded state transition */ }",
      contentHash: "c".repeat(64),
      revisionContentHash: "a".repeat(64),
      locator: {
        kind: "code_range" as const,
        file_path: "frontend/modules/evidence-agent/run-controller.ts",
        line_start: 49,
        line_end: 55
      }
    }
  }
} as const;

export const RECORDING_COMPARISON_SOURCES = [
  RECORDING_FIXTURE.sources.contract,
  RECORDING_FIXTURE.sources.runtime,
  RECORDING_FIXTURE.sources.review
] as const;

export function isRecordedComparisonInput(input: Pick<StartRunInput, "space_id" | "scope" | "deliverable">): boolean {
  return input.deliverable?.kind === "comparison" &&
    input.space_id === RECORDING_FIXTURE.spaces.research &&
    RECORDING_COMPARISON_SOURCES.every((source) => input.scope?.source_ids?.includes(source.sourceId));
}

