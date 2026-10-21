from pydantic import BaseModel, Field


class PerformanceRequestRecord(BaseModel):
    request_id: str
    path: str
    method: str
    status_code: int
    latency_ms: int
    error_code: str | None = None
    provider_name: str | None = None
    provider_status: str | None = None
    retrieval_trace_id: str | None = None
    task_id: int | None = None
    cache_status: str | None = None
    demo_mode: bool
    timestamp: str


class PerformancePathStats(BaseModel):
    path: str
    count: int
    average_latency_ms: int
    max_latency_ms: int
    slow_count: int


class PerformanceSummary(BaseModel):
    total_requests: int
    slow_request_count: int
    average_latency_ms: int
    p95_latency_ms: int
    duplicate_request_count: int
    cache_status_counts: dict[str, int] = Field(default_factory=dict)
    error_code_counts: dict[str, int] = Field(default_factory=dict)
    path_stats: list[PerformancePathStats] = Field(default_factory=list)
    slow_threshold_ms: int
    buffer_limit: int


class PerformanceSnapshot(BaseModel):
    summary: PerformanceSummary
    recent_requests: list[PerformanceRequestRecord] = Field(default_factory=list)
    slow_requests: list[PerformanceRequestRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
