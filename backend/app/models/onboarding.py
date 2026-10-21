from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OnboardingState(Base):
    __tablename__ = "onboarding_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_key: Mapped[str] = mapped_column(String(80), nullable=False, default="local", unique=True, index=True)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    dismissed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
