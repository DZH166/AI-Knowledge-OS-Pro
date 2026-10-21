from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: F401,E402
from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.models.knowledge_space import KnowledgeSpace  # noqa: E402


class FakeEmbeddingService:
    def __init__(self, fingerprint: str = "fake::embedding::v2") -> None:
        self.provider = SimpleNamespace(name="fake", model="fake-embedding", dimensions=8)
        self._fingerprint = fingerprint

    def is_configured(self) -> bool:
        return True

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            base = float(len(text) or 1)
            vectors.append([base % (index + 3) / 10 for index in range(8)])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def fingerprint(self) -> str:
        return self._fingerprint


class FakeLLMService:
    def is_configured(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return "这是基于资料生成的测试回答 [1]"


class FakeHit:
    def __init__(self, score: float, payload: dict) -> None:
        self.score = score
        self.payload = payload


class FakeVectorStore:
    def __init__(self) -> None:
        self.points: dict[str, dict] = {}
        self.deleted: list[str] = []

    def ensure_collection(self) -> None:
        return None

    def upsert_chunks(self, point_ids: list[str], vectors: list[list[float]], payloads: list[dict]) -> None:
        for point_id, vector, payload in zip(point_ids, vectors, payloads, strict=True):
            self.points[point_id] = {"vector": vector, "payload": payload}

    def search(self, space_id: int, query_vector: list[float], limit: int | None = None, score_threshold: float | None = None):
        hits = []
        for item in self.points.values():
            payload = item["payload"]
            if payload["space_id"] == space_id:
                hits.append(FakeHit(0.92, payload))
        return hits[: limit or 5]

    def delete_points(self, point_ids: list[str]) -> None:
        self.deleted.extend(point_ids)
        for point_id in point_ids:
            self.points.pop(point_id, None)


class FakeTaskBroker:
    def __init__(self) -> None:
        self.enqueued: list[tuple[int, str]] = []
        self.cancelled: list[int] = []

    def enqueue_ingestion(self, job_id: int, queue_name: str = "default") -> str:
        self.enqueued.append((job_id, queue_name))
        return f"fake-ingestion-{job_id}"

    def enqueue_task(self, job_id: int, queue_name: str = "default") -> str:
        self.enqueued.append((job_id, queue_name))
        return f"fake-task-{job_id}"

    def cancel(self, job_id: int) -> bool:
        self.cancelled.append(job_id)
        return True


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def knowledge_space(db_session: Session) -> KnowledgeSpace:
    space = KnowledgeSpace(name="测试知识库", description="pytest")
    db_session.add(space)
    db_session.commit()
    db_session.refresh(space)
    return space


@pytest.fixture()
def fake_embedding() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture()
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture()
def fake_task_broker(monkeypatch: pytest.MonkeyPatch) -> FakeTaskBroker:
    broker = FakeTaskBroker()
    monkeypatch.setattr("app.services.ingestion_service.task_broker", broker)
    monkeypatch.setattr("app.services.task_broker.task_broker", broker)
    return broker


@pytest.fixture()
def upload_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    def factory(name: str = "rag.md", content: str = "# RAG\nRAG 是检索增强生成。") -> UploadFile:
        return UploadFile(filename=name, file=BytesIO(content.encode("utf-8")))

    return factory
