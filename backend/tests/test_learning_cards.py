from app.schemas.learning_schema import LearningCardProgressUpdate
from app.services.learning_log_service import learning_log_service
from app.services.learning_package_service import learning_package_service


def test_learning_card_progress_updates_point(db_session, monkeypatch) -> None:
    monkeypatch.setattr(learning_package_service, "_append_stage_delivery_once", lambda slug: None)
    monkeypatch.setattr(learning_log_service, "append_markdown_once", lambda slug, markdown: None)
    learning_package_service.generate_draft(db_session)
    card = learning_package_service.list_cards(db_session)[0]

    updated = learning_package_service.update_card_progress(
        db_session,
        card.id,
        LearningCardProgressUpdate(mastery_status="know"),
    )
    point = learning_package_service.get_knowledge_point(db_session, updated.knowledge_point_id)

    assert updated.mastery_status == "know"
    assert point is not None
    assert point.mastery_status == "know"
