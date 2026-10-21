from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RerankInput:
    query: str
    content: str
    metadata: dict


@dataclass(frozen=True)
class RerankOutput:
    score: float
    reason: str


class RerankProvider:
    """Optional rerank adapter boundary.

    V4.0 starts with a no-provider implementation so retrieval can degrade to
    deterministic fusion without inventing rerank scores.
    """

    name = "not_configured"

    def is_configured(self) -> bool:
        return False

    def rerank(self, query: str, items: list[RerankInput]) -> list[RerankOutput]:
        raise NotImplementedError("Rerank provider is not configured.")


class DisabledRerankProvider(RerankProvider):
    name = "disabled"


def get_rerank_provider() -> RerankProvider:
    return DisabledRerankProvider()
