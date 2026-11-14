import type {
  AnswerMode,
  ApiEnvelope,
  ChatResponse,
  ChatSession,
  CodeRepositoryIngestResponse,
  Chunk,
  DashboardSummary,
  DocumentItem,
  ErrorArchive,
  IngestionJob,
  JobEvent,
  KnowledgeRelation,
  KnowledgeSpace,
  LearningArtifact,
  LearningArtifactType,
  LearningCard,
  LearningDashboard,
  LearningKnowledgePoint,
  LearningLog,
  LearningNote,
  LearningPackage,
  LearningRoadmap,
  MediaOperation,
  MediaTaskResponse,
  ObservabilitySummary,
  OnboardingState,
  PerformanceRequestRecord,
  PerformanceSnapshot,
  PerformanceSummary,
  PortfolioMarkdownResponse,
  PortfolioSummary,
  QALog,
  QuizQuestion,
  SourceItem,
  StorageHealth,
  SystemStatus,
  SystemTestResponse
} from "@/types/api";
import {
  cacheKeyFor,
  clearAllRequestCache,
  clearCacheByPrefix,
  getInFlightRequest,
  readCachedResponse,
  recordRequestCacheMetric,
  setInFlightRequest,
  writeCachedResponse
} from "@/services/request-cache";
import type { ApiRequestOptions } from "@/services/request-cache";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 30000;

export class ApiRequestError extends Error {
  code: string;
  details: Record<string, unknown>;
  retryable: boolean;

  constructor(message: string, options: { code?: string; details?: Record<string, unknown>; retryable?: boolean } = {}) {
    super(message);
    this.name = "ApiRequestError";
    this.code = options.code || "REQUEST_FAILED";
    this.details = options.details || {};
    this.retryable = options.retryable || false;
  }
}

async function request<T>(path: string, init?: RequestInit, options: ApiRequestOptions = {}): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const canCache = method === "GET" && Boolean(options.ttlMs && options.ttlMs > 0);
  const cacheKey = cacheKeyFor(method, path, options);
  const startedAt = performance.now();

  if (canCache && !options.forceRefresh) {
    const cached = readCachedResponse<T>(cacheKey);
    if (cached) {
      recordRequestCacheMetric({
        key: cacheKey,
        path,
        method,
        cache_status: "hit",
        duration_ms: Math.round(performance.now() - startedAt),
        request_id: cached.requestId
      });
      return cached.data;
    }
    const existing = getInFlightRequest<T>(cacheKey);
    if (existing) {
      recordRequestCacheMetric({
        key: cacheKey,
        path,
        method,
        cache_status: "deduped",
        duration_ms: Math.round(performance.now() - startedAt),
        request_id: null
      });
      return existing;
    }
  }

  const promise = performRequest<T>(path, init, options, {
    cacheKey,
    cacheStatus: canCache ? (options.forceRefresh ? "refresh" : "miss") : "bypass",
    method,
    startedAt
  });
  if (canCache) setInFlightRequest(cacheKey, promise);
  return promise;
}

