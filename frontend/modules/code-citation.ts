import type { MultimodalChunk, SourceItem, SourceRevision } from "@/types/api";
import {
  resolveImmutableEvidence,
  type ImmutableEvidencePin
} from "@/modules/evidence-agent/immutable-evidence";

type CodeLocator = {
  file_path: string;
  line_start: number;
  line_end: number;
  language?: string;
  symbol_name?: string | null;
};

export type CodeExcerptLine = { number: number; text: string; highlighted: boolean };
export type CodeLocation = {
  chunkId: number;
  filePath: string;
  language: string;
  lineStart: number;
  lineEnd: number;
  revisionId: number;
};
export type CodeExcerpt = {
  exact: boolean;
  filePath: string;
  language: string;
  lines: CodeExcerptLine[];
  chunkId: number;
  historical: boolean;
  revisionId: number;
  sourceId: number;
  sourceTitle: string;
};

export function listCodeLocations(source: SourceItem): CodeLocation[] {
  const revision = selectedRevision(source);
  if (!revision) return [];
  return revision.chunks
    .map((chunk) => ({ chunk, locator: parseCodeLocator(chunk) }))
    .filter((item): item is { chunk: MultimodalChunk; locator: CodeLocator } => item.locator !== null)
    .map(({ chunk, locator }) => ({
      chunkId: chunk.id,
      filePath: normalizePath(locator.file_path),
      language: locator.language || source.language || "text",
      lineStart: locator.line_start,
      lineEnd: locator.line_end,
      revisionId: revision.id
    }))
    .sort((left, right) => left.filePath.localeCompare(right.filePath) || left.lineStart - right.lineStart);
}

export function buildCodeExcerpt(
  source: SourceItem,
  requestedFilePath: string,
  requestedLineStart: number,
  requestedLineEnd: number
): CodeExcerpt | null {
  const revision = selectedRevision(source);
  if (!revision) return null;
  const filePath = normalizePath(requestedFilePath);
  const fileChunks = revision.chunks
    .map((chunk) => ({ chunk, locator: parseCodeLocator(chunk) }))
    .filter((item): item is { chunk: MultimodalChunk; locator: CodeLocator } => item.locator !== null)
    .filter((item) => normalizePath(item.locator.file_path) === filePath)
    .sort((left, right) => left.locator.line_start - right.locator.line_start);
  if (fileChunks.length === 0) return null;

  const lineStart = positiveLine(requestedLineStart, fileChunks[0].locator.line_start);
  const lineEnd = Math.max(lineStart, positiveLine(requestedLineEnd, lineStart));
  const overlapping = fileChunks.filter(({ locator }) => locator.line_start <= lineEnd && locator.line_end >= lineStart);
  const exact = overlapping.length > 0;
  const selected = exact ? overlapping : [fileChunks[0]];
  const linesByNumber = new Map<number, CodeExcerptLine>();

  for (const { chunk, locator } of selected) {
    const codeLines = codeText(chunk.content_text).split("\n");
    const expectedLength = Math.max(1, locator.line_end - locator.line_start + 1);
    for (const [index, text] of codeLines.slice(0, expectedLength).entries()) {
      const number = locator.line_start + index;
      linesByNumber.set(number, {
        number,
        text,
        highlighted: exact && number >= lineStart && number <= lineEnd
      });
    }
  }

  const firstLocator = selected[0].locator;
  return {
    exact,
    filePath: normalizePath(firstLocator.file_path),
    language: firstLocator.language || source.language || "text",
    lines: [...linesByNumber.values()].sort((left, right) => left.number - right.number),
    chunkId: selected[0].chunk.id,
    historical: source.active_revision_id !== revision.id,
    revisionId: revision.id,
    sourceId: source.id,
    sourceTitle: source.title || source.original_filename || `Source #${source.id}`
  };
}

export function buildPinnedCodeExcerpt(
  source: SourceItem,
  request: {
    pin: ImmutableEvidencePin;
    filePath: string;
    lineStart: number;
    lineEnd: number;
  }
): CodeExcerpt | null {
  const resolved = resolveImmutableEvidence(source, request.pin);
  if (!resolved.ok) return null;
  const locator = parseCodeLocator(resolved.chunk);
  if (!locator || normalizePath(locator.file_path) !== normalizePath(request.filePath)) return null;
  const lineStart = positiveLine(request.lineStart, 0);
  const lineEnd = Math.max(lineStart, positiveLine(request.lineEnd, lineStart));
  if (lineStart < locator.line_start || lineEnd > locator.line_end) return null;

  const codeLines = codeText(resolved.chunk.content_text).split("\n");
  const expectedLength = Math.max(1, locator.line_end - locator.line_start + 1);
  const lines = codeLines.slice(0, expectedLength).map((text, index) => {
    const number = locator.line_start + index;
    return { number, text, highlighted: number >= lineStart && number <= lineEnd };
  });
  if (!lines.some((line) => line.highlighted)) return null;

  return {
    exact: true,
    filePath: normalizePath(locator.file_path),
    language: locator.language || source.language || "text",
    lines,
    chunkId: resolved.chunk.id,
    historical: resolved.historical,
    revisionId: resolved.revision.id,
    sourceId: source.id,
    sourceTitle: source.title || source.original_filename || `Source #${source.id}`
  };
}

function selectedRevision(source: SourceItem): SourceRevision | null {
  const active = source.revisions.find((revision) => revision.id === source.active_revision_id);
  if (active) return active;
  const latest = source.revisions.find((revision) => revision.id === source.latest_revision_id);
  return latest ?? source.revisions[0] ?? null;
}

function parseCodeLocator(chunk: MultimodalChunk): CodeLocator | null {
  try {
    const raw: unknown = JSON.parse(chunk.locator_json);
    if (!raw || typeof raw !== "object") return null;
    const locator = raw as Record<string, unknown>;
    if (
      typeof locator.file_path !== "string" ||
      typeof locator.line_start !== "number" ||
      !Number.isInteger(locator.line_start) ||
      locator.line_start < 1
    ) return null;
    const lineEnd = typeof locator.line_end === "number" && Number.isInteger(locator.line_end)
      ? Math.max(locator.line_start, locator.line_end)
      : locator.line_start;
    return {
      file_path: locator.file_path,
      line_start: locator.line_start,
      line_end: lineEnd,
      language: typeof locator.language === "string" ? locator.language : undefined,
      symbol_name: typeof locator.symbol_name === "string" ? locator.symbol_name : null
    };
  } catch {
    return null;
  }
}

function codeText(content: string): string {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  if (!lines[0]?.startsWith("File: ") || !lines[1]?.startsWith("Lines: ")) return lines.join("\n");
  const separator = lines.findIndex((line, index) => index >= 2 && index <= 5 && line.trim() === "");
  return lines.slice(separator >= 0 ? separator + 1 : 3).join("\n");
}

function normalizePath(value: string): string {
  return value.trim().replace(/\\/g, "/").replace(/^\.\//, "");
}

function positiveLine(value: number, fallback: number): number {
  return Number.isInteger(value) && value > 0 ? value : fallback;
}
