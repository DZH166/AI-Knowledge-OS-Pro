export type EvidenceSourceLocation = {
  sourceId: number;
  revisionId: number;
  indexRevisionId?: number;
  chunkId: number;
  contentHash: string;
  revisionContentHash?: string;
  sourceType: string;
  locator: Record<string, unknown>;
  demo?: boolean;
};

const DOCUMENT_TYPES = new Set(["document", "markdown", "pdf", "text"]);
const MEDIA_TYPES = new Set(["audio", "video", "image"]);

export function catalogSourceHref(source: {
  sourceId: number;
  sourceType: string;
  documentId: number | null;
  demo?: boolean;
}): string {
  const sourceType = source.sourceType.toLowerCase();
  if (source.demo) return `/library?demo=1&source=${encodeURIComponent(source.sourceId)}`;
  if (DOCUMENT_TYPES.has(sourceType) && source.documentId) return `/documents/${source.documentId}`;
  if (isCodeSourceType(sourceType)) return `/code?source=${encodeURIComponent(source.sourceId)}`;
  if (MEDIA_TYPES.has(sourceType)) return `/media/sources/${source.sourceId}`;
  return `/library?source=${encodeURIComponent(source.sourceId)}`;
}

export function evidenceSourceHref(location: EvidenceSourceLocation): string {
  const { sourceId, revisionId, indexRevisionId, chunkId, contentHash, revisionContentHash, locator } = location;
  const sourceType = location.sourceType.toLowerCase();
  const kind = typeof locator.kind === "string" ? locator.kind.toLowerCase() : "";
  const pinnedParams = new URLSearchParams();
  if (location.demo) pinnedParams.set("demo", "1");
  pinnedParams.set("source", String(sourceId));
  pinnedParams.set("revision", String(revisionId));
  if (indexRevisionId !== undefined) pinnedParams.set("index_revision", String(indexRevisionId));
  pinnedParams.set("chunk", String(chunkId));
  pinnedParams.set("hash", contentHash);
  if (revisionContentHash) pinnedParams.set("revision_hash", revisionContentHash);

  if (!location.demo && (isCodeSourceType(sourceType) || kind === "code" || kind === "code_range")) {
    const filePath = text(locator.file_path);
    const lineStart = positiveInteger(locator.line_start);
    if (filePath && lineStart) {
      const params = new URLSearchParams(pinnedParams);
      params.set("file", filePath);
      params.set("line", String(lineStart));
      const lineEnd = positiveInteger(locator.line_end);
      if (lineEnd) params.set("line_end", String(Math.max(lineStart, lineEnd)));
      return `/code?${params.toString()}`;
    }
  }

  if (!location.demo && (DOCUMENT_TYPES.has(sourceType) || kind.startsWith("document") || kind === "pdf_page" || kind === "page")) {
    const documentId = positiveInteger(locator.document_id);
    if (documentId) {
      const params = new URLSearchParams();
      const page = positiveInteger(locator.page_number) ?? positiveInteger(locator.page);
      if (page) params.set("page", String(page));
      appendParams(params, pinnedParams);
      return `/documents/${documentId}?${params.toString()}`;
    }
  }

  if (!location.demo && (MEDIA_TYPES.has(sourceType) || kind === "media_time" || kind === "image_region" || kind === "time")) {
    const params = new URLSearchParams();
    const startMs = nonNegativeInteger(locator.start_ms) ?? nonNegativeInteger(locator.timestamp_ms);
    if (startMs !== null) params.set("t", String(startMs));
    appendParams(params, pinnedParams);
    return `/media/sources/${sourceId}?${params.toString()}`;
  }

  return `/library?${pinnedParams.toString()}`;
}

export function isCodeSourceType(sourceType: string): boolean {
  const normalized = sourceType.trim().toLowerCase();
  return normalized === "code" || normalized === "code_repository";
}

function appendParams(target: URLSearchParams, source: URLSearchParams): void {
  source.forEach((value, key) => target.set(key, value));
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function positiveInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
}

function nonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}
