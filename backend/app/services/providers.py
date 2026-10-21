from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import logging
import math
import time
from typing import Any, Literal

import httpx

from app.core.config import Settings, settings
from app.core.errors import ConfigurationError, DependencyUnavailableError

logger = logging.getLogger(__name__)

CostStatus = Literal["reported", "estimated", "unknown"]


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0
    latency_ms: int = 0
    cost_micros: int | None = None
    cost_status: CostStatus = "unknown"
    estimated_usage: bool = True

    def __post_init__(self) -> None:
        if self.cost_micros is not None and self.cost_micros < 0:
            raise ValueError("LLM cost cannot be negative.")
        if self.cost_micros is None and self.cost_status != "unknown":
            raise ValueError("Known or estimated LLM cost requires cost_micros.")
        if self.cost_micros is not None and self.cost_status == "unknown":
            object.__setattr__(self, "cost_status", "reported")


@dataclass(frozen=True, slots=True)
class _TransportResult:
    payload: dict[str, Any]
    retries: int


class EmbeddingProvider(ABC):
    name: str

    @property
    @abstractmethod
    def dimensions(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class LLMProvider(ABC):
    name: str

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        started_at = time.perf_counter()
        text = self.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.perf_counter() - started_at) * 1_000),
            estimated_usage=True,
        )


