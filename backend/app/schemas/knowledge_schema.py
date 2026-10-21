from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class KnowledgeSpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeSpaceDetail(KnowledgeSpaceRead):
    document_count: int
    chunk_count: int
    qa_count: int

