from datetime import datetime

from pydantic import BaseModel, Field


class OnboardingRead(BaseModel):
    user_key: str = "local"
    steps: dict[str, bool] = Field(default_factory=dict)
    dismissed: bool = False
    progress: int = 0
    next_step: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OnboardingUpdate(BaseModel):
    steps: dict[str, bool] = Field(default_factory=dict)
    dismissed: bool | None = None
