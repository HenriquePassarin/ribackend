"""Utilitários compartilhados pelos testes.

Nenhum teste depende de modelo real, rede ou dataset: o adaptador de visão é
substituído por implementações falsas determinísticas.
"""

from __future__ import annotations

import struct
import threading
import time
import zlib
from collections.abc import Iterable

from app.core.config import Settings
from app.core.images import JPEG, PNG
from app.vision.base import Prediction

PNG_CONTENT_TYPE = "image/png"
JPEG_CONTENT_TYPE = "image/jpeg"


def build_settings(**overrides: object) -> Settings:
    """Configuração isolada para testes (não lê .env)."""
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "sqlite://",
        "auto_create_schema": False,
        "log_level": "WARNING",
        "vision_provider": "stub",
        "min_recognition_confidence": 0.85,
        "always_require_confirmation": True,
        "inference_timeout_seconds": 10.0,
        "max_image_size_mb": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def make_png(width: int = 8, height: int = 8, fill: int = 0) -> bytes:
    """Gera um PNG válido de verdade, sem depender de bibliotecas de imagem."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(b"\x00" + bytes([fill]) * (width * 3) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def gif_bytes() -> bytes:
    """Assinatura de um GIF: imagem válida, mas de formato não suportado."""
    return b"GIF89a" + b"\x01\x00\x01\x00\x80\x00\x00" + bytes(20)


class FakeRecognizer:
    """Adaptador falso, determinístico e controlável pelos testes."""

    def __init__(
        self,
        prediction: Prediction | None = None,
        *,
        error: Exception | None = None,
        delay: float = 0.0,
        formats: Iterable[str] = (PNG, JPEG),
        model_version: str = "fake-model-v1",
    ) -> None:
        self.prediction = prediction or Prediction(
            label="apple_gala", confidence=0.95, model_version=model_version
        )
        self.error = error
        self.delay = delay
        self._formats = frozenset(formats)
        self.calls: list[bytes] = []
        self.thread_ids: list[int] = []

    @property
    def supported_formats(self) -> frozenset[str]:
        return self._formats

    @property
    def is_simulated(self) -> bool:
        # Representa um modelo real: os testes verificam que o serviço não
        # apresenta o stub como reconhecimento real.
        return False

    @property
    def model_version(self) -> str:
        return self.prediction.model_version or "fake-model-v1"

    def predict(self, image_bytes: bytes) -> Prediction:
        self.calls.append(image_bytes)
        self.thread_ids.append(threading.get_ident())
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.prediction
