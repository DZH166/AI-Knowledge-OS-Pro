import type { StartRunInput } from "./contract";

/** Reuse a request identity only while the complete research intent is unchanged. */
export function runIntentKey(intent: Omit<StartRunInput, "request_id">): string {
  return JSON.stringify(intent);
}
