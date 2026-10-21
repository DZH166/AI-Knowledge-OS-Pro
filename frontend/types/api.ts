export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  error: null | {
    code: string;
    message: string;
    user_message: string;
    details: Record<string, unknown>;
    request_id: string;
    retryable: boolean;
  };
  request_id: string;
};

export type KnowledgeSpace = {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  document_count?: number;
  chunk_count?: number;
  qa_count?: number;
};

export type DocumentItem = {
  id: number;
  space_id: number;
  filename: string;
  original_filename: string;
  file_type: string;
  content_type: string | null;
  file_size: number;
  status: string;
  parse_status: string;
  chunk_status: string;
  vector_status: string;
  processing_status: string;
  processing_progress: number;
  retry_count: number;
  content_hash: string | null;
  title: string | null;
  tags: string[];
  source_type: string;
  summary: string | null;
  extractive_preview: string | null;
  ai_summary: string | null;
  error_message: string | null;
  chunk_count: number;
  indexed_at: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  embedding_fingerprint: string | null;
  index_version: string | null;
  created_at: string;
  updated_at: string;
};

export type MediaAsset = {
  id: number;
  source_id: number;
  asset_type: string;
  storage_path: string;
  mime_type: string | null;
  file_size: number;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  metadata_json: string;
  created_at: string;
};

export type MultimodalChunk = {
  id: number;
  source_id: number;
  revision_id: number;
  chunk_index: number;
  modality: string;
  source_type: string;
  content_text: string;
  search_text: string;
  locator_json: string;
  start_ms: number | null;
  end_ms: number | null;
  page_number: number | null;
  slide_number: number | null;
  frame_id: number | null;
  status: string;
  qdrant_point_id: string | null;
  created_at: string;
};

export type TranscriptSegment = {
  id: number;
  source_id: number;
  revision_id: number;
  segment_index: number;
  start_ms: number;
  end_ms: number;
  speaker: string | null;
  language: string | null;
  text: string;
  confidence: number | null;
  created_at: string;
};

export type VisualFrame = {
  id: number;
  source_id: number;
  revision_id: number;
  frame_index: number;
  timestamp_ms: number | null;
  storage_path: string | null;
  ocr_text: string | null;
  visual_description: string | null;
  scene_score: number | null;
  metadata_json: string;
  created_at: string;
};

export type SourceRevision = {
  id: number;
  source_id: number;
  revision_number: number;
  status: string;
  parser_name: string | null;
  parser_version: string | null;
  chunk_count: number;
  vector_count: number;
  validation_status: string;
  error_message: string | null;
  metadata_json: string;
  activated_at: string | null;
  chunks: MultimodalChunk[];
  transcript_segments: TranscriptSegment[];
  visual_frames: VisualFrame[];
};

export type SourceItem = {
  id: number;
  space_id: number;
  document_id: number | null;
  source_type: string;
  title: string | null;
  original_filename: string | null;
  mime_type: string | null;
  file_size: number;
  storage_path: string | null;
  content_hash: string | null;
  status: string;
  language: string | null;
  duration_ms: number | null;
  page_count: number | null;
  width: number | null;
  height: number | null;
  metadata_json: string;
  active_revision_id: number | null;
  latest_revision_id: number | null;
  media_assets: MediaAsset[];
  revisions: SourceRevision[];
  created_at: string;
  updated_at: string;
};

