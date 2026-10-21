import json

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConfigurationError, DependencyUnavailableError
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_space import KnowledgeSpace
from app.services import rerank_provider as rerank_module
from app.services.hybrid_retriever import HybridRetriever
from app.services.rerank_provider import (
    DisabledRerankProvider,
    HttpRerankProvider,
    RerankInput,
    get_rerank_provider,
)


class EmptyVectorStore:
    def search(
        self,
        space_id: int,
        query_vector: list[float],
        limit: int | None = None,
        score_threshold: float | None = None,
    ) -> list:
        del space_id, query_vector, limit, score_threshold
        return []


def test_absent_rerank_configuration_stays_disabled_without_fake_scores() -> None:
    provider = get_rerank_provider(
        Settings(
            _env_file=None,
            rerank_api_key=None,
            rerank_url=None,
            rerank_model=None,
        )
    )

    assert isinstance(provider, DisabledRerankProvider)
    assert provider.is_configured() is False
    with pytest.raises(NotImplementedError):
        provider.rerank(
            "needle",
            [RerankInput(query="needle", content="document", metadata={})],
        )


def test_complete_rerank_configuration_selects_http_adapter() -> None:
    provider = get_rerank_provider(
        Settings(
            rerank_api_key="test-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
        )
    )

    assert isinstance(provider, HttpRerankProvider)
    assert provider.is_configured() is True


@pytest.mark.parametrize(
    ("api_key", "url", "model"),
    [
        ("test-key", None, "rerank-v1"),
        (None, "https://rerank.example.test/v1/rerank", "rerank-v1"),
        ("test-key", "https://rerank.example.test/v1/rerank", None),
        ("test-key", "file:///tmp/rerank", "rerank-v1"),
        ("test-key", "https://bad host/rerank", "rerank-v1"),
    ],
)
def test_partial_or_unsafe_rerank_configuration_fails_explicitly(
    api_key: str | None,
    url: str | None,
    model: str | None,
) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        get_rerank_provider(
            Settings(
                rerank_api_key=api_key,
                rerank_url=url,
                rerank_model=model,
            )
        )

    assert exc_info.value.code == "RERANK_CONFIGURATION_INVALID"


def test_http_rerank_maps_unordered_provider_results_back_to_every_input(
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.12},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        rerank_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = HttpRerankProvider(
        Settings(
            rerank_api_key="test-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
        )
    )
    items = [
        RerankInput(query="needle", content="first document", metadata={"id": 1}),
        RerankInput(query="needle", content="second document", metadata={"id": 2}),
    ]

    outputs = provider.rerank("needle", items)

    assert [output.score for output in outputs] == [0.12, 0.91]
    assert captured_payload == {
        "query": "needle",
        "documents": ["first document", "second document"],
        "top_n": 2,
        "model": "rerank-v1",
    }


@pytest.mark.parametrize(
    "response_payload",
    [
        {},
        {"results": "not-a-list"},
        {"results": [{"index": 0, "relevance_score": 0.5}]},
        {
            "results": [
                {"index": 0, "relevance_score": 0.5},
                {"index": 0, "relevance_score": 0.7},
            ]
        },
        {
            "results": [
                {"index": 0, "relevance_score": 0.5},
                {"index": 2, "relevance_score": 0.7},
            ]
        },
        {
            "results": [
                {"index": 0, "relevance_score": "NaN"},
                {"index": 1, "relevance_score": 0.7},
            ]
        },
        {
            "results": [
                {"index": 0, "relevance_score": 1.1},
                {"index": 1, "relevance_score": 0.7},
            ]
        },
        {
            "results": [
                {"index": True, "relevance_score": 0.5},
                {"index": 1, "relevance_score": 0.7},
            ]
        },
    ],
)
def test_invalid_or_incomplete_rerank_response_fails_explicitly(
    monkeypatch,
    response_payload: dict,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=response_payload)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        rerank_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = HttpRerankProvider(
        Settings(
            rerank_api_key="test-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
        )
    )
    items = [
        RerankInput(query="needle", content="first", metadata={}),
        RerankInput(query="needle", content="second", metadata={}),
    ]

    with pytest.raises(DependencyUnavailableError) as exc_info:
        provider.rerank("needle", items)

    assert exc_info.value.code == "RERANK_RESPONSE_INVALID"
    assert exc_info.value.retryable is False


