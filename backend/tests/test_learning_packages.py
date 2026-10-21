from app.services.learning_package_service import learning_package_service
from app.services.learning_log_service import learning_log_service
from app.core.config import settings


def test_learning_package_draft_and_confirm(db_session, monkeypatch) -> None:
    monkeypatch.setattr(learning_package_service, "_append_stage_delivery_once", lambda slug: None)
    monkeypatch.setattr(learning_log_service, "append_markdown_once", lambda slug, markdown: None)
    draft = learning_package_service.generate_draft(db_session)

    confirmed = learning_package_service.confirm_package(db_session, draft.slug)

    assert draft.slug == confirmed.slug
    assert confirmed.status == "confirmed"
    assert confirmed.knowledge_points


def test_v3_6_stage_delivery_append_uses_current_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(type(settings), "docs_dir", property(lambda _self: tmp_path))
    path = tmp_path / "stage_delivery_log.md"
    path.write_text("# Stage\n\n", encoding="utf-8")

    learning_package_service._append_stage_delivery_once("v3-6-unified-media-learning")
    first = path.read_text(encoding="utf-8")
    learning_package_service._append_stage_delivery_once("v3-6-unified-media-learning")

    assert "V3.6 阶段交付确认" in first
    assert "统一多模态任务中心" in first
    assert "## V2.5 阶段交付" not in first
    assert path.read_text(encoding="utf-8") == first
