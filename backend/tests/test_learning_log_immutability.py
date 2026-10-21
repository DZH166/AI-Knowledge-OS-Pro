from app.schemas.learning_schema import LearningLogCreate
from app.services.learning_log_service import learning_log_service


def _payload(slug: str, summary: str) -> LearningLogCreate:
    return LearningLogCreate(
        version_name="Test",
        slug=slug,
        summary=summary,
        implemented_features=["feature"],
        major_files=[{"path": "x.py", "responsibility": "test"}],
        knowledge_points=[
            {
                "name": "RAG",
                "beginner_explanation": "检索后回答",
                "project_usage": "用于知识问答",
                "review_suggestion": "学习 embedding",
                "interview_expression": "实现了 RAG 闭环",
            }
        ],
        focus="focus",
        review_suggestions="review",
        interview_expression="interview",
        next_version_suggestion="next",
    )


def test_learning_log_does_not_overwrite_existing(db_session, monkeypatch) -> None:
    appended: list[tuple[str, str]] = []
    monkeypatch.setattr(learning_log_service, "append_markdown_once", lambda slug, markdown: appended.append((slug, markdown)))

    first = learning_log_service.create_log(db_session, _payload("same-slug", "first"))
    second = learning_log_service.create_log(db_session, _payload("same-slug", "second"))

    assert first.id == second.id
    assert second.summary == "first"
    assert len(appended) == 1
