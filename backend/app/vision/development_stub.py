"""Adaptador SIMULADO para desenvolvimento e testes.

Este adaptador NÃO realiza reconhecimento visual. Ele apenas deriva um rótulo
determinístico a partir do hash dos bytes da imagem, o que permite exercitar o
fluxo completo do sistema (mapeamento para o catálogo, política de confiança,
confirmação do atendente) sem modelo treinado.

Regras:
    * Só é ativado por configuração explícita (``VISION_PROVIDER=stub``).
    * Nunca é selecionado silenciosamente em produção (ver ``app/core/config.py``).
    * A versão do modelo é marcada como ``development-stub`` para que nenhum
      consumidor confunda o resultado com reconhecimento real.
"""

from __future__ import annotations

import hashlib

from app.core.images import SUPPORTED_FORMATS
from app.vision.base import Prediction

SIMULATED_MODEL_VERSION = "development-stub-v0"

# Rótulos fictícios usados apenas para exercitar o fluxo. Não representam
# classes de um modelo treinado.
DEFAULT_STUB_LABELS: tuple[str, ...] = (
    "apple_gala",
    "apple_fuji",
    "orange_pera",
    "banana_prata",
    "grape_niagara",
)

# Frequência com que o stub simula uma imagem não reconhecida (1 em cada N).
UNRECOGNIZED_EVERY = 5


class DevelopmentStubRecognizer:
    """Reconhecedor simulado e determinístico."""

    def __init__(
        self,
        labels: tuple[str, ...] = DEFAULT_STUB_LABELS,
        model_version: str | None = None,
    ) -> None:
        if not labels:
            raise ValueError("É necessário informar ao menos um rótulo simulado.")
        self._labels = labels
        self._model_version = model_version or SIMULATED_MODEL_VERSION

    @property
    def supported_formats(self) -> frozenset[str]:
        return SUPPORTED_FORMATS

    @property
    def is_simulated(self) -> bool:
        return True

    @property
    def model_version(self) -> str:
        return self._model_version

    def predict(self, image_bytes: bytes) -> Prediction:
        digest = hashlib.sha256(image_bytes).digest()
        bucket = int.from_bytes(digest[:8], "big")

        if bucket % UNRECOGNIZED_EVERY == 0:
            return Prediction(label=None, confidence=None, model_version=self._model_version)

        label = self._labels[bucket % len(self._labels)]
        # Confiança entre 0.500 e 0.999, determinística para os mesmos bytes.
        confidence = round(0.5 + (int.from_bytes(digest[8:12], "big") % 500) / 1000, 3)
        return Prediction(label=label, confidence=confidence, model_version=self._model_version)
