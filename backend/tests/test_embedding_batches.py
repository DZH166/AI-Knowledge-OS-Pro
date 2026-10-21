from app.core.config import settings
from app.services.embedding_service import EmbeddingService


class CountingProvider:
    name = "counting"
    model = "counting-model"
    dimensions = 3

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def is_configured(self) -> bool:
        return True

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_embedding_batches(monkeypatch) -> None:
    provider = CountingProvider()
    monkeypatch.setattr(settings, "embedding_batch_size", 2)
    service = EmbeddingService(provider=provider)

    vectors = service.embed_texts(["a", "b", "c", "d", "e"])

    assert len(vectors) == 5
    assert [len(call) for call in provider.calls] == [2, 2, 1]
