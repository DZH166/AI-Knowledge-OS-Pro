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
  KnowledgeSpace,
  LearningCard,
  LearningArtifact,
  LearningArtifactType,
  LearningDashboard,
  LearningKnowledgePoint,
  LearningLog,
  LearningNote,
  LearningPackage,
  MediaOperation,
  MediaTaskResponse,
  OnboardingState,
  PortfolioSummary,
  QALog,
  QuizQuestion,
  SourceItem,
  SystemStatus,
  SystemTestResponse
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store"
  });
  const raw = await response.text();
  const parsed = raw ? safeParseJson(raw) : null;
  const payload = isRecord(parsed) ? parsed : null;

  if (!response.ok) {
    const userMessage =
      getNestedString(payload, ["error", "user_message"]) ||
      getNestedString(payload, ["detail", "user_message"]) ||
      getNestedString(payload, ["detail", "message"]) ||
      getString(payload?.detail) ||
      `请求失败：${response.status}`;
    throw new Error(userMessage);
  }

  if (payload && "success" in payload && "data" in payload) {
    const envelope = payload as ApiEnvelope<T>;
    if (!envelope.success) {
      throw new Error(envelope.error?.user_message || "请求失败");
    }
    return envelope.data;
  }
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
  dashboard: () => request<DashboardSummary>("/api/dashboard/summary"),
  onboarding: () => request<OnboardingState>("/api/onboarding"),
  updateOnboarding: (payload: { steps?: Record<string, boolean>; dismissed?: boolean }) =>
    request<OnboardingState>("/api/onboarding", {
      method: "PATCH",
      body: JSON.stringify({ steps: payload.steps || {}, dismissed: payload.dismissed })
    }),
  resetOnboarding: () => request<OnboardingState>("/api/onboarding/reset", { method: "POST" }),
  systemStatus: () => request<SystemStatus>("/api/system/status"),
  testLlm: () => request<SystemTestResponse>("/api/system/test-llm", { method: "POST" }),
  testEmbedding: () => request<SystemTestResponse>("/api/system/test-embedding", { method: "POST" }),
  testQdrant: () => request<SystemTestResponse>("/api/system/test-qdrant", { method: "POST" }),
  listSpaces: () => request<KnowledgeSpace[]>("/api/knowledge-spaces"),
  createSpace: (payload: { name: string; description?: string }) =>
    request<KnowledgeSpace>("/api/knowledge-spaces", { method: "POST", body: JSON.stringify(payload) }),
  listDocuments: (spaceId?: number) =>
    request<DocumentItem[]>(spaceId ? `/api/documents?space_id=${spaceId}` : "/api/documents"),
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
  ingestCodeRepository: (payload: {
    space_id: number;
    local_path: string;
    title?: string;
    github_url?: string;
    max_files?: number;
  }) =>
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
  runImageOcr: (sourceId: number) =>
    request<MediaTaskResponse>(`/api/media/sources/${sourceId}/ocr`, { method: "POST" }),
  transcribeMedia: (sourceId: number) =>
    request<MediaTaskResponse>(`/api/media/sources/${sourceId}/transcribe`, { method: "POST" }),
  transcribeAudio: (sourceId: number) =>
    request<MediaTaskResponse>(`/api/media/sources/${sourceId}/transcribe`, { method: "POST" }),
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
  listChatSessions: (spaceId?: number) =>
    request<ChatSession[]>(spaceId ? `/api/chat/sessions?space_id=${spaceId}` : "/api/chat/sessions"),
  getChatSession: (id: number) => request<ChatSession>(`/api/chat/sessions/${id}`),
  askInSession: (sessionId: number, payload: { question: string; answer_mode?: AnswerMode }) =>
    request<ChatResponse>(`/api/chat/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify(payload) }),
  regenerateMessage: (messageId: number) => request<ChatResponse>(`/api/chat/messages/${messageId}/regenerate`, { method: "POST" }),
  favoriteMessage: (messageId: number) =>
    request<{ message_id: number; is_favorite: boolean }>(`/api/chat/messages/${messageId}/favorite`, { method: "POST" }),
  learningDashboard: () => request<LearningDashboard>("/api/learning/dashboard"),
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
  }) => request<{ artifacts: LearningArtifact[]; message: string }>("/api/learning/from-source", {
    method: "POST",
    body: JSON.stringify(payload)
  }),
  exportLearningMarkdown: () => request<{ markdown: string; message: string }>("/api/learning/export-markdown", { method: "POST" }),
  portfolioSummary: () => request<PortfolioSummary>("/api/portfolio/summary")
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
    queued: "等待处理",
    claimed: "已被 Worker 接管",
    uploading: "正在上传",
    running: "处理中",
    cancelling: "正在取消",
    interrupted: "已中断",
    parsing: "正在解析",
    chunking: "正在切片",
    embedding: "生成向量",
    indexing: "写入索引",
    indexed: "已索引",
    ready: "可以使用",
    completed: "已完成",
    failed: "处理失败",
    cancelled: "已取消",
    retrying: "正在重试",
    retry_scheduled: "等待重试",
    success: "成功",
    citation_validation_failed: "引用需校验",
    insufficient_context: "资料不足",
    no_ready_documents: "暂无可用资料",
    real: "真实模式",
    demo: "演示模式",
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
    not_configured: "未配置",
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
    code_file: "代码片段"
  };
  return map[status] || status;
}

export function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (["ready", "completed", "indexed", "success", "real", "know", "understood", "mastered", "resolved"].includes(status)) return "ok";
  if (["failed", "citation_validation_failed", "unknown", "interrupted"].includes(status)) return "danger";
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
      "investigating"
    ].includes(status)
  ) {
    return "warn";
  }
  return "muted";
}
