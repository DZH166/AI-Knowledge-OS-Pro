from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    ok: bool
    status: str
    message: str
    details: dict = Field(default_factory=dict)


class RuntimeStatus(BaseModel):
    app_name: str
    app_version: str
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