def _should_retry_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _post_json_with_retry(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    max_retries: int,
    service_name: str,
    error_code: str,
) -> _TransportResult:
    attempt = 0
    while True:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code in {400, 401, 403, 404}:
                    raise DependencyUnavailableError(
                        f"{service_name} 配置或参数错误：HTTP {response.status_code}",
                        code=error_code,
                        retryable=False,
                    )
                response.raise_for_status()
                return _TransportResult(payload=response.json(), retries=attempt)
        except DependencyUnavailableError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            retryable = True
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            retryable = _should_retry_status(exc.response.status_code)
            last_exc = exc
        except httpx.HTTPError as exc:
            retryable = False
            last_exc = exc

        if not retryable or attempt >= max_retries:
            raise DependencyUnavailableError(f"{service_name} 调用失败：{last_exc}", code=error_code, retryable=retryable) from last_exc
        attempt += 1
        logger.warning("%s retry %s/%s after transient error: %s", service_name, attempt, max_retries, type(last_exc).__name__)
        time.sleep(min(2**attempt, 8))


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    name = "openai_compatible"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def dimensions(self) -> int:
        return self.config.embedding_dimensions

    @property
    def model(self) -> str:
        return self.config.embedding_model

    def is_configured(self) -> bool:
        return bool(self.config.embedding_api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.is_configured():
            raise ConfigurationError(
                "真实模式需要配置 EMBEDDING_API_KEY 或 OPENAI_API_KEY，或显式设置 DEMO_MODE=true。",
                code="EMBEDDING_NOT_CONFIGURED",
            )

        url = self.config.embedding_base_url.rstrip("/") + "/embeddings"
        headers = {"Authorization": f"Bearer {self.config.embedding_api_key}"}
        payload: dict[str, Any] = {"model": self.config.embedding_model, "input": texts}
        if self.config.embedding_dimensions:
            payload["dimensions"] = self.config.embedding_dimensions

        transport_result = _post_json_with_retry(
            url=url,
            headers=headers,
            payload=payload,
            timeout=self.config.embedding_timeout_seconds,
            max_retries=self.config.embedding_max_retries,
            service_name="Embedding 服务",
            error_code="EMBEDDING_CALL_FAILED",
        )
        data = transport_result.payload["data"]
        return [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]


class OpenAICompatibleLLMProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def model(self) -> str:
        return self.config.llm_model

    def is_configured(self) -> bool:
        return bool(self.config.llm_api_key)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.generate(system_prompt=system_prompt, user_prompt=user_prompt).text

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        return self._generate(system_prompt=system_prompt, user_prompt=user_prompt)

    def generate_bounded(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> LLMResult:
        """One HTTP attempt with an output cap and a reduced request timeout."""
        if max_output_tokens < 1 or timeout_seconds <= 0:
            raise ValueError("Bounded generation requires positive output and time limits.")
        return self._generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=0,
        )

    def _generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> LLMResult:
        if not self.is_configured():
            raise ConfigurationError(
                "真实模式需要配置 LLM_API_KEY 或 OPENAI_API_KEY，或显式设置 DEMO_MODE=true。",
                code="LLM_NOT_CONFIGURED",
            )

        url = self.config.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.llm_api_key}"}
        payload = {
            "model": self.config.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens

        started_at = time.perf_counter()
        transport_result = _post_json_with_retry(
            url=url,
            headers=headers,
            payload=payload,
            timeout=min(self.config.llm_timeout_seconds, timeout_seconds) if timeout_seconds is not None else self.config.llm_timeout_seconds,
            max_retries=self.config.llm_max_retries if max_retries is None else max_retries,
            service_name="LLM 服务",
            error_code="LLM_CALL_FAILED",
        )
        data = transport_result.payload
        usage = data.get("usage") or {}
        has_token_breakdown = (
            "prompt_tokens" in usage and "completion_tokens" in usage
        )
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        input_price = self.config.llm_input_cost_micros_per_million_tokens
        output_price = self.config.llm_output_cost_micros_per_million_tokens
        cost_micros: int | None = None
        cost_status: CostStatus = "unknown"
        if input_price is not None and output_price is not None and has_token_breakdown:
            unrounded_cost = input_tokens * input_price + output_tokens * output_price
            cost_micros = (unrounded_cost + 999_999) // 1_000_000
            cost_status = "estimated"
        return LLMResult(
            text=data["choices"][0]["message"]["content"].strip(),
            provider=self.name,
            model=str(data.get("model") or self.model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retries=transport_result.retries,
            latency_ms=int((time.perf_counter() - started_at) * 1_000),
            cost_micros=cost_micros,
            cost_status=cost_status,
            estimated_usage=not has_token_breakdown,
        )


class DemoEmbeddingProvider(EmbeddingProvider):
    name = "demo_hash"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def dimensions(self) -> int:
        return self.config.embedding_dimensions

    @property
    def model(self) -> str:
        return "local-hash-embedding"

    def is_configured(self) -> bool:
        return self.config.demo_mode

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.config.demo_mode:
            raise ConfigurationError("Demo embedding 只能在 DEMO_MODE=true 时启用。", code="DEMO_MODE_DISABLED")
        return [self._local_embedding(text) for text in texts]

    def _local_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.config.embedding_dimensions
        normalized_text = " ".join(text.lower().split())
        if not normalized_text:
            return vector

        words = normalized_text.split()
        features = words + [normalized_text[i : i + 3] for i in range(max(0, len(normalized_text) - 2))]
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.config.embedding_dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class DemoLLMProvider(LLMProvider):
    name = "demo_answer"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def model(self) -> str:
        return "local-demo-answer"

    def is_configured(self) -> bool:
        return self.config.demo_mode

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.config.demo_mode:
            raise ConfigurationError("Demo LLM 只能在 DEMO_MODE=true 时启用。", code="DEMO_MODE_DISABLED")
        preview = user_prompt[:700].strip()
        return (
            "这是 DEMO_MODE=true 下的演示回答。系统已经完成检索、上下文拼接、Prompt 构建和问答历史保存；"
            "但当前没有调用真实大模型，所以这不是正式答案。[1]\n\n"
            "建议下一步配置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL，以及 EMBEDDING_API_KEY、EMBEDDING_MODEL，"
            "然后关闭 DEMO_MODE 进入真实模式。\n\n"
            "本次用于生成回答的资料摘要：\n"
            f"{preview}"
        )


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    @property
    def dimensions(self) -> int:
        return settings.embedding_dimensions

    @property
    def model(self) -> str:
        return settings.embedding_model

    def is_configured(self) -> bool:
        return False

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Ollama embedding provider is reserved for a future version.")


class OllamaLLMProvider(LLMProvider):
    name = "ollama"

    @property
    def model(self) -> str:
        return settings.llm_model

    def is_configured(self) -> bool:
        return False

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError("Ollama LLM provider is reserved for a future version.")


def get_embedding_provider(config: Settings = settings) -> EmbeddingProvider:
    if config.demo_mode:
        return DemoEmbeddingProvider(config)
    if config.embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(config)
    if config.embedding_provider == "ollama":
        return OllamaEmbeddingProvider()
    raise ConfigurationError(f"Unsupported embedding provider: {config.embedding_provider}")


def get_llm_provider(config: Settings = settings) -> LLMProvider:
    if config.demo_mode:
        return DemoLLMProvider(config)
    if config.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMProvider(config)
    if config.llm_provider == "ollama":
        return OllamaLLMProvider()
    raise ConfigurationError(f"Unsupported LLM provider: {config.llm_provider}")


def safe_endpoint_fingerprint(url: str) -> str:
    host = url.rstrip("/").replace("https://", "").replace("http://", "").split("/")[0]
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:12]
