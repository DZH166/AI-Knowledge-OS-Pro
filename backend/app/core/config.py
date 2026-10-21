from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "溯知 Evidence OS"
    app_env: str = "development"
    app_version: str = "V5.8"
    app_semver: str = "5.8.0"
    demo_mode: bool = False

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'knowledge_os.db').as_posix()}"
    upload_dir: Path = BACKEND_DIR / "storage" / "uploads"
    max_upload_size_mb: int = 25

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_timeout_seconds: int = 5
    qdrant_collection_prefix: str = "ai_knowledge_os"

    redis_url: str = "redis://localhost:6379/0"
    task_queue_name: str = "default"
    task_default_priority: int = 100
    task_max_attempts: int = 3
    task_timeout_seconds: int = 1800
    task_heartbeat_timeout_seconds: int = 120
    worker_queues: str = "high,default,low"
    worker_name: str | None = None
    outbox_poll_seconds: float = 1.0
    outbox_lease_seconds: int = 30
    outbox_batch_size: int = 25
    evaluation_timeout_seconds: int = 900
    evaluation_lease_seconds: int = 1020

    llm_provider: str = "openai_compatible"
    llm_api_key: str | None = Field(default=None, validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"))
    llm_base_url: str = Field(default="https://api.openai.com/v1", validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"))
    llm_model: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("LLM_MODEL", "CHAT_MODEL"))
    llm_timeout_seconds: int = 90
    llm_max_retries: int = 2
    llm_input_cost_micros_per_million_tokens: int | None = Field(default=None, ge=0)
    llm_output_cost_micros_per_million_tokens: int | None = Field(default=None, ge=0)

    embedding_provider: str = "openai_compatible"
    embedding_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("EMBEDDING_API_KEY", "OPENAI_API_KEY")
    )
    embedding_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias=AliasChoices("EMBEDDING_BASE_URL", "OPENAI_BASE_URL")
    )
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 64
    embedding_timeout_seconds: int = 60
    embedding_max_retries: int = 2

    rerank_api_key: str | None = None
    rerank_url: str | None = None
    rerank_model: str | None = None
    rerank_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    rerank_max_retries: int = Field(default=2, ge=0, le=5)

    ocr_provider: str = "openai_compatible_vision"
    ocr_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OCR_API_KEY", "OPENAI_API_KEY"))
    ocr_base_url: str = Field(default="https://api.openai.com/v1", validation_alias=AliasChoices("OCR_BASE_URL", "OPENAI_BASE_URL"))
    ocr_model: str = "gpt-4o-mini"
    ocr_timeout_seconds: int = 120
    ocr_max_retries: int = 2

    transcription_provider: str = "openai_compatible_audio"
    transcription_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TRANSCRIPTION_API_KEY", "OPENAI_API_KEY"),
    )
    transcription_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("TRANSCRIPTION_BASE_URL", "OPENAI_BASE_URL"),
    )
    transcription_model: str = "whisper-1"
    transcription_timeout_seconds: int = 300
    transcription_max_retries: int = 2

    retrieval_top_k: int = 5
    retrieval_dense_score_threshold: float = Field(default=0.15, ge=-1.0, le=1.0)
    retrieval_score_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    index_version: str = "v2-openai-compatible-1536"
    chunk_size: int = 1200
    chunk_overlap: int = 180

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    @property
    def learning_log_path(self) -> Path:
        return self.docs_dir / "learning_log.md"

    @property
    def runtime_mode(self) -> str:
        return "demo" if self.demo_mode else "real"

    @property
    def qdrant_collection(self) -> str:
        return f"{self.qdrant_collection_prefix}_{self.index_version}_chunks".replace("-", "_")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
