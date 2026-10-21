from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings, settings
from app.core.errors import ConfigurationError, DependencyUnavailableError
from app.services.providers import _post_json_with_retry


@dataclass(frozen=True)
class OCRResult:
    text: str
    provider: str
    model: str
    confidence: float | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class VisionDescriptionResult:
    description: str
    content_type: str
    learning_points: list[str]
    provider: str
    model: str
    raw: dict[str, Any] | None = None


class OCRProvider(ABC):
    name: str

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract_text(self, image_path: Path, mime_type: str | None = None) -> OCRResult:
        raise NotImplementedError

    def describe_image(self, image_path: Path, mime_type: str | None = None) -> VisionDescriptionResult:
        raise ConfigurationError(
            "当前视觉 provider 不支持图片描述。系统不会生成伪视觉描述。",
            code="VISION_DESCRIPTION_NOT_CONFIGURED",
            details={"provider": self.name, "model": self.model},
        )


class OpenAICompatibleVisionOCRProvider(OCRProvider):
    name = "openai_compatible_vision"

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    @property
    def model(self) -> str:
        return self.config.ocr_model

    def is_configured(self) -> bool:
        return bool(self.config.ocr_api_key)

    def extract_text(self, image_path: Path, mime_type: str | None = None) -> OCRResult:
        if not self.is_configured():
            raise ConfigurationError(
                "真实图片 OCR 需要配置 OCR_API_KEY 或 OPENAI_API_KEY。当前不会生成伪 OCR 文本。",
                code="OCR_NOT_CONFIGURED",
                details={"provider": self.name, "model": self.model},
            )
        if not image_path.exists():
            raise ValueError("图片文件不存在，无法执行 OCR。")

        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime_type or 'image/png'};base64,{encoded}"
        payload = {
            "model": self.config.ocr_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是严格的 OCR 提取器。只提取图片中真实可见的文字。"
                        "如果图片里没有可读文字，回答空字符串。不要补充解释，不要猜测。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请提取这张图片中可见的所有文字，保留原有换行顺序。"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0,
        }
        try:
            data = _post_json_with_retry(
                url=self.config.ocr_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.config.ocr_api_key}"},
                payload=payload,
                timeout=self.config.ocr_timeout_seconds,
                max_retries=self.config.ocr_max_retries,
                service_name="图片 OCR 服务",
                error_code="OCR_CALL_FAILED",
            )
        except DependencyUnavailableError:
            raise
        except Exception as exc:
            raise DependencyUnavailableError(f"图片 OCR 调用失败：{exc}", code="OCR_CALL_FAILED") from exc
        text = str(data["choices"][0]["message"]["content"]).strip()
        return OCRResult(text=text, provider=self.name, model=self.model, raw={"usage": data.get("usage", {})})

    def describe_image(self, image_path: Path, mime_type: str | None = None) -> VisionDescriptionResult:
        if not self.is_configured():
            raise ConfigurationError(
                "真实视觉描述需要配置 OCR_API_KEY 或 OPENAI_API_KEY。当前不会生成伪描述。",
                code="VISION_DESCRIPTION_NOT_CONFIGURED",
                details={"provider": self.name, "model": self.model},
            )
        if not image_path.exists():
            raise ValueError("图片文件不存在，无法执行视觉描述。")

        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime_type or 'image/jpeg'};base64,{encoded}"
        payload = {
            "model": self.config.ocr_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是严格的学习资料视觉分析器。只描述图片中真实可见的信息，不猜测隐藏内容。"
                        "返回 JSON，字段为 description、content_type、learning_points。"
                        "content_type 只能是 error_screenshot、code_screenshot、chart、document、general。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请说明图片展示了什么、适合学习的重点，并识别它属于报错截图、代码截图、图表、文档还是普通图片。",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0,
        }
        data = _post_json_with_retry(
            url=self.config.ocr_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {self.config.ocr_api_key}"},
            payload=payload,
            timeout=self.config.ocr_timeout_seconds,
            max_retries=self.config.ocr_max_retries,
            service_name="视觉描述服务",
            error_code="VISION_DESCRIPTION_CALL_FAILED",
        )
        content = str(data["choices"][0]["message"]["content"]).strip()
        parsed = self._parse_description(content)
        return VisionDescriptionResult(
            description=parsed["description"],
            content_type=parsed["content_type"],
            learning_points=parsed["learning_points"],
            provider=self.name,
            model=self.model,
            raw={"usage": data.get("usage", {})},
        )

    @staticmethod
    def _parse_description(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            value = {"description": content, "content_type": "general", "learning_points": []}
        description = str(value.get("description") or "").strip()
        content_type = str(value.get("content_type") or "general").strip()
        allowed = {"error_screenshot", "code_screenshot", "chart", "document", "general"}
        if content_type not in allowed:
            content_type = "general"
        points = value.get("learning_points") if isinstance(value.get("learning_points"), list) else []
        return {
            "description": description,
            "content_type": content_type,
            "learning_points": [str(item).strip() for item in points if str(item).strip()],
        }


class UnconfiguredOCRProvider(OCRProvider):
    name = "unconfigured"

    @property
    def model(self) -> str:
        return "none"

    def is_configured(self) -> bool:
        return False

    def extract_text(self, image_path: Path, mime_type: str | None = None) -> OCRResult:
        raise ConfigurationError(
            "当前没有配置可用的 OCR provider。请配置 OCR_API_KEY/OCR_BASE_URL/OCR_MODEL。",
            code="OCR_NOT_CONFIGURED",
        )


def get_ocr_provider(config: Settings = settings) -> OCRProvider:
    if config.ocr_provider == "openai_compatible_vision":
        return OpenAICompatibleVisionOCRProvider(config)
    if config.ocr_provider in {"none", "disabled"}:
        return UnconfiguredOCRProvider()
    raise ConfigurationError(f"Unsupported OCR provider: {config.ocr_provider}", code="OCR_PROVIDER_UNSUPPORTED")
