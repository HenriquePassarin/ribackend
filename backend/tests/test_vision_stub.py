"""Testes do adaptador simulado e da fábrica de adaptadores."""

from __future__ import annotations

import logging

import pytest

from app.core.errors import ModelUnavailableError
from app.vision import (
    DisabledRecognizer,
    DevelopmentStubRecognizer,
    build_recognizer,
    reset_recognizer_cache,
)
from app.vision.development_stub import DEFAULT_STUB_LABELS, SIMULATED_MODEL_VERSION
from helpers import build_settings, make_png


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_recognizer_cache()
    yield
    reset_recognizer_cache()


def test_stub_is_deterministic() -> None:
    recognizer = DevelopmentStubRecognizer()
    payload = make_png(4, 4)

    assert recognizer.predict(payload) == recognizer.predict(payload)


def test_stub_is_explicitly_marked_as_simulated() -> None:
    recognizer = DevelopmentStubRecognizer()

    assert recognizer.is_simulated is True
    assert recognizer.model_version == SIMULATED_MODEL_VERSION
    assert "stub" in recognizer.model_version


def test_stub_only_returns_known_labels() -> None:
    recognizer = DevelopmentStubRecognizer()
    labels = set()
    for width in range(1, 40):
        prediction = recognizer.predict(make_png(width, 1, fill=width % 256))
        if prediction.label is not None:
            assert prediction.label in DEFAULT_STUB_LABELS
            assert 0.0 <= (prediction.confidence or 0.0) <= 1.0
        labels.add(prediction.label)

    # O stub precisa exercitar tanto o caminho reconhecido quanto o não reconhecido.
    assert None in labels
    assert len(labels) > 1


def test_stub_formats() -> None:
    assert DevelopmentStubRecognizer().supported_formats == frozenset({"png", "jpeg"})


def test_factory_returns_stub_only_when_configured() -> None:
    recognizer = build_recognizer(build_settings(vision_provider="stub"))

    assert isinstance(recognizer, DevelopmentStubRecognizer)
    assert recognizer.is_simulated is True


def test_factory_caches_instances() -> None:
    settings = build_settings(vision_provider="stub")

    assert build_recognizer(settings) is build_recognizer(settings)


def test_factory_disabled_provider_raises_model_unavailable() -> None:
    recognizer = build_recognizer(build_settings(vision_provider="disabled"))

    assert isinstance(recognizer, DisabledRecognizer)
    with pytest.raises(ModelUnavailableError):
        recognizer.predict(make_png())


def test_simulated_mode_warns_at_startup(make_client) -> None:
    messages: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = _Collect()
    app_logger = logging.getLogger("app.main")
    app_logger.addHandler(handler)
    try:
        make_client()
    finally:
        app_logger.removeHandler(handler)

    assert any("SIMULADO" in message for message in messages)