async function performRequest<T>(
  path: string,
  init: RequestInit | undefined,
  options: ApiRequestOptions,
  meta: { method: string; cacheKey: string; cacheStatus: "miss" | "refresh" | "bypass"; startedAt: number }
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || REQUEST_TIMEOUT_MS);
  const requestId = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers:
        init?.body instanceof FormData
          ? { ...init.headers, "x-request-id": requestId, "x-client-cache-status": meta.cacheStatus }
          : { "Content-Type": "application/json", ...init?.headers, "x-request-id": requestId, "x-client-cache-status": meta.cacheStatus },
      cache: "no-store",
      signal: init?.signal ?? controller.signal
    });
  } catch (exc) {
    recordRequestCacheMetric({
      key: meta.cacheKey,
      path,
      method: meta.method,
      cache_status: "error",
      duration_ms: Math.round(performance.now() - meta.startedAt),
      request_id: requestId
    });
    if (exc instanceof Error && exc.name === "AbortError") {
      throw new Error("请求超时，请检查后端服务状态后重试。");
    }
    throw exc;
  } finally {
    clearTimeout(timeout);
  }

  const raw = await response.text();
  const parsed = raw ? safeParseJson(raw) : null;
  const payload = isRecord(parsed) ? parsed : null;

  if (!response.ok) {
    recordRequestCacheMetric({
      key: meta.cacheKey,
      path,
      method: meta.method,
      cache_status: "error",
      duration_ms: Math.round(performance.now() - meta.startedAt),
      request_id: getNestedString(payload, ["error", "request_id"]) || requestId
    });
    const userMessage =
      getNestedString(payload, ["error", "user_message"]) ||
      getNestedString(payload, ["detail", "user_message"]) ||
      getNestedString(payload, ["detail", "message"]) ||
      getString(payload?.detail) ||
      `请求失败：${response.status}`;
    const errorData = isRecord(payload?.error) ? payload.error : isRecord(payload?.detail) ? payload.detail : {};
    throw new ApiRequestError(userMessage, {
      code: getString(errorData.code) || "REQUEST_FAILED",
      details: isRecord(errorData.details) ? errorData.details : {},
      retryable: Boolean(errorData.retryable)
    });
  }

  if (payload && "success" in payload && "data" in payload) {
    const envelope = payload as ApiEnvelope<T>;
    if (!envelope.success) {
      throw new ApiRequestError(envelope.error?.user_message || "请求失败", {
        code: envelope.error?.code,
        details: envelope.error?.details,
        retryable: envelope.error?.retryable
      });
    }
    if (meta.method === "GET" && options.ttlMs && options.ttlMs > 0) {
      writeCachedResponse(meta.cacheKey, envelope.data, options.ttlMs, envelope.request_id || requestId);
    }
    if (meta.method !== "GET") {
      clearCacheByPrefix(options.cachePrefix || "");
      if (!options.cachePrefix) clearAllRequestCache();
    }
    recordRequestCacheMetric({
      key: meta.cacheKey,
      path,
      method: meta.method,
      cache_status: meta.cacheStatus,
      duration_ms: Math.round(performance.now() - meta.startedAt),
      request_id: envelope.request_id || requestId
    });
    return envelope.data;
  }

  if (meta.method !== "GET") {
    clearCacheByPrefix(options.cachePrefix || "");
    if (!options.cachePrefix) clearAllRequestCache();
  }
  recordRequestCacheMetric({
    key: meta.cacheKey,
    path,
    method: meta.method,
    cache_status: meta.cacheStatus,
    duration_ms: Math.round(performance.now() - meta.startedAt),
    request_id: requestId
  });
  return parsed as T;
}

function safeParseJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return { detail: raw || "服务返回了无法解析的响应。" };
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function getNestedString(value: Record<string, unknown> | null, path: string[]): string | null {
  let current: unknown = value;
  for (const key of path) {
    if (!isRecord(current)) return null;
    current = current[key];
  }
  return getString(current);
}

