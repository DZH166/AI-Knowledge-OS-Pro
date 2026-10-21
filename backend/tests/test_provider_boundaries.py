from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.services import providers as provider_module
from app.services.ocr_service import OpenAICompatibleVisionOCRProvider
from app.services.providers import OpenAICompatibleEmbeddingProvider, OpenAICompatibleLLMProvider
from app.services.rerank_provider import get_rerank_provider
from app.services.transcription_service import OpenAICompatibleTranscriptionProvider


def test_real_mode_llm_embedding_ocr_and_transcription_refuse_without_keys(tmp_path: Path) -> None:
    config = Settings(
        demo_mode=False,
        llm_api_key=None,
        embedding_api_key=None,
        ocr_api_key=None,
        transcription_api_key=None,
    )
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")

    with pytest.raises(ConfigurationError) as llm_error:
        OpenAICompatibleLLMProvider(config).complete("system", "question")
    assert llm_error.value.code == "LLM_NOT_CONFIGURED"

    with pytest.raises(ConfigurationError) as embedding_error:
        OpenAICompatibleEmbeddingProvider(config).embed_texts(["RAG"])
    assert embedding_error.value.code == "EMBEDDING_NOT_CONFIGURED"

    ocr_provider = OpenAICompatibleVisionOCRProvider(config)
    with pytest.raises(ConfigurationError) as ocr_error:
        ocr_provider.extract_text(image_path, "image/png")
    assert ocr_error.value.code == "OCR_NOT_CONFIGURED"

    with pytest.raises(ConfigurationError) as vision_error:
        ocr_provider.describe_image(image_path, "image/png")
    assert vision_error.value.code == "VISION_DESCRIPTION_NOT_CONFIGURED"

    with pytest.raises(ConfigurationError) as transcription_error:
        OpenAICompatibleTranscriptionProvider(config).transcribe(audio_path, "audio/wav")
    assert transcription_error.value.code == "TRANSCRIPTION_NOT_CONFIGURED"


def test_rerank_boundary_degrades_without_fake_scores() -> None:
    provider = get_rerank_provider()

    assert provider.is_configured() is False
    assert provider.name == "disabled"
    with pytest.raises(NotImplementedError):
        provider.rerank("query", [])


def test_openai_compatible_llm_reports_transport_retries(monkeypatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": "grounded"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        provider_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    monkeypatch.setattr(provider_module.time, "sleep", lambda _seconds: None)
    provider = OpenAICompatibleLLMProvider(
        Settings(llm_api_key="test-key", llm_max_retries=1)
    )

    result = provider.generate(system_prompt="system", user_prompt="question")

    assert result.text == "grounded"
    assert result.retries == 1
    assert attempts == 2


def test_openai_compatible_llm_keeps_unconfigured_cost_explicitly_unknown(
    monkeypatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": "grounded"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        provider_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key"))

    result = provider.generate(system_prompt="system", user_prompt="question")

    assert result.cost_micros is None
    assert result.cost_status == "unknown"


def test_openai_compatible_llm_estimates_cost_only_from_explicit_prices(
    monkeypatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": "grounded"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        provider_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = OpenAICompatibleLLMProvider(
        Settings(
            llm_api_key="test-key",
            llm_input_cost_micros_per_million_tokens=2_000_000,
            llm_output_cost_micros_per_million_tokens=3_000_000,
        )
    )

    result = provider.generate(system_prompt="system", user_prompt="question")

    assert result.cost_micros == 26
    assert result.cost_status == "estimated"


def test_configured_prices_still_report_unknown_when_token_breakdown_is_missing(
    monkeypatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": "grounded"}}],
                "usage": {"total_tokens": 12},
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        provider_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    provider = OpenAICompatibleLLMProvider(
        Settings(
            llm_api_key="test-key",
            llm_input_cost_micros_per_million_tokens=2_000_000,
            llm_output_cost_micros_per_million_tokens=3_000_000,
        )
    )

    result = provider.generate(system_prompt="system", user_prompt="question")

    assert result.cost_micros is None
    assert result.cost_status == "unknown"
