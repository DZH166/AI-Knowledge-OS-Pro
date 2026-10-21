import { describe, expect, it } from "vitest";

import { RECORDING_FIXTURE } from "@/modules/evidence-agent/recording-fixture";
import { createDemoArtifact } from "./demo-artifact";

describe("createDemoArtifact", () => {
  it("binds the Artifact to its actual Recording run and the same synthetic sources used by Workbench", () => {
    const runId = "demo-run-22222222-2222-4222-8222-222222222222";
    const artifact = createDemoArtifact(runId, `artifact-${runId}`, "2026-08-15T10:00:00.000Z");

    expect(artifact).toMatchObject({
      artifact_id: `artifact-${runId}`,
      producing_run_id: runId,
      created_at: "2026-08-15T10:00:00.000Z"
    });
    expect(artifact.claims.flatMap((claim) => claim.evidence_refs)).toMatchObject([
      {
        source_id: RECORDING_FIXTURE.sources.contract.sourceId,
        revision_id: RECORDING_FIXTURE.sources.contract.revisionId,
        index_revision_id: RECORDING_FIXTURE.sources.contract.indexRevisionId,
        chunk_id: RECORDING_FIXTURE.sources.contract.chunkId
      },
      {
        source_id: RECORDING_FIXTURE.sources.runtime.sourceId,
        revision_id: RECORDING_FIXTURE.sources.runtime.revisionId,
        index_revision_id: RECORDING_FIXTURE.sources.runtime.indexRevisionId,
        chunk_id: RECORDING_FIXTURE.sources.runtime.chunkId
      }
    ]);
  });

  it("uses the approved replacement title without changing Artifact identity", () => {
    const runId = "demo-run-33333333-3333-4333-8333-333333333333";
    const artifactId = `artifact-${runId}`;
    const artifact = createDemoArtifact(
      runId,
      artifactId,
      "2026-08-21T10:00:00.000Z",
      "人工复核后的研究简报"
    );

    expect(artifact).toMatchObject({
      artifact_id: artifactId,
      producing_run_id: runId,
      title: "人工复核后的研究简报"
    });
  });

  it("shows a third cited claim only for the explicitly recorded comparison scenario", () => {
    const runId = "demo-run-44444444-4444-4444-8444-444444444444";
    const artifact = createDemoArtifact(runId, `artifact-${runId}`, "2026-08-21T10:00:00.000Z", undefined, { comparison: true });

    expect(artifact.kind).toBe("comparison");
    expect(artifact.claims).toHaveLength(3);
    expect(artifact.claims[2]?.evidence_refs[0]).toMatchObject({
      source_id: RECORDING_FIXTURE.sources.review.sourceId,
      revision_id: RECORDING_FIXTURE.sources.review.revisionId,
      chunk_id: RECORDING_FIXTURE.sources.review.chunkId
    });
  });
});
