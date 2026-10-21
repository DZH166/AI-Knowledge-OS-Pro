from app.models.knowledge_space import KnowledgeSpace


def test_create_knowledge_space(db_session) -> None:
    space = KnowledgeSpace(name="项目资料", description="AI 学习")
    db_session.add(space)
    db_session.commit()
    db_session.refresh(space)
    assert space.id
    assert space.name == "项目资料"
