from app.models.document import Document
from app.models.source import MultimodalChunk
from app.services.rag_service import RAGService
from scripts import generate_learning_package
from scripts.release import ROOT, should_exclude
from tests.conftest import FakeLLMService
from tests.test_v3_5_video_transcription import FakeVideoTranscriptionProvider, make_video_upload


def test_document_rag_citations_include_document_id_for_deep_links(
    db_session,
    knowledge_space,
    fake_embedding,
    fake_vector_store,
    upload_factory,
) -> None:
    from app.services.ingestion_service import DocumentIngestionService

    ingestion = DocumentIngestionService(embedding_service=fake_embedding, vector_store=fake_vector_store)
    document, _job = ingestion.ingest_upload(db_session, knowledge_space.id, upload_factory(content="# RAG\nRAG needs citations."))

    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store
    service.llm_service = FakeLLMService()
    response = service.ask_question(db_session, knowledge_space.id, "What does RAG need?", "normal")

    assert db_session.query(Document).filter_by(id=document.id).one()
    assert response.citations
    assert response.citations[0].document_id == document.id
    assert response.citations[0].source_id is None
    assert response.related_chunks[0].document_id == document.id
    assert response.related_chunks[0].source_id is None


def test_video_rag_citations_include_source_id_and_timestamps(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
) -> None:
    from app.core.config import settings
    from app.services.media_service import MediaService
    from tests.conftest import FakeEmbeddingService, FakeVectorStore

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    fake_embedding = FakeEmbeddingService()
    fake_vector_store = FakeVectorStore()
    service = MediaService(
        transcription_provider=FakeVideoTranscriptionProvider(),
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )
    source = service.upload_video(db_session, knowledge_space.id, make_video_upload(tmp_path))
    source = service.process_audio_transcription(db_session, source.id)

    rag = RAGService()
    rag.embedding_service = fake_embedding
    rag.vector_store = fake_vector_store
    rag.llm_service = FakeLLMService()
    response = rag.ask_question(db_session, knowledge_space.id, "What is in the video?", "normal")

    assert db_session.query(MultimodalChunk).filter_by(source_id=source.id).count() >= 1
    assert response.citations
    assert response.citations[0].source_id == source.id
    assert response.citations[0].document_id is None
    assert response.citations[0].source_type == "video"
    assert response.citations[0].start_ms == 0
    assert response.related_chunks[0].source_id == source.id


def test_release_exclusion_rules_cover_sensitive_and_generated_paths() -> None:
    forbidden = [
        ROOT / ".env",
        ROOT / "backend" / "app.db",
        ROOT / "backend" / "storage" / "uploads" / "source.mp4",
        ROOT / "frontend" / ".next" / "BUILD_ID",
        ROOT / "frontend" / "node_modules" / "pkg" / "index.js",
        ROOT / "releases" / "old.zip",
        ROOT / "frontend" / "tsconfig.tsbuildinfo",
        ROOT / "sub2api" / ".git" / "config",
        ROOT / ".agents" / "local.json",
        ROOT / "vendor" / ".git" / "config",
    ]
    allowed = [
        ROOT / "README.md",
        ROOT / "backend" / "app" / "services" / "media_task_service.py",
        ROOT / "docs" / "v3_6_acceptance_report.md",
    ]

    assert all(should_exclude(path) for path in forbidden)
    assert not any(should_exclude(path) for path in allowed)


def test_learning_package_generator_is_v3_6_and_change_based(monkeypatch) -> None:
    changes = [
        generate_learning_package.GitChange("M", "backend/app/services/media_task_service.py"),
        generate_learning_package.GitChange("M", "frontend/components/CitationPanel.tsx"),
        generate_learning_package.GitChange("A", "backend/app/models/learning_artifact.py"),
        generate_learning_package.GitChange("M", "scripts/generate_learning_package.py"),
    ]
    monkeypatch.setattr(generate_learning_package, "collect_git_changes", lambda _from, _to: changes)
    monkeypatch.setattr(generate_learning_package, "collect_git_stat", lambda _from, _to: "4 files changed")
    monkeypatch.setattr(generate_learning_package, "collect_commits", lambda _from, _to: [])
    monkeypatch.setattr(generate_learning_package, "collect_routes", lambda: ["backend/app/api/routes_media.py::@router.post(\"/sources/{source_id}/process\")"])

    class Args:
        version = "V3.6"
        from_ref = None
        to_ref = "HEAD"
        goal = "V3.6 goal"
        test_report = None
        build_report = None
        migration_report = None

    package = generate_learning_package.build_package(Args())

    assert package["slug"] == "v3-6-unified-media-learning"
    assert "V3.6" in package["version_name"]
    assert any("Unified media" in feature for feature in package["implemented_features"])
    assert any(topic["name"] == "Media Task Orchestration" for topic in package["knowledge_points"])
    assert "V2.5" not in package["markdown_content"]
