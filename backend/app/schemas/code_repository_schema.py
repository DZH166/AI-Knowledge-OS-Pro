from pydantic import BaseModel, Field

from app.schemas.media_schema import SourceDetail


class CodeRepositoryIngestRequest(BaseModel):
    space_id: int
    local_path: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=180)
    github_url: str | None = Field(default=None, max_length=500)
    max_files: int = Field(default=80, ge=1, le=300)


class CodeRepositoryIngestResponse(BaseModel):
    source: SourceDetail
    file_count: int
    chunk_count: int
    skipped_count: int
    message: str
