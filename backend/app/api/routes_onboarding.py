from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.onboarding_schema import OnboardingRead, OnboardingUpdate
from app.services.onboarding_service import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingRead)
def get_onboarding(db: Session = Depends(get_db)) -> OnboardingRead:
    return onboarding_service.get_state(db)


@router.patch("", response_model=OnboardingRead)
def update_onboarding(payload: OnboardingUpdate, db: Session = Depends(get_db)) -> OnboardingRead:
    return onboarding_service.update_state(db, payload)


@router.post("/reset", response_model=OnboardingRead)
def reset_onboarding(db: Session = Depends(get_db)) -> OnboardingRead:
    return onboarding_service.reset(db)