export const api = {
  dashboard: (options?: ApiRequestOptions) => request<DashboardSummary>("/api/dashboard/summary", undefined, { ttlMs: 10000, ...options }),
  onboarding: () => request<OnboardingState>("/api/onboarding"),
  updateOnboarding: (payload: { steps?: Record<string, boolean>; dismissed?: boolean }) =>
    request<OnboardingState>("/api/onboarding", {
      method: "PATCH",
      body: JSON.stringify({ steps: payload.steps || {}, dismissed: payload.dismissed })
    }),
  resetOnboarding: () => request<OnboardingState>("/api/onboarding/reset", { method: "POST" }),
  systemStatus: (options?: ApiRequestOptions) => request<SystemStatus>("/api/system/status", undefined, { ttlMs: 10000, ...options }),
  storageHealth: (options?: ApiRequestOptions & { deepHash?: boolean; scanOrphans?: boolean }) => {
    const query = new URLSearchParams();
    if (options?.deepHash) query.set("deep_hash", "true");
    if (options?.scanOrphans === false) query.set("scan_orphans", "false");
    const suffix = query.size ? `?${query.toString()}` : "";
    return request<StorageHealth>(`/api/system/storage-health${suffix}`, undefined, { ttlMs: 0, ...options });
  },
  observability: (options?: ApiRequestOptions) => request<ObservabilitySummary>("/api/system/observability", undefined, { ttlMs: 5000, ...options }),
  performance: (options?: ApiRequestOptions) => request<PerformanceSnapshot>("/api/system/performance", undefined, { ttlMs: 5000, ...options }),
  performanceRecent: (options?: ApiRequestOptions) => request<PerformanceRequestRecord[]>("/api/system/performance/recent", undefined, { ttlMs: 5000, ...options }),
  performanceSlow: (options?: ApiRequestOptions) => request<PerformanceRequestRecord[]>("/api/system/performance/slow", undefined, { ttlMs: 5000, ...options }),
  performanceSummary: (options?: ApiRequestOptions) => request<PerformanceSummary>("/api/system/performance/summary", undefined, { ttlMs: 5000, ...options }),
  testLlm: () => request<SystemTestResponse>("/api/system/test-llm", { method: "POST" }),
  testEmbedding: () => request<SystemTestResponse>("/api/system/test-embedding", { method: "POST" }),
  testQdrant: () => request<SystemTestResponse>("/api/system/test-qdrant", { method: "POST" }),
  listSpaces: () => request<KnowledgeSpace[]>("/api/knowledge-spaces"),
  createSpace: (payload: { name: string; description?: string }) =>
    request<KnowledgeSpace>("/api/knowledge-spaces", { method: "POST", body: JSON.stringify(payload) }),
  listDocuments: (spaceId?: number) => request<DocumentItem[]>(spaceId ? `/api/documents?space_id=${spaceId}` : "/api/documents"),
  getDocument: (documentId: number) => request<DocumentItem>(`/api/documents/${documentId}`),
  getDocumentChunks: (documentId: number) => request<Chunk[]>(`/api/documents/${documentId}/chunks`),
  updateDocument: (documentId: number, payload: { title?: string; tags?: string[]; summary?: string }) =>
    request<DocumentItem>(`/api/documents/${documentId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteDocument: (documentId: number) =>
    request<{ document: DocumentItem | null; message: string; job_id?: number }>(`/api/documents/${documentId}`, { method: "DELETE" }),
  bulkDeleteDocuments: (document_ids: number[]) =>
    request<{ affected_count: number; job_ids: number[]; message: string }>("/api/documents/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ document_ids })
    }),
  bulkReindexDocuments: (document_ids: number[]) =>
    request<{ affected_count: number; job_ids: number[]; message: string }>("/api/documents/bulk-reindex", {
      method: "POST",
      body: JSON.stringify({ document_ids })
    }),
  bulkTags: (document_ids: number[], tags: string[]) =>
    request<{ affected_count: number; job_ids: number[]; message: string }>("/api/documents/bulk-tags", {
      method: "POST",
      body: JSON.stringify({ document_ids, tags })
    }),
  retryDocument: (documentId: number) =>
    request<{ document: DocumentItem; message: string; job_id: number }>(`/api/documents/${documentId}/retry`, { method: "POST" }),
  reparseDocument: (documentId: number) =>
    request<{ document: DocumentItem; message: string; job_id: number }>(`/api/documents/${documentId}/reparse`, { method: "POST" }),
  reindexDocument: (documentId: number) =>
    request<{ document: DocumentItem; message: string; job_id: number }>(`/api/documents/${documentId}/reindex`, { method: "POST" }),
  listIngestionJobs: (spaceId?: number, targetType?: string) => {
    const params = new URLSearchParams();
    if (spaceId) params.set("space_id", String(spaceId));
    if (targetType) params.set("target_type", targetType);
    const query = params.toString();
    return request<IngestionJob[]>(query ? `/api/ingestion-jobs?${query}` : "/api/ingestion-jobs");
  },
  getIngestionJob: (jobId: number) => request<IngestionJob>(`/api/ingestion-jobs/${jobId}`),
  getIngestionJobEvents: (jobId: number) => request<JobEvent[]>(`/api/ingestion-jobs/${jobId}/events`),
  retryIngestionJob: (jobId: number) => request<IngestionJob>(`/api/ingestion-jobs/${jobId}/retry`, { method: "POST" }),
  cancelIngestionJob: (jobId: number) => request<IngestionJob>(`/api/ingestion-jobs/${jobId}/cancel`, { method: "POST" }),
  uploadDocument: (spaceId: number, file: File) => {
    const formData = new FormData();
    formData.append("space_id", String(spaceId));
    formData.append("file", file);
    return request<{ document: DocumentItem; message: string; job_id: number | null }>("/api/documents/upload", {
      method: "POST",
      body: formData
    });
  },
  uploadImage: (spaceId: number, file: File) => {
    const formData = new FormData();
    formData.append("space_id", String(spaceId));
    formData.append("file", file);
    return request<{ source: SourceItem; message: string; job_id?: number | null }>("/api/media/images/upload", {
      method: "POST",
      body: formData
    });
  },
  uploadAudio: (spaceId: number, file: File) => {
    const formData = new FormData();
    formData.append("space_id", String(spaceId));
    formData.append("file", file);
    return request<{ source: SourceItem; message: string; job_id?: number | null }>("/api/media/audio/upload", {
      method: "POST",
      body: formData
    });
  },
  uploadVideo: (spaceId: number, file: File) => {
    const formData = new FormData();
    formData.append("space_id", String(spaceId));
    formData.append("file", file);
    return request<{ source: SourceItem; message: string; job_id?: number | null }>("/api/media/video/upload", {
      method: "POST",
      body: formData
    });
  },
  ingestCodeRepository: (payload: { space_id: number; local_path: string; title?: string; github_url?: string; max_files?: number }) =>
    request<CodeRepositoryIngestResponse>("/api/code-repositories/ingest-local", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listCodeRepositories: (spaceId?: number) => {
    const params = new URLSearchParams();
    if (spaceId) params.set("space_id", String(spaceId));
    const query = params.toString();
    return request<SourceItem[]>(query ? `/api/code-repositories?${query}` : "/api/code-repositories");
  },
  getCodeRepository: (sourceId: number) => request<SourceItem>(`/api/code-repositories/${sourceId}`),
  listSources: (spaceId?: number, sourceType?: string) => {
    const params = new URLSearchParams();
    if (spaceId) params.set("space_id", String(spaceId));
    if (sourceType) params.set("source_type", sourceType);
    const query = params.toString();
    return request<SourceItem[]>(query ? `/api/media/sources?${query}` : "/api/media/sources");
  },
  getSource: (sourceId: number) => request<SourceItem>(`/api/media/sources/${sourceId}`),
  processMedia: (sourceId: number, operation: MediaOperation) =>
    request<MediaTaskResponse>(`/api/media/sources/${sourceId}/process`, {
      method: "POST",
      body: JSON.stringify({ operation })
    }),
  runImageOcr: (sourceId: number) => request<MediaTaskResponse>(`/api/media/sources/${sourceId}/ocr`, { method: "POST" }),
  transcribeMedia: (sourceId: number) => request<MediaTaskResponse>(`/api/media/sources/${sourceId}/transcribe`, { method: "POST" }),
  transcribeAudio: (sourceId: number) => request<MediaTaskResponse>(`/api/media/sources/${sourceId}/transcribe`, { method: "POST" }),
  listErrors: (filters?: { spaceId?: number; sourceId?: number; status?: string }) => {
    const params = new URLSearchParams();
    if (filters?.spaceId) params.set("space_id", String(filters.spaceId));
    if (filters?.sourceId) params.set("source_id", String(filters.sourceId));
    if (filters?.status) params.set("archive_status", filters.status);
    const query = params.toString();
    return request<ErrorArchive[]>(query ? `/api/errors?${query}` : "/api/errors");
  },
  extractErrorFromSource: (sourceId: number) =>
    request<{ archive: ErrorArchive; created: boolean; message: string }>(`/api/errors/from-source/${sourceId}`, { method: "POST" }),
  updateErrorArchive: (archiveId: number, payload: { status?: string; resolution_notes?: string; tags?: string[] }) =>
    request<ErrorArchive>(`/api/errors/${archiveId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  ask: (payload: { space_id: number; question: string; answer_mode: AnswerMode }) =>
    request<ChatResponse>("/api/chat/ask", { method: "POST", body: JSON.stringify(payload) }),
  history: (spaceId?: number) => request<QALog[]>(spaceId ? `/api/chat/history?space_id=${spaceId}` : "/api/chat/history"),
  createChatSession: (payload: { space_id: number; title?: string; answer_mode?: AnswerMode }) =>
    request<ChatSession>("/api/chat/sessions", { method: "POST", body: JSON.stringify(payload) }),
  listChatSessions: (spaceId?: number) => request<ChatSession[]>(spaceId ? `/api/chat/sessions?space_id=${spaceId}` : "/api/chat/sessions"),
  getChatSession: (id: number) => request<ChatSession>(`/api/chat/sessions/${id}`),
  askInSession: (sessionId: number, payload: { question: string; answer_mode?: AnswerMode }) =>
    request<ChatResponse>(`/api/chat/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify(payload) }),
  regenerateMessage: (messageId: number) => request<ChatResponse>(`/api/chat/messages/${messageId}/regenerate`, { method: "POST" }),
  favoriteMessage: (messageId: number) =>
    request<{ message_id: number; is_favorite: boolean }>(`/api/chat/messages/${messageId}/favorite`, { method: "POST" }),
  learningDashboard: (options?: ApiRequestOptions) => request<LearningDashboard>("/api/learning/dashboard", undefined, { ttlMs: 10000, ...options }),
  learningRoadmap: () => request<LearningRoadmap>("/api/learning/roadmap"),
  knowledgeGraph: () => request<KnowledgeRelation[]>("/api/learning/knowledge-graph"),
  learningLogs: () => request<LearningLog[]>("/api/learning/logs"),
  learningVersions: () => request<LearningLog[]>("/api/learning/versions"),
  learningLog: (slug: string) => request<LearningLog>(`/api/learning/logs/${slug}`),
  generateLearningPackageDraft: () => request<LearningPackage>("/api/learning/packages/generate-draft", { method: "POST" }),
  learningPackages: () => request<LearningPackage[]>("/api/learning/packages"),
  learningPackage: (slug: string) => request<LearningPackage>(`/api/learning/packages/${slug}`),
  confirmLearningPackage: (slug: string) => request<LearningPackage>(`/api/learning/packages/${slug}/confirm`, { method: "POST" }),
  knowledgePoints: () => request<LearningKnowledgePoint[]>("/api/learning/knowledge-points"),
  knowledgePoint: (id: number) => request<LearningKnowledgePoint>(`/api/learning/knowledge-points/${id}`),
  updateKnowledgePointProgress: (id: number, payload: { mastery_status: string; note?: string }) =>
    request<LearningKnowledgePoint>(`/api/learning/knowledge-points/${id}/progress`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  addKnowledgePointNote: (id: number, note: string) =>
    request<LearningKnowledgePoint>(`/api/learning/knowledge-points/${id}/notes`, { method: "POST", body: JSON.stringify({ note }) }),
  learningCards: () => request<LearningCard[]>("/api/learning/cards"),
  updateLearningCardProgress: (id: number, mastery_status: string) =>
    request<LearningCard>(`/api/learning/cards/${id}/progress`, { method: "PATCH", body: JSON.stringify({ mastery_status }) }),
  reviewLearningCard: (id: number, mastery_status: string) =>
    request<LearningCard>(`/api/learning/cards/${id}/review`, { method: "POST", body: JSON.stringify({ mastery_status }) }),
  quizzes: () => request<QuizQuestion[]>("/api/learning/quizzes"),
  answerQuiz: (id: number, answer: string) =>
    request<{ correct: boolean; correct_answer: string; explanation: string }>(`/api/learning/quizzes/${id}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer })
    }),
  learningNotes: () => request<LearningNote[]>("/api/learning/notes"),
  createLearningNote: (payload: {
    title: string;
    content: string;
    tags?: string[];
    knowledge_point_id?: number | null;
    document_id?: number | null;
    qa_log_id?: number | null;
    version_slug?: string | null;
  }) => request<LearningNote>("/api/learning/notes", { method: "POST", body: JSON.stringify(payload) }),
  createLearningArtifacts: (payload: {
    source_id?: number;
    document_id?: number;
    chunk_id?: number;
    artifact_types: LearningArtifactType[];
    title?: string;
  }) =>
    request<{ artifacts: LearningArtifact[]; message: string }>("/api/learning/from-source", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportLearningMarkdown: () => request<{ markdown: string; message: string }>("/api/learning/export-markdown", { method: "POST" }),
  portfolioSummary: (options?: ApiRequestOptions) => request<PortfolioSummary>("/api/portfolio/summary", undefined, { ttlMs: 30000, ...options }),
  generatePortfolioResumeEntry: () => request<PortfolioMarkdownResponse>("/api/portfolio/generate-resume-entry", { method: "POST" }),
  generatePortfolioInterviewQa: () => request<PortfolioMarkdownResponse>("/api/portfolio/generate-interview-qa", { method: "POST" }),
  generatePortfolioProjectReview: () => request<PortfolioMarkdownResponse>("/api/portfolio/generate-project-review", { method: "POST" }),
  exportPortfolioMarkdown: () => request<PortfolioMarkdownResponse>("/api/portfolio/export-markdown", { method: "POST" })
};