def test_transient_rerank_failure_retries_with_bounded_timeout_without_logging_secrets(
    monkeypatch,
    caplog,
) -> None:
    attempts = 0
    observed_timeouts: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={"results": [{"index": 0, "score": 0.8}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(*, timeout: float) -> httpx.Client:
        observed_timeouts.append(timeout)
        return real_client(transport=transport, timeout=timeout)

    monkeypatch.setattr(rerank_module.httpx, "Client", client_factory)
    monkeypatch.setattr(rerank_module.time, "sleep", lambda _seconds: None)
    provider = HttpRerankProvider(
        Settings(
            rerank_api_key="super-secret-rerank-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
            rerank_timeout_seconds=0.25,
            rerank_max_retries=1,
        )
    )

    outputs = provider.rerank(
        "sensitive-query",
        [RerankInput(query="sensitive-query", content="private evidence body", metadata={})],
    )

    assert [output.score for output in outputs] == [0.8]
    assert attempts == 2
    assert observed_timeouts == [0.25, 0.25]
    assert "super-secret-rerank-key" not in caplog.text
    assert "sensitive-query" not in caplog.text
    assert "private evidence body" not in caplog.text


def test_rerank_timeout_exhaustion_is_an_explicit_retryable_dependency_error(
    monkeypatch,
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("provider timed out", request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        rerank_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    monkeypatch.setattr(rerank_module.time, "sleep", lambda _seconds: None)
    provider = HttpRerankProvider(
        Settings(
            rerank_api_key="test-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
            rerank_timeout_seconds=0.1,
            rerank_max_retries=2,
        )
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        provider.rerank(
            "needle",
            [RerankInput(query="needle", content="document", metadata={})],
        )

    assert attempts == 3
    assert exc_info.value.code == "RERANK_CALL_FAILED"
    assert exc_info.value.retryable is True
    assert exc_info.value.details == {"attempts": 3, "failure": "ReadTimeout"}


def test_hybrid_retrieval_uses_configured_http_reranker_at_existing_seam(
    monkeypatch,
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    first = _legacy_chunk(
        db_session,
        space_id=knowledge_space.id,
        filename="ordinary.md",
        content="needle ordinary evidence",
    )
    preferred = _legacy_chunk(
        db_session,
        space_id=knowledge_space.id,
        filename="preferred.md",
        content="needle preferred evidence",
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        documents = json.loads(request.content)["documents"]
        results = [
            {
                "index": index,
                "relevance_score": 0.95 if "preferred" in document else 0.05,
            }
            for index, document in enumerate(documents)
        ]
        return httpx.Response(200, request=request, json={"results": list(reversed(results))})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        rerank_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = HttpRerankProvider(
        Settings(
            rerank_api_key="test-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
        )
    )

    retriever = HybridRetriever(
        vector_store=EmptyVectorStore(),
        rerank_provider=provider,
    )
    results = retriever.search(
        db_session,
        space_id=knowledge_space.id,
        query="needle",
        query_vector=[0.0],
        limit=2,
        score_threshold=0.0,
    )

    assert calls == 1
    assert [result.chunk_id for result in results] == [preferred.id, first.id]
    assert [result.rerank_score for result in results] == [0.95, 0.05]
    assert results[1].final_score < 0.05
    assert all("rerank:http_rerank" in result.reason for result in results)

    filtered = retriever.search(
        db_session,
        space_id=knowledge_space.id,
        query="needle",
        query_vector=[0.0],
        limit=2,
    )

    assert calls == 2
    assert [result.chunk_id for result in filtered] == [preferred.id]
    assert filtered[0].final_score >= 0.15


def test_hybrid_retrieval_does_not_silently_fallback_when_configured_reranker_fails(
    monkeypatch,
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    _legacy_chunk(
        db_session,
        space_id=knowledge_space.id,
        filename="evidence.md",
        content="needle evidence",
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        rerank_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = HttpRerankProvider(
        Settings(
            rerank_api_key="test-key",
            rerank_url="https://rerank.example.test/v1/rerank",
            rerank_model="rerank-v1",
            rerank_max_retries=0,
        )
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        HybridRetriever(
            vector_store=EmptyVectorStore(),
            rerank_provider=provider,
        ).search(
            db_session,
            space_id=knowledge_space.id,
            query="needle",
            query_vector=[0.0],
            limit=1,
            score_threshold=0.0,
        )

    assert calls == 1
    assert exc_info.value.code == "RERANK_CALL_FAILED"


def _legacy_chunk(
    db: Session,
    *,
    space_id: int,
    filename: str,
    content: str,
) -> Chunk:
    document = Document(
        space_id=space_id,
        filename=filename,
        original_filename=filename,
        file_type="md",
        file_size=len(content),
        storage_path=filename,
        status="ready",
        parse_status="parsed",
        chunk_status="chunked",
        vector_status="indexed",
        processing_status="completed",
    )
    db.add(document)
    db.flush()
    chunk = Chunk(
        document_id=document.id,
        space_id=space_id,
        chunk_index=0,
        content=content,
        content_preview=content,
        char_count=len(content),
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk
