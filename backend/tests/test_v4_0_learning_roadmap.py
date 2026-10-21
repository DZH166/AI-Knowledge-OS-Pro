from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.learning_system import KnowledgePoint, VersionLearningPackage
from app.services.learning_package_service import learning_package_service


def test_learning_roadmap_derives_relations_from_existing_points(db_session) -> None:
    package = _seed_learning_points(db_session)

    roadmap = learning_package_service.roadmap(db_session)
    relation_types = {relation.relation_type for relation in roadmap.relations}

    assert roadmap.total_steps == 3
    assert roadmap.review_needed_count == 1
    assert roadmap.steps[0].title == "Citation Validation"
    assert roadmap.steps[0].action_label == "优先复习并做练习"
    assert "prerequisite" in relation_types
    assert "next_to_learn" in relation_types
    assert "used_by_project" in relation_types
    assert package.id is not None


def test_learning_roadmap_routes_return_display_contract(db_session) -> None:
    _seed_learning_points(db_session)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        roadmap_response = client.get("/api/learning/roadmap")
        assert roadmap_response.status_code == 200
        roadmap = roadmap_response.json()["data"]
        assert roadmap["generated_from"] == "existing_knowledge_points_cards_quizzes_notes"
        assert roadmap["total_steps"] == 3

        graph_response = client.get("/api/learning/knowledge-graph")
        assert graph_response.status_code == 200
        graph = graph_response.json()["data"]
        assert any(relation["relation_type"] == "used_by_project" for relation in graph)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _seed_learning_points(db_session) -> VersionLearningPackage:
    package = VersionLearningPackage(
        version_name="V4.0 Learning",
        slug="v4-learning-roadmap",
        status="draft",
        summary="Learning roadmap",
        implemented_features_json="[]",
        major_files_json="[]",
        focus="Knowledge relation",
        review_suggestions="Review weak points",
        interview_expression="Explain learning graph",
        next_version_suggestion="Add persistent graph",
        markdown_content="# V4.0 Learning",
    )
    db_session.add(package)
    db_session.flush()
    points = [
        KnowledgePoint(
            package_id=package.id,
            name="Hybrid Retrieval",
            beginner_explanation="Combine dense and keyword retrieval.",
            project_usage="RAG search uses hybrid retrieval.",
            code_locations_json='["backend/app/services/hybrid_retriever.py"]',
            review_suggestion="Explain score fusion.",
            interview_expression="I can explain dense and keyword fusion.",
            mastery_status="learning",
        ),
        KnowledgePoint(
            package_id=package.id,
            name="Citation Validation",
            beginner_explanation="Check citations before trusting answers.",
            project_usage="RAG search validates citation usage.",
            code_locations_json="[]",
            review_suggestion="Review citation failure path.",
            interview_expression="I can explain why answers need citations.",
            mastery_status="review_needed",
        ),
        KnowledgePoint(
            package_id=package.id,
            name="Code Repository Ingestion",
            beginner_explanation="Turn code files into searchable chunks.",
            project_usage="Code repository chunks support file and line citations.",
            code_locations_json='["backend/app/services/code_repository_service.py"]',
            review_suggestion="Review safety skip rules.",
            interview_expression="I can explain safe repository ingestion.",
            mastery_status="not_started",
        ),
    ]
    db_session.add_all(points)
    db_session.commit()
    db_session.refresh(package)
    return package