export function formatDate(value: string | null) {
  if (!value) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDuration(milliseconds: number | null | undefined) {
  if (milliseconds === null || milliseconds === undefined) return "未记录";
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return hours > 0
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function sourceFileUrl(sourceId: number) {
  return `${API_BASE_URL}/api/media/sources/${sourceId}/file`;
}

export function mediaAssetFileUrl(assetId: number) {
  return `${API_BASE_URL}/api/media/assets/${assetId}/file`;
}

export function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: "等待处理",
    queued: "\u6392\u961f\u4e2d",
    claimed: "Worker 已接管",
    uploading: "上传中",
    running: "\u5904\u7406\u4e2d",
    cancelling: "取消中",
    interrupted: "已中断",
    parsing: "解析中",
    chunking: "切片中",
    embedding: "生成向量",
    indexing: "写入索引",
    indexed: "已索引",
    ready: "可以使用",
    active: "使用中",
    retired: "已退役",
    completed: "\u5df2\u5b8c\u6210",
    failed: "\u5931\u8d25",
    cancelled: "\u5df2\u53d6\u6d88",
    retrying: "\u91cd\u8bd5\u4e2d",
    retry_scheduled: "等待重试",
    success: "成功",
    citation_validation_failed: "引用需校验",
    insufficient_context: "资料不足",
    no_ready_documents: "暂无可用资料",
    real: "\u771f\u5b9e\u6a21\u5f0f",
    demo: "\u6f14\u793a\u6a21\u5f0f",
    not_started: "未开始",
    learning: "学习中",
    understood: "已理解",
    know: "会了",
    unclear: "模糊",
    unknown: "不会",
    review_needed: "待复习",
    mastered: "已掌握",
    image_metadata_only: "图片元数据模式",
    image_ocr: "图片 OCR",
    not_configured: "\u672a\u914d\u7f6e",
    empty: "无可用文本",
    open: "待处理",
    investigating: "排查中",
    resolved: "已解决",
    ignored: "已忽略",
    high: "高",
    medium: "中",
    low: "低",
    audio_metadata_only: "音频元数据模式",
    audio_transcription: "音频转写",
    audio_transcript: "音频片段",
    video_metadata_only: "视频元数据模式",
    video_transcription: "视频转写",
    video_transcript: "视频片段",
    code_repository: "代码仓库",
    code_file: "代码片段",
    prerequisite: "前置知识",
    related: "相关知识",
    used_by_project: "项目使用",
    next_to_learn: "下一步",
    hit: "缓存命中",
    miss: "缓存未命中",
    deduped: "请求去重",
    refresh: "强制刷新",
    bypass: "未缓存",
    server: "服务端记录"
  };
  return map[status] || status;
}

export function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (["ready", "completed", "indexed", "success", "real", "know", "understood", "mastered", "resolved", "hit"].includes(status)) return "ok";
  if (["failed", "citation_validation_failed", "unknown", "interrupted", "error"].includes(status)) return "danger";
  if (
    [
      "demo",
      "pending",
      "queued",
      "claimed",
      "running",
      "cancelling",
      "insufficient_context",
      "review_needed",
      "unclear",
      "not_configured",
      "empty",
      "open",
      "investigating",
      "miss",
      "deduped",
      "refresh"
    ].includes(status)
  ) {
    return "warn";
  }
  return "muted";
}
