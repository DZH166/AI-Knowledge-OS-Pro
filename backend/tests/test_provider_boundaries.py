from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import ConfigurationError
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
