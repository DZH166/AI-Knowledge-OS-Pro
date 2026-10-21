from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import wave


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


NOT_CONFIGURED = {
    "llm": "LLM_NOT_CONFIGURED",
    "embedding": "EMBEDDING_NOT_CONFIGURED",
    "ocr": "OCR_NOT_CONFIGURED",
    "vision_description": "VISION_DESCRIPTION_NOT_CONFIGURED",
    "transcription": "TRANSCRIPTION_NOT_CONFIGURED",
    "rerank": "RERANK_NOT_CONFIGURED",
}


@dataclass(frozen=True)
class ProviderEvalResult:
    name: str
    provider: str
    model: str
    status: str
    error_code: str | None
    endpoint_fingerprint: str | None
    duration_ms: int
    note: str


@dataclass(frozen=True)
class DryRunSettings:
    llm_provider: str = "openai_compatible"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    embedding_provider: str = "openai_compatible"
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None
    ocr_provider: str = "openai_compatible_vision"
    ocr_model: str = "gpt-4o-mini"
    ocr_base_url: str = "https://api.openai.com/v1"
    ocr_api_key: str | None = None
    transcription_provider: str = "openai_compatible_audio"
    transcription_model: str = "whisper-1"
    transcription_base_url: str = "https://api.openai.com/v1"
    transcription_api_key: str | None = None


def env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def dry_run_settings() -> DryRunSettings:
    return DryRunSettings(
        llm_provider=env_first("LLM_PROVIDER", default="openai_compatible") or "openai_compatible",
        llm_model=env_first("LLM_MODEL", "CHAT_MODEL", default="gpt-4o-mini") or "gpt-4o-mini",
        llm_base_url=env_first("LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1") or "https://api.openai.com/v1",
        llm_api_key=env_first("LLM_API_KEY", "OPENAI_API_KEY"),
        embedding_provider=env_first("EMBEDDING_PROVIDER", default="openai_compatible") or "openai_compatible",
        embedding_model=env_first("EMBEDDING_MODEL", default="text-embedding-3-small") or "text-embedding-3-small",
        embedding_base_url=env_first("EMBEDDING_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1") or "https://api.openai.com/v1",
        embedding_api_key=env_first("EMBEDDING_API_KEY", "OPENAI_API_KEY"),
        ocr_provider=env_first("OCR_PROVIDER", default="openai_compatible_vision") or "openai_compatible_vision",
        ocr_model=env_first("OCR_MODEL", default="gpt-4o-mini") or "gpt-4o-mini",
        ocr_base_url=env_first("OCR_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1") or "https://api.openai.com/v1",
        ocr_api_key=env_first("OCR_API_KEY", "OPENAI_API_KEY"),
        transcription_provider=env_first("TRANSCRIPTION_PROVIDER", default="openai_compatible_audio") or "openai_compatible_audio",
        transcription_model=env_first("TRANSCRIPTION_MODEL", default="whisper-1") or "whisper-1",
        transcription_base_url=env_first("TRANSCRIPTION_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1") or "https://api.openai.com/v1",
        transcription_api_key=env_first("TRANSCRIPTION_API_KEY", "OPENAI_API_KEY"),
    )


def ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def safe_endpoint_fingerprint(url: str) -> str:
    host = url.rstrip("/").replace("https://", "").replace("http://", "").split("/")[0]
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:12]


def endpoint_for(config: object, name: str) -> str | None:
    if name == "llm":
        return safe_endpoint_fingerprint(config.llm_base_url)
    if name == "embedding":
        return safe_endpoint_fingerprint(config.embedding_base_url)
    if name in {"ocr", "vision_description"}:
        return safe_endpoint_fingerprint(config.ocr_base_url)
    if name == "transcription":
        return safe_endpoint_fingerprint(config.transcription_base_url)
    return None


def configured_map(config: object) -> dict[str, bool]:
    return {
        "llm": bool(config.llm_api_key),
        "embedding": bool(config.embedding_api_key),
        "ocr": bool(config.ocr_api_key),
        "vision_description": bool(config.ocr_api_key),
        "transcription": bool(config.transcription_api_key),
        "rerank": False,
    }


def dry_run(config: object) -> list[ProviderEvalResult]:
    configured = configured_map(config)
    providers = {
        "llm": (config.llm_provider, config.llm_model),
        "embedding": (config.embedding_provider, config.embedding_model),
        "ocr": (config.ocr_provider, config.ocr_model),
        "vision_description": (config.ocr_provider, config.ocr_model),
        "transcription": (config.transcription_provider, config.transcription_model),
        "rerank": ("disabled", "none"),
    }
    results: list[ProviderEvalResult] = []
    for name, (provider, model) in providers.items():
        ok = configured[name]
        results.append(
            ProviderEvalResult(
                name=name,
                provider=provider,
                model=model,
                status="configured" if ok else "not_configured",
                error_code=None if ok else NOT_CONFIGURED[name],
                endpoint_fingerprint=endpoint_for(config, name),
                duration_ms=0,
                note="No provider call was made in dry-run mode.",
            )
        )
    return results


