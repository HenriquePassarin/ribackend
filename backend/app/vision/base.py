"""Interface isolada do componente de visão computacional.

As regras de negócio dependem apenas deste contrato, nunca de uma biblioteca ou
modelo específico.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Prediction:
    """Resultado bruto do modelo.

    ``label`` é a classe prevista (ex.: ``apple_gala``). A confiança, quando
    disponível, é um valor entre 0 e 1 informado pelo modelo e NÃO representa
    garantia de acerto.
    """

    label: str | None
    confidence: float | None
    model_version: str | None


@runtime_checkable
class FruitRecognizer(Protocol):
    """Contrato do adaptador de visão computacional.

    Extensões em relação ao contrato mínimo da especificação:

    * ``supported_formats``: formatos de arquivo que o adaptador aceita, usados
      para validar o upload antes da inferência.
    * ``is_simulated``: indica se a implementação é um simulador de
      desenvolvimento. Deve ser ``True`` para qualquer stub, nunca para um
      modelo real.
    """

    @property
    def supported_formats(self) -> frozenset[str]:
        ...

    @property
    def is_simulated(self) -> bool:
        ...

    def predict(self, image_bytes: bytes) -> Prediction:
        """Executa a inferência. Pode ser bloqueante: ver estratégia de execução
        documentada em ``app/services/recognition_service.py``."""
        ...
