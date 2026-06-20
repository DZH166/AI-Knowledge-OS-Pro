from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    filename: str
    original_filename: str
    file_type: str
    content_type: str | None
    file_size: int
    status: str
    parse_status: str
    chunk_status: str
    vector_status: str
    processing_status: str = "pending"
    processing_progress: int = 0
    retry_count: int = 0
    content_hash: str | None = None
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_type: str = "upload"
    summary: str | None
    extractive_preview: str | None = None
    ai_summary: str | None = None
    error_message: str | None
    chunk_count: int
    indexed_at: datetime | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    embedding_fingerprint: str | None = None
    index_version: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None
    summary: str | None = None


class BulkDocumentIds(BaseModel):
    document_ids: list[int] = Field(min_length=1)


class BulkTagRequest(BulkDocumentIds):
    tags: list[str] = Field(default_factory=list)


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int | None = None
    source_id: int | None = None
    space_id: int
    target_type: str = "document"
    chunk_index: int
    content: str
    content_preview: str
    char_count: int
    page_number: int | None = None
    heading_path: str | None = None
    section_title: str | None = None
    token_count: int | None = None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    message: str
    job_id: int | None = None


class DocumentActionResponse(BaseModel):
    document: DocumentRead | None = None
    message: str
    job_id: int | None = None


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int | None = None
    source_id: int | None = None
    space_id: int
    target_type: str = "document"
    job_type: str
    status: str
    current_step: str | None = None
    step_index: int = 0
    step_total: int = 0
    progress: int
    worker_id: str | None = None
    queue_name: str = "default"
    priority: int = 100
    attempt: int = 0
    max_attempts: int = 3
    message: str | None
    error_code: str | None = None
    error_message: str | None
    error_details_json: str = "{}"
    result_json: str = "{}"
    parent_job_id: int | None = None
    retry_count: int
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime
    updated_at: datetime


class JobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    event_type: str
    step: str | None = None
    progress: int
    message: str | None = None
    technical_message: str | None = None
    created_at: datetime


class BulkDocumentActionResponse(BaseModel):
    affected_count: int
    job_ids: list[int] = Field(default_factory=list)
    message: str
