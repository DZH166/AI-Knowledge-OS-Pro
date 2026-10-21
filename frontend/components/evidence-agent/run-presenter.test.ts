import { describe, expect, it } from "vitest";

import type { RunEvent } from "@/modules/evidence-agent";
import { attentionFromEvents, ledgerFromEvents, planFromEvents } from "./run-presenter";

function interactionEvent(payload: Record<string, unknown>): RunEvent {
  return {
    schema_version: 1,
    event_id: "run-1:4",
    cursor: 4,
    run_id: "run-1",
    run_version: 4,
    change: { type: "domain_event", event_type: "interaction.required", payload }
  };
}

describe("run attention presenter", () => {
  it("presents a persisted clarification gate while awaiting input", () => {
    const attention = attentionFromEvents(
      [
        interactionEvent({
          gate_id: "gate-1",
          kind: "clarification",
          question: "请指定要核验的年份。",
          target: { requirement_id: "requirement-1", requirement_ordinal: 2 },
          response_schema: {
            type: "object",
            properties: { text: { type: "string", minLength: 1, maxLength: 500 } },
            required: ["text"],
            additionalProperties: false
          }
        })
      ],
      "awaiting_input"
    );

    expect(attention).toEqual({
      kind: "clarification",
      gateId: "gate-1",
      question: "请指定要核验的年份。",
      targetRequirementId: "requirement-1",
      targetRequirementOrdinal: 2
    });
  });

  it("does not treat an approval event as clarification", () => {
    expect(
      attentionFromEvents(
        [
          interactionEvent({
            kind: "approval",
            summary: "发布成果",
            target: "artifact:research_report",
            risk_class: "write",
            proposal_digest: "a".repeat(64)
          })
        ],
        "awaiting_input"
      )
    ).toBeNull();
  });
});

describe("run public event projection", () => {
  it("projects the durable plan.created requirements without relying on demo-only labels", () => {
    const plan = planFromEvents([
      {
        schema_version: 1,
        event_id: "run-1:2",
        cursor: 2,
        run_id: "run-1",
        run_version: 2,
        change: {
          type: "domain_event",
          event_type: "plan.created",
          payload: {
            plan_version: 1,
            strategy: "structured_model_plan",
            requirements: ["核验成本", "核验延迟"]
          }
        }
      }
    ]);

    expect(plan).toEqual({
      version: 1,
      strategy: "structured_model_plan",
      requirements: ["核验成本", "核验延迟"]
    });
  });

  it("replays evidence relation changes as ordered upserts keyed by evidence id", () => {
    const reference = {
      source_id: 1,
      revision_id: 2,
      index_revision_id: 3,
      chunk_id: 4,
      content_hash: "a".repeat(64),
      locator: { kind: "text" as const, start_offset: 0, end_offset: 18 }
    };
    const events: RunEvent[] = [
      {
        schema_version: 1,
        event_id: "run-1:3",
        cursor: 3,
        run_id: "run-1",
        run_version: 3,
        change: {
          type: "domain_event",
          event_type: "evidence.added",
          payload: {
            evidence_id: "evidence-1",
            source_title: "Pinned source",
            excerpt: "candidate excerpt",
            relation: "candidate",
            reference
          }
        }
      },
      {
        schema_version: 1,
        event_id: "run-1:4",
        cursor: 4,
        run_id: "run-1",
        run_version: 4,
        change: {
          type: "domain_event",
          event_type: "evidence.relation_changed",
          payload: {
            evidence_id: "evidence-1",
            requirement_id: "requirement-1",
            requirement_ordinal: 1,
            previous_relation: "candidate",
            relation: "supports",
            reason: "model_selected_support",
            method: "model_assessment"
          }
        }
      }
    ];

    expect(ledgerFromEvents(events)).toEqual([
      {
        id: "evidence-1",
        sourceTitle: "Pinned source",
        excerpt: "candidate excerpt",
        relation: "supports",
        reason: "model_selected_support",
        method: "model_assessment",
        reference
      }
    ]);
    expect(ledgerFromEvents(events)).toEqual(ledgerFromEvents([...events]));
  });

  it("keeps excluded evidence visible with a human-readable reason", () => {
    const events: RunEvent[] = [
      {
        schema_version: 1,
        event_id: "run-1:5",
        cursor: 5,
        run_id: "run-1",
        run_version: 5,
        change: {
          type: "domain_event",
          event_type: "evidence.added",
          payload: {
            evidence_id: "evidence-excluded",
            source_title: "Candidate source",
            excerpt: "candidate excerpt",
            relation: "candidate",
            reference: {
              source_id: 1,
              revision_id: 2,
              index_revision_id: 3,
              chunk_id: 5,
              content_hash: "b".repeat(64),
              locator: { kind: "text" }
            }
          }
        }
      },
      {
        schema_version: 1,
        event_id: "run-1:6",
        cursor: 6,
        run_id: "run-1",
        run_version: 6,
        change: {
          type: "domain_event",
          event_type: "evidence.relation_changed",
          payload: {
            evidence_id: "evidence-excluded",
            requirement_id: "requirement-1",
            requirement_ordinal: 1,
            previous_relation: "candidate",
            relation: "excluded",
            reason: "model_not_selected",
            method: "model_assessment"
          }
        }
      }
    ];
    expect(ledgerFromEvents(events)[0]).toMatchObject({
      relation: "excluded",
      reason: "model_not_selected",
      method: "model_assessment"
    });
  });
});
