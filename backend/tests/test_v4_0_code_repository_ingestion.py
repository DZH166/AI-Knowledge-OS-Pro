from fastapi.testclient import TestClient
import pytest

from app.core.errors import ConfigurationError
from app.db.session import get_db
from app.main import app
from app.models.source import CitationLocator, MultimodalChunk
from app.services.code_repository_service import CodeRepositoryService
from app.services.rag_service import RAGService
from tests.conftest import FakeLLMService


class UnconfiguredEmbedding:
    def is_configured(self) -> bool:
        return False


def test_code_repository_ingestion_skips_sensitive_files_and_creates_code_locators(
    db_session,
    knowledge_space,
    tmp_path,
    fake_embedding,
    fake_vector_store,
) -> None:
    repo = tmp_path / "sample-repo"
    (repo / "app").mkdir(parents=True)
    (repo / "node_modules").mkdir()
    (repo / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/health')\ndef health():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("# Sample\n\nThis project uses FastAPI routes.\n", encoding="utf-8")
    (repo / ".env").write_text("OPENAI_API_KEY=secret-value\n", encoding="utf-8")
    (repo / "node_modules" / "ignored.js").write_text("const secret = 'ignore';\n", encoding="utf-8")

    service = CodeRepositoryService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    source, file_count, skipped_count = service.ingest_local_repository(
        db_session,
        space_id=knowledge_space.id,
        local_path=str(repo),
        github_url="https://github.com/example/sample-repo",
    )

    chunks = db_session.query(MultimodalChunk).order_by(MultimodalChunk.chunk_index).all()
    assert source.source_type == "code_repository"
    assert file_count == 2
    assert skipped_count >= 1
    assert len(chunks) == 2
    assert all("secret-value" not in chunk.content_text for chunk in chunks)
    assert all(chunk.qdrant_point_id for chunk in chunks)
    assert db_session.query(CitationLocator).count() == len(chunks)

    first_payload = next(iter(fake_vector_store.points.values()))["payload"]
    assert first_payload["source_type"] == "code_repository"
    assert first_payload["file_path"] in {"README.md", "app/main.py"}
    assert first_payload["line_start"] >= 1
    assert "symbol_name" in first_payload

    rag = RAGService()
    rag.embedding_service = fake_embedding
    rag.vector_store = fake_vector_store
    rag.llm_service = FakeLLMService()
    response = rag.ask_question(db_session, knowledge_space.id, "FastAPI health route 在哪里？", "normal")
    assert response.retrieval_status == "success"
    assert response.citations[0].source_type == "code_repository"
    assert response.citations[0].file_path
    assert response.citations[0].line_start
    assert response.citations[0].line_end


def test_code_repository_ingestion_requires_embedding_provider(db_session, knowledge_space, tmp_path) -> None:
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    service = CodeRepositoryService(embedding_service=UnconfiguredEmbedding())  # type: ignore[arg-type]

    with pytest.raises(ConfigurationError) as exc_info:
        service.ingest_local_repository(db_session, space_id=knowledge_space.id, local_path=str(repo))

    assert exc_info.value.code == "EMBEDDING_NOT_CONFIGURED"


def test_code_repository_ingestion_route_returns_source_contract(
    db_session,
    knowledge_space,
    tmp_path,
    fake_embedding,
    fake_vector_store,
    monkeypatch,
) -> None:
    repo = tmp_path / "route-repo"
    repo.mkdir()
    (repo / "main.py").write_text("def route_contract():\n    return 'ok'\n", encoding="utf-8")
    service = CodeRepositoryService(embedding_service=fake_embedding, vector_store=fake_vector_store)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("app.api.routes_code_repositories.code_repository_service", service)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/code-repositories/ingest-local",
            json={"space_id": knowledge_space.id, "local_path": str(repo), "max_files": 10},
        )
        assert response.status_code == 201
        payload = response.json()["data"]
        assert payload["source"]["source_type"] == "code_repository"
        assert payload["file_count"] == 1
        assert payload["chunk_count"] >= 1
        assert payload["source"]["revisions"][0]["chunks"][0]["modality"] == "code_file"
    finally:
        app.dependency_overrides.pop(get_db, None)
