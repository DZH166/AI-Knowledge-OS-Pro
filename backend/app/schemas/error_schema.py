from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorArchiveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    source_id: int | None = None
    chunk_id: int | None = None
    title: str
    error_type: str
    error_message: str
    stack_excerpt: str | None = None
    language: str | None = None
    severity: str
    status: str
    detection_method: str
    confidence: int
    suggested_actions: list[str]
    tags: list[str]
    resolution_notes: str | None = None
    fingerprint: str
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ErrorArchiveUpdate(BaseModel):
    status: Literal["open", "investigating", "resolved", "ignored"] | None = None
    resolution_notes: str | None = Field(default=None, max_length=10000)
    tags: list[str] | None = None


class ErrorExtractionResponse(BaseModel):
    archive: ErrorArchiveRead
    created: bool
    message: str
