import json

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.learning_note import LearningNote
from app.models.learning_system import KnowledgePoint, LearningCard, QuizQuestion, VersionLearningPackage
from app.models.qa_log import QALog
from app.models.source import CitationLocator, MultimodalChunk, Source, SourceRevision, VisualFrame
from app.services.portfolio_service import portfolio_service
from tests.conftest import FakeLLMService


class UnconfiguredLLMService:
    def is_configured(self) -> bool:
        return False

    def complete(self, system_prompt: str, user_prompt: str) -> str:  # pragma: no cover - should never be called
        raise AssertionError("complete should not be called when the provider is missing")


def test_portfolio_summary_uses_real_database_counts(db_session, knowledge_space) -> None:
    source = _seed_portfolio_records(db_session, knowledge_space.id)

    summary = portfolio_service.summary(db_session)

    metric_values = {metric.key: metric.value for metric in summary.metrics}
    assert summary.version == "V4.3"
    assert metric_values["knowledge_spaces"] == 1
    assert metric_values["documents"] == 1
    assert metric_values["sources"] == 1
    assert metric_values["citation_locators"] == 1
    assert metric_values["tasks"] == 1
    assert metric_values["learning_assets"] == 4
    assert any("NOT_CONFIGURED" in boundary for boundary in summary.honest_boundaries)
    assert any(capability.name == "作品集/面试系统" for capability in summary.capabilities)
    assert source.id is not None


def test_portfolio_summary_route_returns_display_contract(db_session, knowledge_space) -> None:
    _seed_portfolio_records(db_session, knowledge_space.id)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/portfolio/summary")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["project_name"] == "AI Knowledge OS Pro"
        assert payload["semantic_version"] == "4.3.0"
        assert len(payload["metrics"]) >= 6
        assert len(payload["resume_bullets"]) >= 3
        assert "fake" not in json.dumps(payload, ensure_ascii=False).lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_portfolio_generation_routes_refuse_without_llm_provider(db_session, knowledge_space, monkeypatch) -> None:
    _seed_portfolio_records(db_session, knowledge_space.id)
    original_llm = portfolio_service.llm_service
    portfolio_service.llm_service = UnconfiguredLLMService()  # type: ignore[assignment]

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post("/api/portfolio/generate-resume-entry")
        assert response.status_code == 503
        payload = response.json()
        assert payload["error"]["code"] == "LLM_NOT_CONFIGURED"
        assert "Portfolio markdown generation requires a real LLM provider" in payload["error"]["message"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        portfolio_service.llm_service = original_llm


def test_portfolio_generation_routes_use_real_summary_fact_base(db_session, knowledge_space) -> None:
    _seed_portfolio_records(db_session, knowledge_space.id)
    original_llm = portfolio_service.llm_service
    portfolio_service.llm_service = FakeLLMService()  # type: ignore[assignment]

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post("/api/portfolio/generate-interview-qa")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["title"] == "Interview Q&A"
        assert payload["markdown"]
        assert payload["source_branch"]
        assert payload["source_commit"]
        assert payload["evidence"]
        assert "fake" not in json.dumps(payload, ensure_ascii=False).lower()
    finally:
        app.dependency_overrides.pop(get_db, None)
        portfolio_service.llm_service = original_llm


def test_portfolio_export_markdown_returns_summary_snapshot(db_session, knowledge_space) -> None:
    _seed_portfolio_records(db_session, knowledge_space.id)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post("/api/portfolio/export-markdown")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["title"] == "Portfolio Summary"
        assert "# AI Knowledge OS Pro Portfolio Summary" in payload["markdown"]
        assert payload["source_commit"]
        assert payload["evidence"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def _seed_portfolio_records(db_session, space_id: int) -> Source:
    document = Document(
        space_id=space_id,
        filename="portfolio.md",
        original_filename="portfolio.md",
        file_type="md",
        content_type="text/markdown",
        file_size=128,
        storage_path="/tmp/portfolio.md",
        status="ready",
        parse_status="parsed",
        chunk_status="chunked",
        vector_status="indexed",
        processing_status="completed",
    )
    db_session.add(document)
    db_session.flush()

    source = Source(
        space_id=space_id,
        document_id=document.id,
        source_type="video",
        title="Portfolio demo video",
        original_filename="portfolio.mp4",
        mime_type="video/mp4",
        file_size=4096,
        status="ready",
    )
    db_session.add(source)
    db_session.flush()

    revision = SourceRevision(
        source_id=source.id,
        document_id=document.id,
        revision_number=1,
        status="active",
        chunk_count=1,
        vector_count=1,
        validation_status="passed",
    )
    db_session.add(revision)
    db_session.flush()

    chunk = MultimodalChunk(
        source_id=source.id,
        revision_id=revision.id,
        chunk_index=0,
        modality="transcript",
        source_type="video",
        content_text="作品集演示片段",
        search_text="作品集演示片段",
        locator_json=json.dumps({"start_ms": 1000, "end_ms": 3000}),
        start_ms=1000,
        end_ms=3000,
        status="ready",
    )
    db_session.add(chunk)
    db_session.flush()

    db_session.add(
        CitationLocator(
            source_id=source.id,
            revision_id=revision.id,
            chunk_id=chunk.id,
            locator_json=json.dumps({"source_type": "video", "start_ms": 1000, "end_ms": 3000}),
            display_text="视频 00:01-00:03",
        )
    )
    db_session.add(
        VisualFrame(
            source_id=source.id,
            revision_id=revision.id,
            frame_index=0,
            timestamp_ms=1000,
            storage_path="/tmp/frame.jpg",
        )
    )
    db_session.add(
        IngestionJob(
            document_id=None,
            source_id=source.id,
            space_id=space_id,
            target_type="media",
            job_type="video_transcription",
            status="completed",
            progress=100,
        )
    )
    db_session.add(
        QALog(
            space_id=space_id,
            question="这个项目如何讲解？",
            answer="用 RAG、任务队列和学习档案讲解。",
            answer_mode="normal",
            retrieval_status="grounded",
            runtime_mode="demo",
        )
    )
    package = VersionLearningPackage(
        version_name="V4.0 Portfolio",
        slug="v4-portfolio",
        status="draft",
        summary="作品集阶段",
        implemented_features_json="[]",
        major_files_json="[]",
        focus="作品集表达",
        review_suggestions="复习项目定位",
        interview_expression="可以讲清楚边界",
        next_version_suggestion="继续做模拟面试",
        markdown_content="# V4.0",
    )
    db_session.add(package)
    db_session.flush()

    point = KnowledgePoint(
        package_id=package.id,
        name="作品集表达",
        beginner_explanation="把项目说清楚。",
        project_usage="用于简历和面试。",
        code_locations_json="[]",
        review_suggestion="结合 README 复习。",
        interview_expression="我能讲清楚项目演进。",
    )
    db_session.add(point)
    db_session.flush()

    db_session.add(LearningCard(package_id=package.id, knowledge_point_id=point.id, front="怎么讲项目？", back="先讲定位，再讲架构。"))
    db_session.add(
        QuizQuestion(
            package_id=package.id,
            knowledge_point_id=point.id,
            question="作品集讲解先讲什么？",
            options_json=json.dumps(["项目定位", "密钥内容"]),
            correct_answer="项目定位",
            explanation="先讲定位和真实边界。",
        )
    )
    db_session.add(LearningNote(title="面试草稿", content="强调真实边界。", tags_json=json.dumps(["portfolio"])))
    db_session.commit()
    db_session.refresh(source)
    return source
