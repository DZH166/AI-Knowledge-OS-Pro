import json
import subprocess
import sys

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import ConfigurationError
from app.db.session import get_db
from app.main import app
from app.models.document import Document
from app.models.source import CitationLocator, IndexRevision, MultimodalChunk, Source, SourceRevision
from app.schemas.system_schema import ComponentStatus
from app.services.rag_service import rag_service
from app.services.system_service import system_service
from scripts import release
from scripts.seed_demo_data import main as seed_demo_main
from tests.conftest import FakeEmbeddingService, FakeVectorStore


class UnconfiguredLLMService:
    def is_configured(self) -> bool:
        return False

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise ConfigurationError("LLM provider is not configured.", code="LLM_NOT_CONFIGURED")


def test_v4_3_static_quality_gate_scripts_pass() -> None:
    commands = [
        [sys.executable, "scripts/check_docs_links.py"],
        [sys.executable, "scripts/check_readme_assets.py"],
        [sys.executable, "scripts/check_all.py", "--quick"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=release.ROOT, text=True, capture_output=True, check=True)
        assert "result=passed" in completed.stdout


def test_v4_3_demo_walkthrough_scripts_pass_on_isolated_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "demo_showcase.db"
    monkeypatch.setattr(sys, "argv", ["seed_demo_data.py", "--database-path", str(database), "--reset"])
    seed_demo_main()

    commands = [
        [sys.executable, "scripts/check_demo_ready.py", "--database-path", str(database)],
        [sys.executable, "scripts/evaluate_rag.py", "--demo", "--database-path", str(database)],
        [sys.executable, "scripts/check_full_regression.py", "--database-path", str(database)],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=release.ROOT, text=True, capture_output=True, check=True)
        assert "result=passed" in completed.stdout or "Demo readiness check passed" in completed.stdout


def test_v4_3_core_api_routes_return_enveloped_contracts(db_session, knowledge_space, monkeypatch) -> None:
    monkeypatch.setattr(
        system_service,
        "_qdrant_status",
        lambda: ComponentStatus(ok=False, status="unavailable", message="Qdrant unavailable", details={"error": "test"}),
    )
    monkeypatch.setattr(
        system_service,
        "_redis_status",
        lambda: ComponentStatus(ok=False, status="unavailable", message="Redis unavailable", details={"error": "test"}),
    )

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        assert client.get("/health").json()["version"] == "V4.4"

        endpoints = [
            "/api/dashboard/summary",
            "/api/system/status",
            "/api/media/sources",
            "/api/ingestion-jobs",
            "/api/learning/logs",
            "/api/chat/history",
            "/api/portfolio/summary",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, endpoint
            payload = response.json()
            assert payload["success"] is True
            assert "data" in payload
            assert payload["request_id"]

        status = client.get("/api/system/status").json()["data"]
        assert status["runtime"]["app_version"] == "V4.4"
        assert status["llm"]["status"] in {"not_configured", "configured", "demo"}
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_v4_3_chat_missing_llm_refuses_without_fake_answer(db_session, knowledge_space) -> None:
    fake_embedding = FakeEmbeddingService()
    fake_vector_store = FakeVectorStore()
    fake_vector_store.points["point-1"] = {
        "vector": [0.1] * 8,
        "payload": {
            "space_id": knowledge_space.id,
            "chunk_id": 1,
            "chunk_index": 0,
            "document_name": "provider-boundary.md",
            "content": "Provider boundaries require NOT_CONFIGURED errors.",
            "content_preview": "Provider boundaries require NOT_CONFIGURED errors.",
            "document_id": 1,
            "source_type": "document",
            "citation_ready": True,
        },
    }
    document = Document(
        id=1,
        space_id=knowledge_space.id,
        filename="provider-boundary.md",
        original_filename="provider-boundary.md",
        file_type="md",
        content_type="text/markdown",
        file_size=128,
        storage_path="/tmp/provider-boundary.md",
        status="ready",
        parse_status="parsed",
        chunk_status="chunked",
        vector_status="indexed",
        processing_status="completed",
        embedding_fingerprint=fake_embedding.fingerprint(),
        index_version=settings.index_version,
        chunk_count=1,
    )
    db_session.add(document)
    db_session.commit()

    original_embedding = rag_service.embedding_service
    original_vector_store = rag_service.vector_store
    original_llm = rag_service.llm_service
    rag_service.embedding_service = fake_embedding  # type: ignore[assignment]
    rag_service.vector_store = fake_vector_store  # type: ignore[assignment]
    rag_service.llm_service = UnconfiguredLLMService()  # type: ignore[assignment]

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/ask",
            json={"space_id": knowledge_space.id, "question": "How should missing providers behave?", "answer_mode": "normal"},
        )
        assert response.status_code == 503
        payload = response.json()
        assert payload["error"]["code"] == "LLM_NOT_CONFIGURED"
        assert payload["data"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        rag_service.embedding_service = original_embedding
        rag_service.vector_store = original_vector_store
        rag_service.llm_service = original_llm


def test_v4_3_learning_action_uses_real_multimodal_chunk(db_session, knowledge_space) -> None:
    source = Source(
        space_id=knowledge_space.id,
        source_type="video",
        title="V4.3 demo video",
        original_filename="v4_3_demo.mp4",
        mime_type="video/mp4",
        file_size=1024,
        status="ready",
    )
    db_session.add(source)
    db_session.flush()
    revision = SourceRevision(
        source_id=source.id,
        revision_number=1,
        status="active",
        chunk_count=1,
        vector_count=1,
        validation_status="passed",
    )
    db_session.add(revision)
    db_session.flush()
    source.active_revision_id = revision.id
    source.latest_revision_id = revision.id
    chunk = MultimodalChunk(
        source_id=source.id,
        revision_id=revision.id,
        chunk_index=0,
        modality="video_transcript",
        source_type="video",
        content_text="V4.3 validates README links, provider boundaries and release readiness with real checks.",
        search_text="V4.3 validates README links, provider boundaries and release readiness with real checks.",
        locator_json=json.dumps({"type": "video", "start_ms": 0, "end_ms": 4000}),
        start_ms=0,
        end_ms=4000,
        status="active",
    )
    db_session.add(chunk)
    db_session.flush()
    db_session.add(
        CitationLocator(
            source_id=source.id,
            revision_id=revision.id,
            chunk_id=chunk.id,
            locator_json=json.dumps({"source_type": "video", "start_ms": 0, "end_ms": 4000}),
            display_text="video 00:00",
        )
    )
    db_session.add(
        IndexRevision(
            source_id=source.id,
            revision_id=revision.id,
            status="active",
            index_version=settings.index_version,
            embedding_fingerprint="fake::embedding::v2",
            point_count=1,
            validation_status="passed",
        )
    )
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/learning/from-source",
            json={
                "source_id": source.id,
                "chunk_id": chunk.id,
                "artifact_types": ["knowledge_point", "card", "quiz", "note", "interview_expression"],
                "title": "V4.3 quality gates",
            },
        )
        assert response.status_code == 201
        payload = response.json()["data"]
        assert len(payload["artifacts"]) == 5
        assert all(item["source_id"] == source.id for item in payload["artifacts"])
    finally:
        app.dependency_overrides.pop(get_db, None)
