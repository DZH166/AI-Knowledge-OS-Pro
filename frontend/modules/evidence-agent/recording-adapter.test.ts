import { describe, expect, it } from "vitest";

import type { StartRunInput } from "./contract";
import { RecordingEvidenceAgentAdapter } from "./recording-adapter";
import { RECORDING_FIXTURE, isRecordedComparisonInput } from "./recording-fixture";

const startInput: StartRunInput = {
  schema_version: 1,
  request_id: "request-1",
  space_id: 1,
  goal: "Compare the pinned revisions across selected sources.",
  scope: { source_ids: [1, 2] },
  deliverable: { kind: "research_report" },
  mode: "force_agent",
  budget: { max_steps: 8, max_tool_calls: 12, max_model_calls: 6 },
  permissions: { read_only: true, allow_scope_expansion: false },
  provider_mode: "recording"
};

describe("RecordingEvidenceAgentAdapter", () => {
  it("identifies the same three-document recording scenario for runs and artifacts", () => {
    const ids = [
      RECORDING_FIXTURE.sources.contract.sourceId,
      RECORDING_FIXTURE.sources.runtime.sourceId,
      RECORDING_FIXTURE.sources.review.sourceId
    ];
    const candidate = { ...startInput, space_id: RECORDING_FIXTURE.spaces.research,
      scope: { source_ids: ids }, deliverable: { kind: "comparison" as const } };
    expect(isRecordedComparisonInput(candidate)).toBe(true);
    expect(isRecordedComparisonInput({ ...candidate, scope: { source_ids: ids.slice(0, 2) } })).toBe(false);
    expect(isRecordedComparisonInput({ ...candidate, deliverable: { kind: "research_report" } })).toBe(false);
  });

  it("pins all three selected synthetic revisions in a recorded comparison", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({
      createRunId: () => "run-recorded-comparison",
      scenario: "portfolio-demo"
    });
    const sources = [
      RECORDING_FIXTURE.sources.contract,
      RECORDING_FIXTURE.sources.runtime,
      RECORDING_FIXTURE.sources.review
    ];
    const receipt = await adapter.start({
      ...startInput,
      space_id: RECORDING_FIXTURE.spaces.research,
      scope: { source_ids: sources.map((source) => source.sourceId) },
      deliverable: { kind: "comparison" }
    });
    const events = [];
    for await (const event of adapter.observe(receipt.run_id)) events.push(event);

    expect(receipt.view.scope_snapshot.revisions.map((revision) => revision.source_id))
      .toEqual(sources.map((source) => source.sourceId));
    expect(events.filter((event) => event.change.type === "domain_event" && event.change.event_type === "evidence.added")
      .map((event) => event.change.type === "domain_event" ? event.change.payload.reference : null))
      .toContainEqual(expect.objectContaining({ source_id: RECORDING_FIXTURE.sources.review.sourceId }));

    expect(events.find((event) => event.change.type === "domain_event" && event.change.event_type === "interaction.required"))
      .toMatchObject({ change: { payload: { summary: "发布三资料对比录制样例", target: "artifact:comparison" } } });

    await adapter.act(receipt.run_id, {
      request_id: "approve-recorded-comparison",
      expected_version: 7,
      signal: "approve",
      proposal_digest: "a".repeat(64)
    });
    expect(adapter.exportJournal(receipt.run_id).events.find((event) =>
      event.change.type === "domain_event" && event.change.event_type === "artifact.published"
    )).toMatchObject({ change: { payload: { title: "三资料对比录制样例" } } });
  });

  it("creates a deterministic run and exposes its initial snapshot through observe", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({ createRunId: () => "run-recorded-1" });
    const receipt = await adapter.start(startInput);

    expect(receipt).toMatchObject({
      schema_version: 1,
      run_id: "run-recorded-1",
      cursor: 1,
      view: { goal: startInput.goal, status: "queued", requested_mode: "force_agent" }
    });

    const events = adapter.observe(receipt.run_id);
    const first = await events[Symbol.asyncIterator]().next();
    expect(first.value).toMatchObject({
      schema_version: 1,
      event_id: "run-recorded-1:1",
      cursor: 1,
      run_id: "run-recorded-1",
      change: { type: "snapshot", reset: false }
    });
  });

  it("turns cancellation into a command event resumable from the prior cursor", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({ createRunId: () => "run-recorded-2" });
    const run = await adapter.start({ ...startInput, request_id: "request-2" });
    const receipt = await adapter.act(run.run_id, {
      request_id: "command-cancel-1",
      expected_version: 1,
      signal: "cancel"
    });
    const cancelled = await adapter.observe(run.run_id, { after: run.cursor })[Symbol.asyncIterator]().next();

    expect(receipt).toMatchObject({
      command_id: "command-cancel-1",
      status: "cancelled",
      cursor: 2,
      run_version: 2
    });
    expect(cancelled.value).toMatchObject({
      cursor: 2,
      run_version: 2,
      change: { type: "status_changed", status: "cancelled" }
    });
  });

  it("replays the same receipt without appending another event for a duplicate request id", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({ createRunId: () => "run-recorded-3" });
    const run = await adapter.start({ ...startInput, request_id: "request-3" });
    const command = { request_id: "command-duplicate", expected_version: 1, signal: "cancel" } as const;

    const firstReceipt = await adapter.act(run.run_id, command);
    const duplicateReceipt = await adapter.act(run.run_id, command);
    const events = [];
    for await (const event of adapter.observe(run.run_id, { after: run.cursor })) events.push(event);

    expect(duplicateReceipt).toEqual(firstReceipt);
    expect(events).toHaveLength(1);
  });

  it("emits a reset snapshot when a caller resumes from an unknown cursor", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({ createRunId: () => "run-recorded-reset" });
    const run = await adapter.start({ ...startInput, request_id: "request-reset" });
    const reset = await adapter.observe(run.run_id, { after: 999 })[Symbol.asyncIterator]().next();

    expect(reset.value).toMatchObject({ cursor: 1, change: { type: "snapshot", reset: true } });
  });

  it("ends a rejected publication as insufficient evidence like the backend state machine", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({
      createRunId: () => "run-recorded-reject",
      scenario: "portfolio-demo"
    });
    const run = await adapter.start({ ...startInput, request_id: "request-reject" });
    const existingEvents = [];
    for await (const event of adapter.observe(run.run_id)) existingEvents.push(event);
    const awaitingApproval = existingEvents.at(-1);

    expect(awaitingApproval).toMatchObject({
      run_version: 7,
      change: { type: "domain_event", event_type: "interaction.required" }
    });

    const rejected = await adapter.act(run.run_id, {
      request_id: "command-reject",
      expected_version: 7,
      signal: "reject",
      proposal_digest: "a".repeat(64)
    });
    const rejectionEvent = await adapter.observe(run.run_id, { after: awaitingApproval?.cursor })[Symbol.asyncIterator]().next();

    expect(rejected.status).toBe("insufficient_evidence");
    expect(rejectionEvent.value).toMatchObject({
      run_version: 8,
      change: { type: "status_changed", status: "insufficient_evidence" }
    });
  });

  it("uses the production plan.created public contract with displayable requirements", async () => {
    const adapter = new RecordingEvidenceAgentAdapter({
      createRunId: () => "run-recorded-plan-contract",
      scenario: "portfolio-demo"
    });
    const run = await adapter.start({ ...startInput, request_id: "request-plan-contract" });
    const events = [];
    for await (const event of adapter.observe(run.run_id)) events.push(event);

    const plan = events.find(
      (event) => event.change.type === "domain_event" && event.change.event_type === "plan.created"
    );
    expect(plan).toMatchObject({
      change: {
        type: "domain_event",
        event_type: "plan.created",
        payload: {
          plan_version: 1,
          strategy: "structured_model_plan",
          requirements: expect.arrayContaining([expect.any(String)])
        }
      }
    });
    expect(
      events.some(
        (event) => event.change.type === "domain_event" && event.change.event_type === "plan.proposed"
      )
    ).toBe(false);
  });

  it("restores the completed event and command journal with the real demo run artifact identity", async () => {
    const runId = "demo-run-11111111-1111-4111-8111-111111111111";
    const adapter = new RecordingEvidenceAgentAdapter({
      createRunId: () => runId,
      scenario: "portfolio-demo"
    });
    const run = await adapter.start({ ...startInput, request_id: "request-durable-demo" });
    const command = {
      request_id: "command-durable-approval",
      expected_version: 7,
      signal: "approve",
      proposal_digest: "a".repeat(64)
    } as const;

    const firstReceipt = await adapter.act(run.run_id, command);
    const journal = adapter.exportJournal(run.run_id);
    const restored = new RecordingEvidenceAgentAdapter({ journal, scenario: "portfolio-demo" });
    const replayedReceipt = await restored.act(run.run_id, command);
    const events = [];
    for await (const event of restored.observe(run.run_id, { after: run.cursor })) events.push(event);

    expect(journal).toMatchObject({
      schema_version: 1,
      run_id: runId,
      bootstrap_receipt: { run_id: runId, cursor: 1 },
      current_receipt: {
        run_id: runId,
        cursor: 14,
        view: {
          id: runId,
          status: "completed",
          final_artifact_id: `artifact-${runId}`
        }
      },
      commands: [{ command, receipt: firstReceipt }]
    });
    expect(replayedReceipt).toEqual(firstReceipt);
    expect(events.at(-1)).toMatchObject({
      cursor: 14,
      change: { type: "status_changed", status: "completed" }
    });
  });

  it("rotates the proposal digest and publishes the modified title to the same Artifact", async () => {
    const runId = "demo-run-title-modification";
    const adapter = new RecordingEvidenceAgentAdapter({
      createRunId: () => runId,
      scenario: "portfolio-demo"
    });
    const run = await adapter.start({ ...startInput, request_id: "request-title-modification" });

    await adapter.act(run.run_id, {
      request_id: "command-modify-title",
      expected_version: 7,
      signal: "modify",
      response: { title: "人工复核后的研究简报" },
      proposal_digest: "a".repeat(64)
    });

    await expect(adapter.act(run.run_id, {
      request_id: "command-stale-approval",
      expected_version: 8,
      signal: "approve",
      proposal_digest: "a".repeat(64)
    })).rejects.toThrow("Proposal Digest 已失效");

    await adapter.act(run.run_id, {
      request_id: "command-current-approval",
      expected_version: 8,
      signal: "approve",
      proposal_digest: "b".repeat(64)
    });

    const journal = adapter.exportJournal(run.run_id);
    expect(journal.current_receipt.view).toMatchObject({
      status: "completed",
      final_artifact_id: `artifact-${runId}`
    });
    expect(journal.events).toEqual(expect.arrayContaining([
      expect.objectContaining({
        change: {
          type: "domain_event",
          event_type: "interaction.required",
          payload: expect.objectContaining({ proposal_digest: "b".repeat(64) })
        }
      }),
      expect.objectContaining({
        change: {
          type: "domain_event",
          event_type: "artifact.published",
          payload: {
            artifact_id: `artifact-${runId}`,
            title: "人工复核后的研究简报"
          }
        }
      })
    ]));
  });
});
