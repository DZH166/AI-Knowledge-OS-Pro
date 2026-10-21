import { z } from "zod";
import { backendErrorDetails, backendErrorMessage } from "@/services/backend-error";

import {
  CommandReceiptSchema,
  RunCommandSchema,
  RunEventSchema,
  RunReceiptSchema,
  RunStatusSchema,
  RunViewSchema,
  SseFrameSchema,
  StartRunInputSchema,
  type CommandReceipt,
  type RunCommand,
  type RunEvent,
  type RunReceipt,
  type StartRunInput
} from "./contract";
import type { EvidenceAgent, ObserveOptions } from "./evidence-agent";
import { resolveEvidenceApiBaseUrl } from "./api-base-url";

type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type HttpSseAdapterOptions = { baseUrl?: string; fetch?: Fetch };

export class EvidenceAgentTransportError extends Error {
  readonly code: string | null;
  readonly retryable: boolean;

  constructor(
    message: string,
    readonly status: number,
    readonly payload: unknown,
    options: { code?: string; retryable?: boolean } = {}
  ) {
    super(message);
    this.name = "EvidenceAgentTransportError";
    const details = backendErrorDetails(payload);
    this.code = options.code ?? details.code;
    this.retryable = options.retryable ?? details.retryable;
  }
}

export class EvidenceAgentStartError extends Error {
  constructor(readonly runId: string, readonly reason: unknown) {
    super(`研究任务已创建，但详情读取失败。${reason instanceof Error ? reason.message : "请重试。"}`);
    this.name = "EvidenceAgentStartError";
  }
}

const envelope = <T extends z.ZodType>(data: T) =>
  z
    .object({ success: z.literal(true), data, error: z.null(), request_id: z.string().min(1) })
    .passthrough();

export class HttpSseEvidenceAgentAdapter implements EvidenceAgent {
  private readonly baseUrl: string;
  private readonly fetch: Fetch;

  constructor(options: HttpSseAdapterOptions = {}) {
    this.baseUrl = resolveEvidenceApiBaseUrl(options.baseUrl, options.fetch !== undefined);
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async start(rawInput: StartRunInput): Promise<RunReceipt> {
    const input = StartRunInputSchema.parse(rawInput);
    const submission = await this.jsonRequest("/api/v1/evidence-runs", CommandReceiptSchema, {
      method: "POST",
      body: JSON.stringify(input)
    });
    try {
      return await this.resumeStart(submission.run_id, submission.cursor);
    } catch (reason) {
      throw new EvidenceAgentStartError(submission.run_id, reason);
    }
  }

  async resumeStart(runId: string, cursor?: number): Promise<RunReceipt> {
    const view = await this.jsonRequest(
      `/api/v1/evidence-runs/${encodeURIComponent(runId)}`,
      RunViewSchema,
      { method: "GET" }
    );
    return RunReceiptSchema.parse({ schema_version: 1, run_id: runId, cursor: cursor ?? view.last_event_cursor, view });
  }

  async *observe(runId: string, options: ObserveOptions = {}): AsyncGenerator<RunEvent> {
    const query = options.after === undefined ? "" : `?after=${encodeURIComponent(String(options.after))}`;
    const headers = new Headers({ Accept: "text/event-stream" });
    if (options.after !== undefined) headers.set("Last-Event-ID", String(options.after));
    const response = await this.fetchResponse(
      this.url(`/api/v1/evidence-runs/${encodeURIComponent(runId)}/stream${query}`),
      { method: "GET", headers, signal: options.signal }
    );
    await ensureOk(response);
    if (!response.body) throw new EvidenceAgentTransportError("Evidence run stream has no body.", response.status, null);

    for await (const message of decodeSse(response.body)) {
      if (!message.data) continue;
      let rawFrame: unknown;
      try {
        rawFrame = JSON.parse(message.data);
      } catch (error) {
        throw new EvidenceAgentTransportError(`Invalid evidence run SSE JSON: ${String(error)}`, response.status, message.data);
      }
      const frame = SseFrameSchema.parse(rawFrame);
      if (message.id && Number(message.id) !== frame.cursor) {
        throw new EvidenceAgentTransportError("SSE id and durable cursor disagree.", response.status, rawFrame);
      }
      if (message.event && message.event !== frame.type) {
        throw new EvidenceAgentTransportError("SSE event name and frame type disagree.", response.status, rawFrame);
      }
      if (frame.type === "heartbeat") continue;
      yield normalizeFrame(runId, frame);
    }
  }

  async act(runId: string, rawCommand: RunCommand): Promise<CommandReceipt> {
    const command = RunCommandSchema.parse(rawCommand);
    return this.jsonRequest(
      `/api/v1/evidence-runs/${encodeURIComponent(runId)}/commands`,
      CommandReceiptSchema,
      { method: "POST", body: JSON.stringify(command) }
    );
  }

  private async jsonRequest<T>(path: string, schema: z.ZodType<T>, init: RequestInit): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    const response = await this.fetchResponse(this.url(path), { ...init, headers });
    await ensureOk(response);
    const payload: unknown = await response.json();
    return envelope(schema).parse(payload).data;
  }

  private url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  private async fetchResponse(url: string, init: RequestInit): Promise<Response> {
    try {
      return await this.fetch(url, init);
    } catch (reason) {
      if (reason instanceof Error && reason.name === "AbortError") throw reason;
      throw new EvidenceAgentTransportError(
        "网络连接失败，请检查网络和后端服务后重试。",
        0,
        null,
        { code: "NETWORK_UNAVAILABLE", retryable: true }
      );
    }
  }
}

async function ensureOk(response: Response): Promise<void> {
  if (response.ok) return;
  let payload: unknown = null;
  try {
    payload = await response.clone().json();
  } catch {
    payload = await response.clone().text();
  }
  throw new EvidenceAgentTransportError(
    backendErrorMessage(payload, `研究请求失败（HTTP ${response.status}），请稍后重试或检查后端服务。`),
    response.status,
    payload
  );
}

function normalizeFrame(runId: string, frame: z.output<typeof SseFrameSchema>): RunEvent {
  if (frame.type === "sync") {
    const rawRun = z.record(z.string(), z.unknown()).parse(frame.payload.run);
    const view = RunViewSchema.parse({ schema_version: 1, outcome: null, ...rawRun });
    return RunEventSchema.parse({
      schema_version: 1,
      event_id: `${runId}:${frame.cursor}`,
      cursor: frame.cursor,
      run_id: runId,
      run_version: frame.run_version,
      change: { type: "snapshot", reset: true, view }
    });
  }

  const status = frame.type.startsWith("run.") ? RunStatusSchema.safeParse(frame.type.slice(4)) : undefined;
  return RunEventSchema.parse({
    schema_version: 1,
    event_id: `${runId}:${frame.cursor}`,
    cursor: frame.cursor,
    run_id: runId,
    run_version: frame.run_version,
    change: status?.success
      ? { type: "status_changed", status: status.data }
      : { type: "domain_event", event_type: frame.type, payload: frame.payload }
  });
}

type SseMessage = { id?: string; event?: string; data: string };

async function* decodeSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const message = parseSseBlock(block);
        if (message) yield message;
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const message = parseSseBlock(buffer);
      if (message) yield message;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSseBlock(block: string): SseMessage | null {
  let id: string | undefined;
  let event: string | undefined;
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    const value = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") id = value;
    else if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { id, event, data: data.join("\n") } : null;
}
