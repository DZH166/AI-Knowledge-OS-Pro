import { describe, expect, it } from "vitest";

import {
  EvaluationComparisonSchema,
  EvaluationDetailSchema,
  RunTraceSchema,
  StartEvaluationInputSchema
} from "./contract";
import { evaluationDetail, runTrace } from "./test-fixtures";


describe("agent control runtime contracts", () => {
  it("accepts the fixed deterministic evaluation and strict start input", () => {
    expect(EvaluationDetailSchema.parse(evaluationDetail()).cases).toHaveLength(60);
    expect(StartEvaluationInputSchema.parse({ request_id: "request-1", label: "Baseline" })).toEqual({
      schema_version: 1,
      request_id: "request-1",
      label: "Baseline"
    });
  });

  it("rejects arbitrary start fields and dishonest passed evaluations", () => {
    expect(() => StartEvaluationInputSchema.parse({
      request_id: "request-1",
      label: "Baseline",
      dataset_path: "C:/private.jsonl"
    })).toThrow();
    expect(() => EvaluationDetailSchema.parse({
      ...evaluationDetail(),
      summary: { ...evaluationDetail().summary, external_provider_calls: 1 }
    })).toThrow(/zero external provider calls/i);
    expect(() => EvaluationDetailSchema.parse({
      ...evaluationDetail(),
      cases: evaluationDetail().cases.slice(0, 59)
    })).toThrow(/case rows|60 cases/i);
    expect(() => EvaluationDetailSchema.parse({
      ...evaluationDetail(),
      failure_case_ids: ["case-1"]
    })).toThrow(/failure counts/i);
    expect(() => EvaluationDetailSchema.parse({
      ...evaluationDetail(),
      provider_boundary: "This is a real production benchmark."
    })).toThrow(/provider boundary/i);
    expect(() => EvaluationDetailSchema.parse({
      ...evaluationDetail(),
      metrics: { ...evaluationDetail().metrics, case_pass_rate: 0.5 }
    })).toThrow(/pass rates/i);
    const duplicateCases = evaluationDetail().cases.map((item, index) => index === 1 ? { ...item, case_id: "case-1" } : item);
    expect(() => EvaluationDetailSchema.parse({
      ...evaluationDetail(),
      cases: duplicateCases
    })).toThrow(/unique/i);
  });

  it("rejects private trace facts and unknown payload fields", () => {
    const trace = runTrace();
    expect(() => RunTraceSchema.parse({
      ...trace,
      events: [{
        ...trace.events[0],
        visibility: "private",
        redacted: true,
        facts: ["prompt=private"]
      }]
    })).toThrow(/cannot expose facts/i);
    expect(() => RunTraceSchema.parse({
      ...trace,
      events: [{ ...trace.events[0], prompt: "raw private prompt" }]
    })).toThrow();
    expect(() => RunTraceSchema.parse({
      ...trace,
      replay: { ...trace.replay, event_count: 2 }
    })).toThrow(/counts/i);
    expect(() => RunTraceSchema.parse({
      ...trace,
      events: [{ ...trace.events[0], sequence: 2 }]
    })).toThrow(/1-based/i);
  });

  it("rejects contradictory comparison verdicts and metric flags", () => {
    const base = {
      schema_version: 1,
      left_id: "left",
      right_id: "right",
      compatible: false,
      incompatibility_reasons: ["dataset_digest_mismatch"],
      verdict: "stable",
      policy_changed: false,
      left_policy_fingerprint: "a".repeat(64),
      right_policy_fingerprint: "a".repeat(64),
      metric_deltas: [],
      gate_changes: [],
      new_failure_case_ids: [],
      resolved_failure_case_ids: []
    };
    expect(() => EvaluationComparisonSchema.parse(base)).toThrow(/incomparable/i);
    expect(() => EvaluationComparisonSchema.parse({
      ...base,
      verdict: "incomparable",
      metric_deltas: [{
        metric: "case_pass_rate",
        left: 1,
        right: 0.9,
        delta: -0.1,
        preferred_direction: "higher",
        improved: false,
        regressed: true
      }]
    })).toThrow(/cannot expose misleading/i);
    expect(() => EvaluationComparisonSchema.parse({
      ...base,
      compatible: true,
      incompatibility_reasons: [],
      verdict: "regressed",
      metric_deltas: [{
        metric: "case_pass_rate",
        left: 1,
        right: 0.9,
        delta: -0.1,
        preferred_direction: "higher",
        improved: true,
        regressed: true
      }]
    })).toThrow(/cannot improve and regress/i);
    expect(() => EvaluationComparisonSchema.parse({
      ...base,
      verdict: "incomparable",
      policy_changed: false,
      right_policy_fingerprint: "b".repeat(64)
    })).toThrow(/policy change disclosure/i);
  });
});
