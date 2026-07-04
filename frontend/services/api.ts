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
  LearningRoadmap,
  KnowledgeRelation,
  LearningKnowledgePoint,
  LearningLog,
  LearningNote,
  LearningPackage,
  MediaOperation,
  MediaTaskResponse,
  OnboardingState,
  PortfolioMarkdownResponse,
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
  }) => request<{ artifacts: LearningArtifact[]; message: string }>("/api/learning/from-source", {
    method: "POST",
    body: JSON.stringify(payload)
  }),
  exportLearningMarkdown: () => request<{ markdown: string; message: string }>("/api/learning/export-markdown", { method: "POST" }),
  portfolioSummary: () => request<PortfolioSummary>("/api/portfolio/summary"),
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
    pending: "\u7b49\u5f85\u5904\u7406",
    queued: "\u6392\u961f\u4e2d",
    claimed: "Worker \u5df2\u63a5\u7ba1",
    uploading: "\u4e0a\u4f20\u4e2d",
    running: "\u5904\u7406\u4e2d",
    cancelling: "\u53d6\u6d88\u4e2d",
    interrupted: "\u5df2\u4e2d\u65ad",
    parsing: "\u89e3\u6790\u4e2d",
    chunking: "\u5207\u7247\u4e2d",
    embedding: "\u751f\u6210\u5411\u91cf",
    indexing: "\u5199\u5165\u7d22\u5f15",
    indexed: "\u5df2\u7d22\u5f15",
    ready: "\u53ef\u4ee5\u4f7f\u7528",
    completed: "\u5df2\u5b8c\u6210",
    failed: "\u5931\u8d25",
    cancelled: "\u5df2\u53d6\u6d88",
    retrying: "\u91cd\u8bd5\u4e2d",
    retry_scheduled: "\u7b49\u5f85\u91cd\u8bd5",
    success: "\u6210\u529f",
    citation_validation_failed: "\u5f15\u7528\u9700\u6821\u9a8c",
    insufficient_context: "\u8d44\u6599\u4e0d\u8db3",
    no_ready_documents: "\u6682\u65e0\u53ef\u7528\u8d44\u6599",
    real: "\u771f\u5b9e\u6a21\u5f0f",
    demo: "\u6f14\u793a\u6a21\u5f0f",
    not_started: "\u672a\u5f00\u59cb",
    learning: "\u5b66\u4e60\u4e2d",
    understood: "\u5df2\u7406\u89e3",
    know: "\u4f1a\u4e86",
    unclear: "\u6a21\u7cca",
    unknown: "\u4e0d\u4f1a",
    review_needed: "\u5f85\u590d\u4e60",
    mastered: "\u5df2\u638c\u63e1",
    image_metadata_only: "\u56fe\u7247\u5143\u6570\u636e\u6a21\u5f0f",
    image_ocr: "\u56fe\u7247 OCR",
    not_configured: "\u672a\u914d\u7f6e",
    empty: "\u65e0\u53ef\u7528\u6587\u672c",
    open: "\u5f85\u5904\u7406",
    investigating: "\u6392\u67e5\u4e2d",
    resolved: "\u5df2\u89e3\u51b3",
    ignored: "\u5df2\u5ffd\u7565",
    high: "\u9ad8",
    medium: "\u4e2d",
    low: "\u4f4e",
    audio_metadata_only: "\u97f3\u9891\u5143\u6570\u636e\u6a21\u5f0f",
    audio_transcription: "\u97f3\u9891\u8f6c\u5199",
    audio_transcript: "\u97f3\u9891\u7247\u6bb5",
    video_metadata_only: "\u89c6\u9891\u5143\u6570\u636e\u6a21\u5f0f",
    video_transcription: "\u89c6\u9891\u8f6c\u5199",
    video_transcript: "\u89c6\u9891\u7247\u6bb5",
    code_repository: "\u4ee3\u7801\u4ed3\u5e93",
    code_file: "\u4ee3\u7801\u7247\u6bb5",
    prerequisite: "\u524d\u7f6e\u77e5\u8bc6",
    related: "\u76f8\u5173\u77e5\u8bc6",
    used_by_project: "\u9879\u76ee\u4f7f\u7528",
    next_to_learn: "\u4e0b\u4e00\u6b65"
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