export type ErrorArchive = {
  id: number;
  space_id: number;
  source_id: number | null;
  chunk_id: number | null;
  title: string;
  error_type: string;
  error_message: string;
  stack_excerpt: string | null;
  language: string | null;
  severity: string;
  status: string;
  detection_method: string;
  confidence: number;
  suggested_actions: string[];
  tags: string[];
  resolution_notes: string | null;
  fingerprint: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Chunk = {
  id: number;
  document_id: number;
  space_id: number;
  chunk_index: number;
  content: string;
  content_preview: string;
  char_count: number;
  page_number: number | null;
  heading_path: string | null;
  section_title: string | null;
  token_count: number | null;
  created_at: string;
};

export type IngestionJob = {
  id: number;
  document_id: number | null;
  source_id: number | null;
  space_id: number;
  target_type: "document" | "media" | string;
  job_type: string;
  status: string;
  current_step: string | null;
  step_index: number;
  step_total: number;
  progress: number;
  worker_id: string | null;
  queue_name: string;
  priority: number;
  attempt: number;
  max_attempts: number;
  message: string | null;
  error_code: string | null;
  error_message: string | null;
  error_details_json: string;
  result_json: string;
  parent_job_id: number | null;
  retry_count: number;
  started_at: string | null;
  heartbeat_at: string | null;
  finished_at: string | null;
  cancel_requested_at: string | null;
  duration_ms: number | null;
  created_at: string;
  updated_at: string;
};

export type MediaOperation =
  | "image_ocr"
  | "image_visual_description"
  | "image_screenshot_analysis"
  | "image_full_analysis"
  | "audio_transcription"
  | "video_transcription"
  | "video_keyframes"
  | "video_keyframe_ocr"
  | "video_visual_description"
  | "video_full_pipeline";

export type MediaTaskResponse = {
  source: SourceItem;
  job: IngestionJob;
  message: string;
};

export type JobEvent = {
  id: number;
  job_id: number;
  event_type: string;
  step: string | null;
  progress: number;
  message: string | null;
  technical_message: string | null;
  created_at: string;
};

export type Citation = {
  citation_id: string;
  document_name: string;
  chunk_id: number;
  chunk_index: number;
  content_preview: string;
  score: number;
  page_number?: number | null;
  heading_path?: string | null;
  section_title?: string | null;
  source_type?: string | null;
  source_id?: number | null;
  document_id?: number | null;
  start_ms?: number | null;
  end_ms?: number | null;
  dense_score?: number | null;
  keyword_score?: number | null;
  rerank_score?: number | null;
  final_score?: number | null;
  retrieval_reason?: string | null;
  citation_ready?: boolean | null;
  file_path?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  symbol_name?: string | null;
};

export type RelatedChunk = {
  chunk_id: number;
  document_name: string;
  content: string;
  score: number;
  page_number?: number | null;
  heading_path?: string | null;
  section_title?: string | null;
  source_type?: string | null;
  source_id?: number | null;
  document_id?: number | null;
  start_ms?: number | null;
  end_ms?: number | null;
  dense_score?: number | null;
  keyword_score?: number | null;
  rerank_score?: number | null;
  final_score?: number | null;
  retrieval_reason?: string | null;
  citation_ready?: boolean | null;
  file_path?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  symbol_name?: string | null;
};

export type CodeRepositoryIngestResponse = {
  source: SourceItem;
  file_count: number;
  chunk_count: number;
  skipped_count: number;
  message: string;
};

export type AnswerMode = "normal" | "beginner" | "project" | "interview";

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  used_citation_ids: string[];
  related_chunks: RelatedChunk[];
  answer_confidence: string;
  retrieval_score: number | null;
  retrieval_status: string;
  runtime_mode: string;
  qa_log_id: number;
};

export type QALog = ChatResponse & {
  id: number;
  space_id: number;
  question: string;
  answer_mode: AnswerMode;
  created_at: string;
};

export type ChatMessage = {
  id: number;
  session_id: number;
  qa_log_id: number | null;
  role: "user" | "assistant" | string;
  content: string;
  answer_mode: string | null;
  citations: Citation[];
  used_citation_ids: string[];
  related_chunks: RelatedChunk[];
  retrieval_status: string | null;
  answer_confidence: string | null;
  is_favorite: boolean;
  created_at: string;
};

export type ChatSession = {
  id: number;
  space_id: number;
  title: string;
  answer_mode: string;
  is_archived: boolean;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
};

export type MajorFile = {
  path: string;
  responsibility: string;
};

export type LearningLogKnowledgePoint = {
  name: string;
  beginner_explanation: string;
  project_usage: string;
  code_locations?: string[];
  review_suggestion: string;
  interview_expression: string;
};

export type LearningLog = {
  id: number;
  version_name: string;
  slug: string;
  summary: string;
  implemented_features: string[];
  major_files: MajorFile[];
  knowledge_points: LearningLogKnowledgePoint[];
  focus: string;
  review_suggestions: string;
  interview_expression: string;
  next_version_suggestion: string;
  markdown_content: string;
  created_at: string;
};

export type LearningPackage = {
  id: number;
  version_name: string;
  slug: string;
  status: string;
  summary: string;
  implemented_features: string[];
  major_files: MajorFile[];
  knowledge_points: LearningLogKnowledgePoint[];
  focus: string;
  review_suggestions: string;
  interview_expression: string;
  next_version_suggestion: string;
  markdown_content: string;
  created_at: string;
  confirmed_at: string | null;
};

