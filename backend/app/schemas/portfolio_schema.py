from pydantic import BaseModel


class PortfolioMetric(BaseModel):
    key: str
    label: str
    value: int
    description: str


class PortfolioCapability(BaseModel):
    name: str
    status: str
    evidence: str
    boundary: str


class PortfolioSummary(BaseModel):
    project_name: str
    version: str
    semantic_version: str
    runtime_mode: str
    positioning: str
    metrics: list[PortfolioMetric]
    capabilities: list[PortfolioCapability]
    resume_bullets: list[str]
    interview_talking_points: list[str]
    recommended_storyline: list[str]
    honest_boundaries: list[str]
    next_steps: list[str]
