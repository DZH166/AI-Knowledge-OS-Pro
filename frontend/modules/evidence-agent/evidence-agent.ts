import type { CommandReceipt, RunCommand, RunEvent, RunReceipt, StartRunInput } from "./contract";

export type ObserveOptions = {
  after?: number;
  signal?: AbortSignal;
};

export interface EvidenceAgent {
  start(input: StartRunInput): Promise<RunReceipt>;
  observe(runId: string, options?: ObserveOptions): AsyncIterable<RunEvent>;
  act(runId: string, command: RunCommand): Promise<CommandReceipt>;
}
