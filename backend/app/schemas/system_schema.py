from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    ok: bool
    status: str
    message: str
    details: dict = Field(default_factory=dict)


class RuntimeStatus(BaseModel):
    app_name: str
    app_version: str
    semantic_version: str
    app_env: str
    runtime_mode: str
    python_version: str
    database_url: str
    qdrant_url: str
    qdrant_collection: str
    redis_url: str
    task_queue_name: str
    worker_queues: str
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    ocr_provider: str
    ocr_model: str
    transcription_provider: str
    transcription_model: str
    index_version: str
    retrieval_top_k: int
    retrieval_score_threshold: float


class SystemStatusResponse(BaseModel):
    runtime: RuntimeStatus
    db: ComponentStatus
    qdrant: ComponentStatus
    collection: ComponentStatus
    redis: ComponentStatus
    worker: ComponentStatus
    llm: ComponentStatus
    embedding: ComponentStatus
    ocr: ComponentStatus
    transcription: ComponentStatus
    index: ComponentStatus
    warnings: list[str] = Field(default_factory=list)


class SystemTestResponse(BaseModel):
    ok: bool
    status: str
    message: str
    details: dict = Field(default_factory=dict)


class ObservabilityRequest(BaseModel):
    request_id: str
    method: str
    path: str
    status_code: int
    latency_ms: int
    error_code: str | None = None
    created_at: str


class ObservabilityTask(BaseModel):
    task_id: int
    target_type: str
    document_id: int | None = None
    source_id: int | None = None
    status: str
    task_stage: str | None = None
    progress: int
    task_duration_ms: int | None = None
    error_code: str | None = None
    latest_event: str | None = None
    created_at: str
    updated_at: str | None = None


class ObservabilityRetrieval(BaseModel):
    retrieval_trace_id: str
    generation_id: str
    qa_log_id: int
    runtime_mode: str
    answer_status: str
    retrieval_top_k: int
    retrieval_source_mix: dict[str, int] = Field(default_factory=dict)
    citation_count: int
    citation_validation_status: str
    latency_ms: int | None = None
    error_code: str | None = None
    created_at: str


class ObservabilityProviderStatus(BaseModel):
    provider_name: str
    provider_status: str
    provider_error_code: str | None = None
    message: str
    latency_ms: int | None = None


class ObservabilitySummary(BaseModel):
    demo_mode: bool
    runtime_mode: str
    recent_requests: list[ObservabilityRequest] = Field(default_factory=list)
    recent_tasks: list[ObservabilityTask] = Field(default_factory=list)
    recent_retrievals: list[ObservabilityRetrieval] = Field(default_factory=list)
    provider_status: list[ObservabilityProviderStatus] = Field(default_factory=list)
    error_categories: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class StorageHealthFinding(BaseModel):
    code: str
    severity: str
    entity: str
    message: str


class StorageHealthResponse(BaseModel):
    ok: bool
    checked_at: str
    database: dict = Field(default_factory=dict)
    files: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)
    findings: list[StorageHealthFinding] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