export type LearningKnowledgePoint = LearningLogKnowledgePoint & {
  id: number;
  package_id: number | null;
  mastery_status: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type LearningCard = {
  id: number;
  package_id: number | null;
  knowledge_point_id: number | null;
  front: string;
  back: string;
  mastery_status: string;
  last_reviewed_at: string | null;
  next_review_at: string | null;
  review_count: number;
  difficulty: string;
  created_at: string;
};

export type QuizQuestion = {
  id: number;
  package_id: number | null;
  knowledge_point_id: number | null;
  question: string;
  options: string[];
  explanation: string | null;
};

export type LearningNote = {
  id: number;
  title: string;
  content: string;
  tags: string[];
  knowledge_point_id: number | null;
  document_id: number | null;
  qa_log_id: number | null;
  version_slug: string | null;
  created_at: string;
  updated_at: string;
};

export type LearningArtifactType = "knowledge_point" | "card" | "quiz" | "note" | "interview_expression";

export type LearningArtifact = {
  id: number;
  artifact_type: LearningArtifactType | string;
  title: string;
  content: string;
  source_id: number | null;
  document_id: number | null;
  chunk_id: number | null;
  document_chunk_id: number | null;
  locator_json: string;
  knowledge_point_id: number | null;
  card_id: number | null;
  quiz_id: number | null;
  note_id: number | null;
  created_at: string;
};

export type PortfolioMetric = {
  key: string;
  label: string;
  value: number;
  description: string;
};

export type PortfolioCapability = {
  name: string;
  status: string;
  evidence: string;
  boundary: string;
};

export type PortfolioSummary = {
  project_name: string;
  version: string;
  semantic_version: string;
  runtime_mode: string;
  positioning: string;
  metrics: PortfolioMetric[];
  capabilities: PortfolioCapability[];
  resume_bullets: string[];
  interview_talking_points: string[];
  recommended_storyline: string[];
  honest_boundaries: string[];
  next_steps: string[];
};

export type PortfolioMarkdownResponse = {
  title: string;
  markdown: string;
  message: string;
  source_branch: string | null;
  source_commit: string | null;
  evidence: string[];
};

export type LearningDashboard = {
  current_version: string;
  total_knowledge_points: number;
  mastered_count: number;
  learning_count: number;
  review_needed_count: number;
  due_card_count: number;
  quiz_count: number;
  note_count: number;
  next_lesson: string;
};

export type KnowledgeRelation = {
  source_point_id: number;
  source_name: string;
  target_point_id: number | null;
  target_name: string | null;
  relation_type: string;
  reason: string;
};

export type LearningRoadmapStep = {
  order: number;
  knowledge_point_id: number;
  title: string;
  mastery_status: string;
  relation_hint: string;
  action_label: string;
  code_locations: string[];
  interview_expression: string;
};

export type LearningRoadmap = {
  total_steps: number;
  review_needed_count: number;
  generated_from: string;
  steps: LearningRoadmapStep[];
  relations: KnowledgeRelation[];
};

export type DashboardSummary = {
  knowledge_space_count: number;
  document_count: number;
  qa_count: number;
  recent_documents: DocumentItem[];
  recent_qa: QALog[];
  current_version: string;
  current_capabilities: string[];
  recent_learning_log: LearningLog | null;
  next_step_suggestion: string;
};

export type ComponentStatus = {
  ok: boolean;
  status: string;
  message: string;
  details: Record<string, unknown>;
};

export type RuntimeStatus = {
  app_name: string;
  app_version: string;
  semantic_version: string;
  app_env: string;
  runtime_mode: string;
  python_version: string;
  database_url: string;
  qdrant_url: string;
  qdrant_collection: string;
  redis_url: string;
  task_queue_name: string;
  worker_queues: string;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;
  ocr_provider: string;
  ocr_model: string;
  transcription_provider: string;
  transcription_model: string;
  index_version: string;
  retrieval_top_k: number;
  retrieval_score_threshold: number;
};

export type SystemStatus = {
  runtime: RuntimeStatus;
  db: ComponentStatus;
  qdrant: ComponentStatus;
  collection: ComponentStatus;
  redis: ComponentStatus;
  worker: ComponentStatus;
  llm: ComponentStatus;
  embedding: ComponentStatus;
  ocr: ComponentStatus;
  transcription: ComponentStatus;
  index: ComponentStatus;
  warnings: string[];
};

export type SystemTestResponse = {
  ok: boolean;
  status: string;
  message: string;
  details: Record<string, unknown>;
};

export type ObservabilityRequest = {
  request_id: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  error_code: string | null;
  created_at: string;
};

export type ObservabilityTask = {
  task_id: number;
  target_type: string;
  document_id: number | null;
  source_id: number | null;
  status: string;
  task_stage: string | null;
  progress: number;
  task_duration_ms: number | null;
  error_code: string | null;
  latest_event: string | null;
  created_at: string;
  updated_at: string | null;
};

export type ObservabilityRetrieval = {
  retrieval_trace_id: string;
  generation_id: string;
  qa_log_id: number;
  runtime_mode: string;
  answer_status: string;
  retrieval_top_k: number;
  retrieval_source_mix: Record<string, number>;
  citation_count: number;
  citation_validation_status: string;
  latency_ms: number | null;
  error_code: string | null;
  created_at: string;
};

export type ObservabilityProviderStatus = {
  provider_name: string;
  provider_status: string;
  provider_error_code: string | null;
  message: string;
  latency_ms: number | null;
};

export type ObservabilitySummary = {
  demo_mode: boolean;
  runtime_mode: string;
  recent_requests: ObservabilityRequest[];
  recent_tasks: ObservabilityTask[];
  recent_retrievals: ObservabilityRetrieval[];
  provider_status: ObservabilityProviderStatus[];
  error_categories: Record<string, number>;
  notes: string[];
};

export type OnboardingState = {
  user_key: string;
  steps: Record<string, boolean>;
  dismissed: boolean;
  progress: number;
  next_step: string;
  created_at: string | null;
  updated_at: string | null;
};
