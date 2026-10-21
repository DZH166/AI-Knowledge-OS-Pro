import { describe, expect, it } from "vitest";

import {
  CreatePolicyInputSchema,
  PolicyComparisonSchema,
  PolicyDetailSchema,
  PolicySimulationSchema
} from "./contract";
import { policyComparison, policyDetail, policySimulation } from "./test-fixtures";


describe("Agent policy runtime contracts", () => {
  it("accepts strict policy detail, draft input, comparison, and simulation", () => {
    expect(PolicyDetailSchema.parse(policyDetail()).status).toBe("active");
    expect(PolicyComparisonSchema.parse(policyComparison()).changes).toHaveLength(2);
    expect(PolicySimulationSchema.parse(policySimulation()).changed_decision_count).toBe(1);
    expect(CreatePolicyInputSchema.parse({
      request_id: "create-1",
      label: "Candidate",
      base_policy_id: "policy-1",
      config: policyDetail().config
    }).schema_version).toBe(1);
  });

  it("rejects executable fields, boolean integers, contradictory diffs, and dishonest simulations", () => {
    expect(() => CreatePolicyInputSchema.parse({
      request_id: "create-1",
      label: "Candidate",
      base_policy_id: "policy-1",
      config: { ...policyDetail().config, factual_top_k: true }
    })).toThrow();
    expect(() => CreatePolicyInputSchema.parse({
      request_id: "create-1",
      label: "Candidate",
      base_policy_id: "policy-1",
      config: { ...policyDetail().config, arbitrary_python: "import os" }
    })).toThrow();
    expect(() => PolicyComparisonSchema.parse({
      ...policyComparison(), compatible: false, incompatibility_reasons: ["schema"], changes: policyComparison().changes
    })).toThrow(/cannot expose/i);
    expect(() => PolicySimulationSchema.parse({
      ...policySimulation(), changed_decision_count: 0
    })).toThrow(/changed count/i);
    expect(() => PolicySimulationSchema.parse({
      ...policySimulation(), private_prompt: "secret"
    })).toThrow();
  });
});
