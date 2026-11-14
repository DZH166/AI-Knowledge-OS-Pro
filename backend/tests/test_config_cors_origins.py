from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings_without_env_file(monkeypatch: pytest.MonkeyPatch, raw: str) -> Settings:
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", raw)
    return Settings(_env_file=None)


def test_comma_separated_cors_origins_match_documented_env_example(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_without_env_file(
        monkeypatch,
        "http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:3010",
    )

    assert settings.backend_cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3010",
    ]


def test_json_array_cors_origins_stay_supported_for_existing_scripts(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps(["http://127.0.0.1:43101"])

    assert _settings_without_env_file(monkeypatch, raw).backend_cors_origins == ["http://127.0.0.1:43101"]


def test_blank_cors_entries_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_without_env_file(monkeypatch, " http://localhost:3000 , ,http://127.0.0.1:3000 ")

    assert settings.backend_cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_invalid_json_cors_origins_fail_with_explicit_message(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="comma-separated list or a JSON array"):
        _settings_without_env_file(monkeypatch, "[not-json")


def test_settings_load_without_cors_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACKEND_CORS_ORIGINS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.backend_cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
