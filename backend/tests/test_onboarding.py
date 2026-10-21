from app.schemas.onboarding_schema import OnboardingUpdate
from app.services.onboarding_service import onboarding_service


def test_onboarding_progress_and_reset(db_session) -> None:
    state = onboarding_service.get_state(db_session)
    assert state.progress == 0
    assert state.next_step == "system_check"

    updated = onboarding_service.update_state(
        db_session,
        OnboardingUpdate(steps={"system_check": True, "create_space": True}, dismissed=False),
    )
    assert updated.progress == 40
    assert updated.next_step == "upload_document"

    reset = onboarding_service.reset(db_session)
    assert reset.progress == 0
    assert reset.dismissed is False
