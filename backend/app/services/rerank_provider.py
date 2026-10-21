from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import time
from typing import Any, NoReturn
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, settings
from app.core.errors import ConfigurationError, DependencyUnavailableError

logger = logging.getLogger(__name__)


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


class HttpRerankProvider(RerankProvider):
    name = "http"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self._api_key, self._url, self._model = _validated_configuration(config)

    def is_configured(self) -> bool:
        return True

    def rerank(self, query: str, items: list[RerankInput]) -> list[RerankOutput]:
        if not items:
            return []
        payload: dict[str, Any] = {
            "query": query,
            "documents": [item.content for item in items],
            "top_n": len(items),
            "model": self._model,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        response_payload = _post_json_with_retry(
            url=self._url,
            headers=headers,
            payload=payload,
            timeout=self.config.rerank_timeout_seconds,
            max_retries=self.config.rerank_max_retries,
        )
        return _parse_response(response_payload, expected_count=len(items))


def get_rerank_provider(config: Settings = settings) -> RerankProvider:
    configured = tuple(
        bool(value and value.strip())
        for value in (
            config.rerank_api_key,
            config.rerank_url,
            config.rerank_model,
        )
    )
    if not any(configured):
        return DisabledRerankProvider()
    return HttpRerankProvider(config)


def _validated_configuration(config: Settings) -> tuple[str, str, str]:
    api_key = (config.rerank_api_key or "").strip()
    url = (config.rerank_url or "").strip()
    model = (config.rerank_model or "").strip()
    parsed_url = urlparse(url)
    try:
        httpx_url: httpx.URL | None = httpx.URL(url)
    except httpx.InvalidURL:
        httpx_url = None
    if (
        not api_key
        or not url
        or not model
        or httpx_url is None
        or any(character.isspace() for character in url)
        or parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise ConfigurationError(
            "Rerank 需要完整的 API key、HTTP(S) URL 与 model 配置。",
            code="RERANK_CONFIGURATION_INVALID",
        )
    return api_key, url, model


def _post_json_with_retry(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    max_retries: int,
) -> Any:
    attempt = 0
    while True:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
            if 200 <= response.status_code < 300:
                try:
                    return response.json()
                except ValueError:
                    _raise_invalid_response()
            retryable = response.status_code in {408, 429} or response.status_code >= 500
            failure_kind = f"HTTP {response.status_code}"
        except httpx.TransportError as exc:
            retryable = True
            failure_kind = type(exc).__name__

        if not retryable or attempt >= max_retries:
            raise DependencyUnavailableError(
                "Rerank 服务暂时不可用。",
                code="RERANK_CALL_FAILED",
                details={"attempts": attempt + 1, "failure": failure_kind},
                retryable=retryable,
            )
        attempt += 1
        logger.warning(
            "Rerank retry %s/%s after transient provider failure (%s).",
            attempt,
            max_retries,
            failure_kind,
        )
        time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))


def _parse_response(payload: Any, *, expected_count: int) -> list[RerankOutput]:
    if not isinstance(payload, dict):
        _raise_invalid_response()
    results = payload.get("results", payload.get("data"))
    if not isinstance(results, list) or len(results) != expected_count:
        _raise_invalid_response()

    by_index: dict[int, RerankOutput] = {}
    for result in results:
        if not isinstance(result, dict):
            _raise_invalid_response()
        index = result.get("index")
        score = result.get("relevance_score", result.get("score"))
        if type(index) is not int or index < 0 or index >= expected_count:
            _raise_invalid_response()
        if index in by_index:
            _raise_invalid_response()
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            _raise_invalid_response()
        numeric_score = float(score)
        if not math.isfinite(numeric_score) or not 0.0 <= numeric_score <= 1.0:
            _raise_invalid_response()
        by_index[index] = RerankOutput(
            score=numeric_score,
            reason="http_rerank",
        )

    if set(by_index) != set(range(expected_count)):
        _raise_invalid_response()
    return [by_index[index] for index in range(expected_count)]


def _raise_invalid_response() -> NoReturn:
    raise DependencyUnavailableError(
        "Rerank 服务返回了无效或不完整的结果。",
        code="RERANK_RESPONSE_INVALID",
        retryable=False,
    )
