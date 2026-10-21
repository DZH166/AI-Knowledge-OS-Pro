import type { KnowledgeSpace, SourceItem, SourceRevision } from "@/types/api";
import { RECORDING_FIXTURE } from "@/modules/evidence-agent/recording-fixture";

const syntheticCreatedAt = "2026-08-15T10:00:00.000Z";

export const RECORDING_SPACES: KnowledgeSpace[] = [
  {
    id: 9_001,
    name: "Synthetic · Evidence Agent 产品研究",
    description: "Recording Demo 专用的确定性知识空间，不对应真实资料。",
    created_at: syntheticCreatedAt,
    updated_at: syntheticCreatedAt,
    document_count: 3,
    chunk_count: 28,
    qa_count: 0
  },
  {
    id: 9_002,
    name: "Synthetic · 架构核验样本",
    description: "用于展示切换空间后清空旧来源选择。",
    created_at: syntheticCreatedAt,
    updated_at: syntheticCreatedAt,
    document_count: 1,
    chunk_count: 12,
    qa_count: 0
  }
];

export const RECORDING_SOURCES: SourceItem[] = [
  syntheticSource(RECORDING_FIXTURE.spaces.research, RECORDING_FIXTURE.sources.contract, 18, 18),
  syntheticSource(RECORDING_FIXTURE.spaces.research, RECORDING_FIXTURE.sources.runtime, 10, 10),
  syntheticSource(RECORDING_FIXTURE.spaces.architecture, RECORDING_FIXTURE.sources.code, 12, 12)
];

export function sourceTitle(source: SourceItem): string {
  return source.title || source.original_filename || `Source #${source.id}`;
}

export function sourceTypeLabel(sourceType: string): string {
  return ({
    document: "文档",
    text: "文本",
    image: "图片",
    audio: "音频",
    video: "视频",
    code: "代码仓库",
    code_repository: "代码仓库"
  } as Record<string, string>)[sourceType] ?? sourceType;
}

export function activeSourceRevision(source: SourceItem): SourceRevision | null {
  if (source.active_revision_id === null) return null;
  return source.revisions.find((revision) => revision.id === source.active_revision_id) ?? null;
}

export function sourceIndexSummary(source: SourceItem): string {
  const revision = activeSourceRevision(source);
  if (!revision) return "未建立 active index";
  return `${revision.validation_status} · ${revision.vector_count} vectors`;
}

function syntheticSource(
  spaceId: number,
  fixture: typeof RECORDING_FIXTURE.sources[keyof typeof RECORDING_FIXTURE.sources],
  chunkCount: number,
  vectorCount: number
): SourceItem {
  const { chunkId, contentHash, excerpt, indexRevisionId, locator, revisionId, sourceId, sourceType, title } = fixture;
  const code = sourceType === "code_repository";
  return {
    id: sourceId,
    space_id: spaceId,
    document_id: null,
    source_type: sourceType,
    title,
    original_filename: title,
    mime_type: code ? "application/x-git" : "text/plain",
    file_size: 42_000,
    storage_path: null,
    content_hash: "a".repeat(64),
    status: "active",
    language: code ? "typescript" : "zh-CN",
    duration_ms: null,
    page_count: sourceType === "document" ? 12 : null,
    width: null,
    height: null,
    metadata_json: JSON.stringify({ synthetic: true }),
    active_revision_id: revisionId,
    latest_revision_id: revisionId,
    active_index_revision_id: indexRevisionId,
    media_assets: [],
    revisions: [
      {
        id: revisionId,
        source_id: sourceId,
        revision_number: 1,
        status: "active",
        parser_name: code ? "tree-sitter" : "recording-parser",
        parser_version: "1",
        content_hash: "b".repeat(64),
        chunk_count: chunkCount,
        vector_count: vectorCount,
        validation_status: "passed",
        error_message: null,
        metadata_json: JSON.stringify({ synthetic: true }),
        activated_at: syntheticCreatedAt,
        index_revisions: [{
          id: indexRevisionId,
          source_id: sourceId,
          revision_id: revisionId,
          status: "active",
          index_version: "recording-v1"
        }],
        chunks: [{
          id: chunkId,
          source_id: sourceId,
          revision_id: revisionId,
          chunk_index: 0,
          modality: code ? "code_file" : "text",
          source_type: sourceType,
          content_text: excerpt,
          content_hash: contentHash,
          search_text: excerpt,
          locator_json: JSON.stringify(locator),
          start_ms: null,
          end_ms: null,
          page_number: "page_number" in locator ? locator.page_number : null,
          slide_number: null,
          frame_id: null,
          status: "active",
          qdrant_point_id: `recording-${chunkId}`,
          created_at: syntheticCreatedAt
        }],
        transcript_segments: [],
        visual_frames: []
      }
    ],
    created_at: syntheticCreatedAt,
    updated_at: syntheticCreatedAt
  };
}
