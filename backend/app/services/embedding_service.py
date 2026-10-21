from app.core.config import settings
from app.services.providers import EmbeddingProvider, get_embedding_provider, safe_endpoint_fingerprint


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self.provider = provider or get_embedding_provider()

    def is_configured(self) -> bool:
        return self.provider.is_configured()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        batch_size = max(1, settings.embedding_batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(self.provider.embed_texts(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def fingerprint(self) -> str:
        if settings.demo_mode:
            endpoint = "demo"
        else:
            endpoint = safe_endpoint_fingerprint(settings.embedding_base_url)
        parts = [
            self.provider.name,
            endpoint,
            self.provider.model,
            str(self.provider.dimensions),
            settings.index_version,
            "cosine-normalized",
        ]
        return "::".join(parts)
