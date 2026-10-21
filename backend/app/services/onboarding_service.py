from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingState
from app.schemas.onboarding_schema import OnboardingRead, OnboardingUpdate


ONBOARDING_STEPS = [
    "system_check",
    "create_space",
    "upload_document",
    "ask_question",
    "start_learning",
]


class OnboardingService:
    def get_state(self, db: Session, user_key: str = "local") -> OnboardingRead:
        state = self._get_or_create(db, user_key)
        return self.to_read(state)

    def update_state(self, db: Session, payload: OnboardingUpdate, user_key: str = "local") -> OnboardingRead:
        state = self._get_or_create(db, user_key)
        steps = self._steps(state)
        steps.update({key: bool(value) for key, value in payload.steps.items() if key in ONBOARDING_STEPS})
        state.steps_json = json.dumps(steps, ensure_ascii=False)
        if payload.dismissed is not None:
            state.dismissed = payload.dismissed
        db.commit()
        db.refresh(state)
        return self.to_read(state)

    def reset(self, db: Session, user_key: str = "local") -> OnboardingRead:
        state = self._get_or_create(db, user_key)
        state.steps_json = "{}"
        state.dismissed = False
        db.commit()
        db.refresh(state)
        return self.to_read(state)

    def _get_or_create(self, db: Session, user_key: str) -> OnboardingState:
        state = db.scalar(select(OnboardingState).where(OnboardingState.user_key == user_key))
        if state is None:
            state = OnboardingState(user_key=user_key, steps_json="{}")
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def to_read(self, state: OnboardingState) -> OnboardingRead:
        steps = self._steps(state)
        completed = sum(1 for step in ONBOARDING_STEPS if steps.get(step))
        next_step = next((step for step in ONBOARDING_STEPS if not steps.get(step)), "completed")
        return OnboardingRead(
            user_key=state.user_key,
            steps=steps,
            dismissed=state.dismissed,
            progress=round(completed / len(ONBOARDING_STEPS) * 100),
            next_step=next_step,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )

    @staticmethod
    def _steps(state: OnboardingState) -> dict[str, bool]:
        try:
            raw = json.loads(state.steps_json or "{}")
        except json.JSONDecodeError:
            raw = {}
        return {step: bool(raw.get(step, False)) for step in ONBOARDING_STEPS}


onboarding_service = OnboardingService()
