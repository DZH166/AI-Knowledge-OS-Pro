from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AnswerMode = Literal["normal", "beginner", "project", "interview"]


class Citation(BaseModel):
    citation_id: str
    document_name: str
    chunk_id: int
    chunk_index: int
    content_preview: str
    score: float
    page_number: int | None = None
    heading_path: str | None = None
    section_title: str | None = None
    source_type: str | None = None
    source_id: int | None = None
    document_id: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class RelatedChunk(BaseModel):
    chunk_id: int
    document_name: str
    content: str
    score: float
    page_number: int | None = None
    heading_path: str | None = None
    section_title: str | None = None
    source_type: str | None = None
    source_id: int | None = None
    document_id: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class ChatRequest(BaseModel):
    space_id: int
    question: str = Field(min_length=1, max_length=4000)
    answer_mode: AnswerMode = "normal"


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    used_citation_ids: list[str] = Field(default_factory=list)
    related_chunks: list[RelatedChunk]
    answer_confidence: str = "unknown"
    retrieval_score: float | None = None
    retrieval_status: str = "unknown"
    runtime_mode: str = "real"
    qa_log_id: int


class QALogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    question: str
    answer: str
    answer_mode: str
    citations: list[Citation]
    used_citation_ids: list[str] = Field(default_factory=list)
    related_chunks: list[RelatedChunk]
    answer_confidence: str = "unknown"
    retrieval_score: float | None = None
    retrieval_status: str = "unknown"
    runtime_mode: str = "real"
    created_at: datetime


class ChatSessionCreate(BaseModel):
    space_id: int
    title: str | None = Field(default=None, max_length=160)
    answer_mode: AnswerMode = "normal"


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    answer_mode: AnswerMode | None = None
    is_archived: bool | None = None


class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    qa_log_id: int | None = None
    role: str
    content: str
    answer_mode: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    used_citation_ids: list[str] = Field(default_factory=list)
    related_chunks: list[RelatedChunk] = Field(default_factory=list)
    retrieval_status: str | None = None
    answer_confidence: str | None = None
    is_favorite: bool = False
    created_at: datetime


class ChatSessionRead(BaseModel):
    id: int
    space_id: int
    title: str
    answer_mode: str
    is_archived: bool
    messages: list[ChatMessageRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChatSessionMessageCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer_mode: AnswerMode | None = None


class ChatFavoriteResponse(BaseModel):
    message_id: int
    is_favorite: bool