def demo_eval() -> list[ProviderEvalResult]:
    from app.core.config import Settings
    from app.services.providers import get_embedding_provider, get_llm_provider
    from app.services.rerank_provider import get_rerank_provider

    config = Settings(demo_mode=True)
    started = time.perf_counter()
    embedding = get_embedding_provider(config)
    embedding.embed_texts(["AI Knowledge OS Pro demo provider evaluation"])
    embedding_duration = ms(started)

    started = time.perf_counter()
    llm = get_llm_provider(config)
    llm.complete("Return a concise demo response.", "Explain demo provider boundaries in one sentence.")
    llm_duration = ms(started)

    return [
        ProviderEvalResult(
            name="embedding",
            provider=embedding.name,
            model=embedding.model,
            status="passed",
            error_code=None,
            endpoint_fingerprint=None,
            duration_ms=embedding_duration,
            note="DEMO_MODE local hash embedding executed without network calls.",
        ),
        ProviderEvalResult(
            name="llm",
            provider=llm.name,
            model=llm.model,
            status="passed",
            error_code=None,
            endpoint_fingerprint=None,
            duration_ms=llm_duration,
            note="DEMO_MODE local answer provider executed without network calls.",
        ),
        ProviderEvalResult(
            name="ocr",
            provider=config.ocr_provider,
            model=config.ocr_model,
            status="not_configured",
            error_code=NOT_CONFIGURED["ocr"],
            endpoint_fingerprint=None,
            duration_ms=0,
            note="Demo mode does not invent OCR text.",
        ),
        ProviderEvalResult(
            name="transcription",
            provider=config.transcription_provider,
            model=config.transcription_model,
            status="not_configured",
            error_code=NOT_CONFIGURED["transcription"],
            endpoint_fingerprint=None,
            duration_ms=0,
            note="Demo mode does not invent transcripts.",
        ),
        ProviderEvalResult(
            name="rerank",
            provider=get_rerank_provider().name,
            model="none",
            status="not_configured",
            error_code=NOT_CONFIGURED["rerank"],
            endpoint_fingerprint=None,
            duration_ms=0,
            note="Rerank remains disabled; retrieval must not invent rerank scores.",
        ),
    ]


def tiny_png(path: Path) -> None:
    # 1x1 transparent PNG.
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c6360000002000100ffff03000006000557bfab1d00000000"
            "49454e44ae426082"
        )
    )


def tiny_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 1600)


def result_from_error(name: str, provider: str, model: str, started: float, exc: Exception, endpoint: str | None) -> ProviderEvalResult:
    code = getattr(exc, "code", None) or f"{name.upper()}_CALL_FAILED"
    status = "not_configured" if str(code).endswith("NOT_CONFIGURED") else "failed"
    return ProviderEvalResult(
        name=name,
        provider=provider,
        model=model,
        status=status,
        error_code=str(code),
        endpoint_fingerprint=endpoint,
        duration_ms=ms(started),
        note=str(exc).replace("\n", " ")[:240],
    )


