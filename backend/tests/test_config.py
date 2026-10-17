"""Testes de configuração: validação e documentação externa."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from helpers import build_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_simulated_provider_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError) as excinfo:
        build_settings(app_env="production", vision_provider="stub")

    assert "stub" in str(excinfo.value)


def test_simulated_provider_requires_explicit_documented_override() -> None:
    settings = build_settings(
        app_env="production", vision_provider="stub", allow_stub_in_production=True
    )

    assert settings.vision_provider == "stub"
    assert settings.allow_stub_in_production is True


def test_simulated_provider_is_allowed_in_development_and_test() -> None:
    assert build_settings(app_env="development").vision_provider == "stub"
    assert build_settings(app_env="test").vision_provider == "stub"


@pytest.mark.parametrize("value", [-0.1, 1.5, 2])
def test_confidence_threshold_must_be_between_zero_and_one(value: float) -> None:
    with pytest.raises(ValidationError):
        build_settings(min_recognition_confidence=value)


def test_default_limit_cannot_exceed_maximum() -> None:
    with pytest.raises(ValidationError):
        build_settings(fruits_default_limit=50, fruits_max_limit=10)


def test_api_prefix_must_start_with_slash() -> None:
    with pytest.raises(ValidationError):
        build_settings(api_v1_prefix="api/v1")


def test_max_image_size_is_converted_to_bytes() -> None:
    settings = build_settings(max_image_size_mb=3)

    assert settings.max_image_size_bytes == 3 * 1024 * 1024


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = build_settings(cors_origins="http://localhost:3000, https://caixa.local")

    assert settings.cors_origin_list == ["http://localhost:3000", "https://caixa.local"]


def test_no_cors_origin_by_default() -> None:
    assert build_settings().cors_origin_list == []


def parse_env_example() -> dict[str, str]:
    lines = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip().upper()] = value.strip()
    return values


def test_env_example_documents_only_known_settings() -> None:
    keys = set(parse_env_example())
    known = {name.upper() for name in Settings.model_fields}

    assert keys, "O .env.example deve documentar as variáveis de configuração."
    assert keys <= known, f"Variáveis desconhecidas no .env.example: {sorted(keys - known)}"


def test_env_example_contains_no_credentials() -> None:
    values = parse_env_example()

    assert values["DATABASE_URL"] == "sqlite:///./fruits.db"
    assert values["MODEL_PATH"] == ""
    assert values["MODEL_VERSION"] == ""
    assert values["ALLOW_STUB_IN_PRODUCTION"] == "false"


def test_empty_optional_settings_become_none() -> None:
    settings = build_settings(model_path="", model_version="")

    assert settings.model_path is None
    assert settings.model_version is None
