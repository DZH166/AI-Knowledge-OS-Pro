import type { MultimodalChunk, SourceItem, SourceRevision } from "@/types/api";

const SHA256 = /^[0-9a-f]{64}$/i;
const IMMUTABLE_KEYS = ["revision", "index_revision", "hash", "revision_hash"] as const;

type SearchParams = Pick<URLSearchParams, "get" | "has">;

export type ImmutableEvidencePin = {
  sourceId: number;
  revisionId: number;
  indexRevisionId?: number;
  chunkId: number;
  contentHash: string;
  revisionContentHash?: string;
};

export type ImmutableEvidencePinState =
  | { mode: "current" }
  | { mode: "invalid"; error: string }
  | { mode: "pinned"; pin: ImmutableEvidencePin };

export type ImmutableEvidenceResolution =
  | { ok: false; error: string }
  | {
      ok: true;
      historical: boolean;
      revision: SourceRevision;
      chunk: MultimodalChunk;
    };

export type MediaTimestampState =
  | { mode: "absent" }
  | { mode: "invalid"; error: string }
  | { mode: "valid"; milliseconds: number };

export function parseImmutableEvidencePin(params: SearchParams): ImmutableEvidencePinState {
  if (!IMMUTABLE_KEYS.some((key) => params.has(key))) return { mode: "current" };

  const sourceId = positiveInteger(params.get("source"));
  const revisionId = positiveInteger(params.get("revision"));
  const indexRevisionId = optionalPositiveInteger(params.get("index_revision"));
  const chunkId = positiveInteger(params.get("chunk"));
  const contentHash = sha256(params.get("hash"));
  const revisionContentHash = optionalSha256(params.get("revision_hash"));
  if (sourceId === null || revisionId === null || chunkId === null || contentHash === null) {
    return { mode: "invalid", error: "固定证据地址必须同时包含合法的 source、revision、chunk 与 SHA-256 hash。" };
  }
  if (params.has("index_revision") && indexRevisionId === null) {
    return { mode: "invalid", error: "固定证据地址中的 index_revision 无效。" };
  }
  if (params.has("revision_hash") && revisionContentHash === null) {
    return { mode: "invalid", error: "固定证据地址中的 revision_hash 无效。" };
  }
  return {
    mode: "pinned",
    pin: {
      sourceId,
      revisionId,
      ...(indexRevisionId === null ? {} : { indexRevisionId }),
      chunkId,
      contentHash,
      ...(revisionContentHash === null ? {} : { revisionContentHash })
    }
  };
}

export function resolveImmutableEvidence(
  source: SourceItem,
  pin: ImmutableEvidencePin
): ImmutableEvidenceResolution {
  if (source.id !== pin.sourceId) return failure("来源编号与固定证据不一致。");
  const revision = source.revisions.find((candidate) => candidate.id === pin.revisionId);
  if (!revision || revision.source_id !== source.id) return failure("指定 revision 不存在于该来源。");
  if (pin.revisionContentHash && !sameHash(revision.content_hash, pin.revisionContentHash)) {
    return failure("revision 内容哈希校验失败。");
  }
  if (pin.indexRevisionId !== undefined) {
    const indexRevision = revision.index_revisions?.find((candidate) => candidate.id === pin.indexRevisionId);
    if (!indexRevision || indexRevision.source_id !== source.id || indexRevision.revision_id !== revision.id) {
      return failure("index revision 不属于固定的 source revision。");
    }
  }
  const chunk = revision.chunks.find((candidate) => candidate.id === pin.chunkId);
  if (!chunk || chunk.source_id !== source.id || chunk.revision_id !== revision.id) {
    return failure("指定 canonical chunk 不存在于固定 revision。");
  }
  if (!sameHash(chunk.content_hash, pin.contentHash)) return failure("chunk 内容哈希校验失败。");
  return { ok: true, historical: source.active_revision_id !== revision.id, revision, chunk };
}

export function matchesImmutableMediaTime(chunk: MultimodalChunk, rawTimestamp: string | null): boolean {
  const parsedTimestamp = parseMediaTimestamp(rawTimestamp);
  if (parsedTimestamp.mode !== "valid") return false;
  const timestamp = parsedTimestamp.milliseconds;

  let start = nonNegativeInteger(chunk.start_ms);
  let end = nonNegativeInteger(chunk.end_ms);
  try {
    const raw: unknown = JSON.parse(chunk.locator_json);
    if (raw && typeof raw === "object") {
      const locator = raw as Record<string, unknown>;
      start ??= nonNegativeInteger(locator.start_ms) ?? nonNegativeInteger(locator.timestamp_ms);
      end ??= nonNegativeInteger(locator.end_ms);
    }
  } catch {
    return false;
  }
  if (start === null) return false;
  return timestamp >= start && timestamp <= (end ?? start);
}

export function parseMediaTimestamp(rawTimestamp: string | null): MediaTimestampState {
  if (rawTimestamp === null) return { mode: "absent" };
  if (!/^\d+$/.test(rawTimestamp)) {
    return { mode: "invalid", error: "媒体时间参数 t 必须是非负整数（毫秒）。" };
  }
  const milliseconds = Number(rawTimestamp);
  if (!Number.isSafeInteger(milliseconds) || milliseconds < 0) {
    return { mode: "invalid", error: "媒体时间参数 t 必须是非负整数（毫秒）。" };
  }
  return { mode: "valid", milliseconds };
}

function failure(error: string): ImmutableEvidenceResolution {
  return { ok: false, error };
}

function positiveInteger(value: string | null): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : null;
}

function optionalPositiveInteger(value: string | null): number | null {
  return value === null ? null : positiveInteger(value);
}

function sha256(value: string | null): string | null {
  return value && SHA256.test(value) ? value.toLowerCase() : null;
}

function optionalSha256(value: string | null): string | null {
  return value === null ? null : sha256(value);
}

function sameHash(actual: string | null | undefined, expected: string): boolean {
  return typeof actual === "string" && actual.toLowerCase() === expected.toLowerCase();
}

function nonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
}
