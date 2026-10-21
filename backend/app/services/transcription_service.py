from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import httpx

from app.core.config import Settings, settings
from app.core.errors import ConfigurationError, DependencyUnavailableError


@dataclass(frozen=True)
class TranscriptionSegmentResult:
    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None
    duration_ms: int | None
    segments: list[TranscriptionSegmentResult]
    provider: str
    model: str


class TranscriptionProvider(ABC):
    name: str

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def transcribe(self, audio_path: Path, mime_type: str | None = None) -> TranscriptionResult:
        raise NotImplementedError


class OpenAICompatibleTranscriptionProvider(TranscriptionProvider):
    name = "openai_compatible_audio"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def model(self) -> str:
        return self.config.transcription_model

    def is_configured(self) -> bool:
        return bool(self.config.transcription_api_key)

    def transcribe(self, audio_path: Path, mime_type: str | None = None) -> TranscriptionResult:
        if not self.is_configured():
            raise ConfigurationError(
                "真实音频转写需要配置 TRANSCRIPTION_API_KEY 或 OPENAI_API_KEY。当前不会生成伪转写。",
                code="TRANSCRIPTION_NOT_CONFIGURED",
                details={"provider": self.name, "model": self.model},
            )
        if not audio_path.exists():
            raise ValueError("音频文件不存在，无法执行转写。")

        data = self._request(audio_path, mime_type)
        text = str(data.get("text", "")).strip()
        raw_segments = data.get("segments") if isinstance(data.get("segments"), list) else []
        segments: list[TranscriptionSegmentResult] = []
        for index, item in enumerate(raw_segments):
            if not isinstance(item, dict):
                continue
            segment_text = str(item.get("text", "")).strip()
            if not segment_text:
                continue
            start_ms = max(0, int(float(item.get("start", 0)) * 1000))
            end_ms = max(start_ms, int(float(item.get("end", 0)) * 1000))
            segments.append(
                TranscriptionSegmentResult(
                    index=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=segment_text,
                    confidence=self._confidence(item),
                )
            )
        duration_ms = self._milliseconds(data.get("duration"))
        if text and not segments:
            segments.append(
                TranscriptionSegmentResult(
                    index=0,
                    start_ms=0,
                    end_ms=duration_ms or 0,
                    text=text,
                )
            )
        return TranscriptionResult(
            text=text or "\n".join(segment.text for segment in segments),
            language=str(data.get("language") or "").strip() or None,
            duration_ms=duration_ms,
            segments=segments,
            provider=self.name,
            model=self.model,
        )

    def _request(self, audio_path: Path, mime_type: str | None) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                with audio_path.open("rb") as handle, httpx.Client(timeout=self.config.transcription_timeout_seconds) as client:
                    response = client.post(
                        self.config.transcription_base_url.rstrip("/") + "/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.config.transcription_api_key}"},
                        data={"model": self.model, "response_format": "verbose_json"},
                        files={"file": (audio_path.name, handle, mime_type or "application/octet-stream")},
                    )
                if response.status_code in {400, 401, 403, 404}:
                    raise DependencyUnavailableError(
                        f"音频转写配置或参数错误：HTTP {response.status_code}",
                        code="TRANSCRIPTION_CALL_FAILED",
                        retryable=False,
                    )
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except DependencyUnavailableError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                retryable = True
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                last_exc = exc
            except httpx.HTTPError as exc:
                retryable = False
                last_exc = exc
            if not retryable or attempt >= self.config.transcription_max_retries:
                raise DependencyUnavailableError(
                    f"音频转写调用失败：{last_exc}",
                    code="TRANSCRIPTION_CALL_FAILED",
                    retryable=retryable,
                ) from last_exc
            attempt += 1
            time.sleep(min(2**attempt, 8))

    @staticmethod
    def _milliseconds(value: object) -> int | None:
        try:
            return max(0, int(float(value) * 1000)) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _confidence(item: dict[str, Any]) -> float | None:
        value = item.get("confidence")
        if value is None and item.get("avg_logprob") is not None:
            return None
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None


class UnconfiguredTranscriptionProvider(TranscriptionProvider):
    name = "unconfigured"

    @property
    def model(self) -> str:
        return "none"

    def is_configured(self) -> bool:
        return False

    def transcribe(self, audio_path: Path, mime_type: str | None = None) -> TranscriptionResult:
        raise ConfigurationError(
            "当前没有配置可用的音频转写 provider。",
            code="TRANSCRIPTION_NOT_CONFIGURED",
        )


def get_transcription_provider(config: Settings = settings) -> TranscriptionProvider:
    if config.transcription_provider == "openai_compatible_audio":
        return OpenAICompatibleTranscriptionProvider(config)
    if config.transcription_provider in {"none", "disabled"}:
        return UnconfiguredTranscriptionProvider()
    raise ConfigurationError(
        f"Unsupported transcription provider: {config.transcription_provider}",
        code="TRANSCRIPTION_PROVIDER_UNSUPPORTED",
    )