def probe_real_if_configured(config: object) -> list[ProviderEvalResult]:
    from app.core.errors import ConfigurationError, DependencyUnavailableError
    from app.services.ocr_service import get_ocr_provider
    from app.services.providers import get_embedding_provider, get_llm_provider
    from app.services.rerank_provider import get_rerank_provider
    from app.services.transcription_service import get_transcription_provider

    results: list[ProviderEvalResult] = []

    embedding = get_embedding_provider(config)
    started = time.perf_counter()
    if embedding.is_configured():
        try:
            embedding.embed_texts(["AI Knowledge OS Pro provider smoke test."])
            results.append(
                ProviderEvalResult("embedding", embedding.name, embedding.model, "passed", None, endpoint_for(config, "embedding"), ms(started), "Real embedding call succeeded.")
            )
        except (ConfigurationError, DependencyUnavailableError, Exception) as exc:
            results.append(result_from_error("embedding", embedding.name, embedding.model, started, exc, endpoint_for(config, "embedding")))
    else:
        results.append(ProviderEvalResult("embedding", embedding.name, embedding.model, "not_configured", NOT_CONFIGURED["embedding"], endpoint_for(config, "embedding"), 0, "Skipped real call because no embedding key is configured."))

    llm = get_llm_provider(config)
    started = time.perf_counter()
    if llm.is_configured():
        try:
            llm.complete("Return exactly OK.", "Provider smoke test.")
            results.append(ProviderEvalResult("llm", llm.name, llm.model, "passed", None, endpoint_for(config, "llm"), ms(started), "Real LLM call succeeded."))
        except (ConfigurationError, DependencyUnavailableError, Exception) as exc:
            results.append(result_from_error("llm", llm.name, llm.model, started, exc, endpoint_for(config, "llm")))
    else:
        results.append(ProviderEvalResult("llm", llm.name, llm.model, "not_configured", NOT_CONFIGURED["llm"], endpoint_for(config, "llm"), 0, "Skipped real call because no LLM key is configured."))

    ocr = get_ocr_provider(config)
    with tempfile.TemporaryDirectory() as tmp:
        image_path = Path(tmp) / "provider-smoke.png"
        tiny_png(image_path)
        started = time.perf_counter()
        if ocr.is_configured():
            try:
                ocr.extract_text(image_path, "image/png")
                results.append(ProviderEvalResult("ocr", ocr.name, ocr.model, "passed", None, endpoint_for(config, "ocr"), ms(started), "Real OCR call succeeded."))
            except (ConfigurationError, DependencyUnavailableError, Exception) as exc:
                results.append(result_from_error("ocr", ocr.name, ocr.model, started, exc, endpoint_for(config, "ocr")))
            started = time.perf_counter()
            try:
                ocr.describe_image(image_path, "image/png")
                results.append(ProviderEvalResult("vision_description", ocr.name, ocr.model, "passed", None, endpoint_for(config, "vision_description"), ms(started), "Real vision description call succeeded."))
            except (ConfigurationError, DependencyUnavailableError, Exception) as exc:
                results.append(result_from_error("vision_description", ocr.name, ocr.model, started, exc, endpoint_for(config, "vision_description")))
        else:
            results.append(ProviderEvalResult("ocr", ocr.name, ocr.model, "not_configured", NOT_CONFIGURED["ocr"], endpoint_for(config, "ocr"), 0, "Skipped real call because no OCR key is configured."))
            results.append(ProviderEvalResult("vision_description", ocr.name, ocr.model, "not_configured", NOT_CONFIGURED["vision_description"], endpoint_for(config, "vision_description"), 0, "Skipped real call because no OCR/vision key is configured."))

        transcription = get_transcription_provider(config)
        audio_path = Path(tmp) / "provider-smoke.wav"
        tiny_wav(audio_path)
        started = time.perf_counter()
        if transcription.is_configured():
            try:
                transcription.transcribe(audio_path, "audio/wav")
                results.append(ProviderEvalResult("transcription", transcription.name, transcription.model, "passed", None, endpoint_for(config, "transcription"), ms(started), "Real transcription call succeeded."))
            except (ConfigurationError, DependencyUnavailableError, Exception) as exc:
                results.append(result_from_error("transcription", transcription.name, transcription.model, started, exc, endpoint_for(config, "transcription")))
        else:
            results.append(ProviderEvalResult("transcription", transcription.name, transcription.model, "not_configured", NOT_CONFIGURED["transcription"], endpoint_for(config, "transcription"), 0, "Skipped real call because no transcription key is configured."))

    rerank = get_rerank_provider()
    results.append(ProviderEvalResult("rerank", rerank.name, "none", "not_configured", NOT_CONFIGURED["rerank"], None, 0, "Rerank is disabled by design in this release."))
    return results


def write_reports(results: list[ProviderEvalResult], *, mode: str, json_output: Path | None, markdown_output: Path | None) -> None:
    payload = {"mode": mode, "results": [asdict(item) for item in results]}
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# V4.4 Provider Evaluation ({mode})",
            "",
            "| Provider | Status | Error code | Model | Endpoint | Duration | Note |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
        for item in results:
            lines.append(
                f"| {item.name} | {item.status} | {item.error_code or '-'} | {item.provider}/{item.model} | "
                f"{item.endpoint_fingerprint or '-'} | {item.duration_ms}ms | {item.note} |"
            )
        markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_results(results: list[ProviderEvalResult], *, mode: str) -> None:
    print(f"provider_eval_mode={mode}")
    for item in results:
        print(
            "provider={name} status={status} error_code={error} model={provider}/{model} endpoint={endpoint} duration_ms={duration} note={note}".format(
                name=item.name,
                status=item.status,
                error=item.error_code or "-",
                provider=item.provider,
                model=item.model,
                endpoint=item.endpoint_fingerprint or "-",
                duration=item.duration_ms,
                note=item.note,
            )
        )
    failed = [item for item in results if item.status == "failed"]
    print("result=failed" if failed else "result=passed")
    if failed:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate provider readiness without leaking keys or inventing AI output.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Inspect configuration only; do not call providers.")
    mode.add_argument("--demo", action="store_true", help="Run local demo-provider checks only.")
    mode.add_argument("--real-if-configured", action="store_true", help="Call providers only when the required key is configured.")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    if args.demo:
        selected = "demo"
        results = demo_eval()
    elif args.real_if_configured:
        from app.core.config import settings

        selected = "real-if-configured"
        results = probe_real_if_configured(settings)
    else:
        selected = "dry-run"
        results = dry_run(dry_run_settings())
    write_reports(results, mode=selected, json_output=args.json_output, markdown_output=args.markdown_output)
    print_results(results, mode=selected)


if __name__ == "__main__":
    main()
