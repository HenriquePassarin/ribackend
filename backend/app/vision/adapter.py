"""Fábrica do adaptador de visão computacional.

Seleciona a implementação a partir da configuração (``VISION_PROVIDER``), o que
permite trocar entre o adaptador simulado, o serviço desabilitado e um modelo
ONNX real executado pelo OpenCV, sem alterar rotas, serviços ou repositórios.

Provedores disponíveis:

* ``opencv``   — modelo ONNX real executado com ``cv2.dnn``.
* ``stub``     — adaptador SIMULADO de desenvolvimento (não reconhece frutas).
* ``disabled`` — serviço indisponível; a API responde 503 sem inventar resultado.

Como integrar outro modelo/framework (também no README):

1. Criar um módulo em ``app/vision/`` implementando ``FruitRecognizer``
   (``predict`` é o único método obrigatório).
2. Registrar a fábrica em ``_PROVIDER_FACTORIES`` e adicionar o provedor ao tipo
   ``VisionProvider`` em ``app/core/config.py``.
3. Rodar experimentos em um dataset representativo antes de afirmar desempenho.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.core.errors import ModelUnavailableError
from app.core.config import Settings
from app.core.images import SUPPORTED_FORMATS
from app.vision.base import FruitRecognizer, Prediction
from app.vision.development_stub import DevelopmentStubRecognizer

logger = logging.getLogger(__name__)


class DisabledRecognizer:
    """Implementação usada quando nenhum provedor de visão está disponível."""

    @property
    def supported_formats(self) -> frozenset[str]:
        return SUPPORTED_FORMATS

    @property
    def is_simulated(self) -> bool:
        return False

    def predict(self, image_bytes: bytes) -> Prediction:  # noqa: ARG002 - contrato da interface
        raise ModelUnavailableError(
            "Nenhum modelo de visão computacional está configurado (VISION_PROVIDER=disabled)."
        )


@dataclass(frozen=True)
class ModelConfig:
    """Parâmetros do modelo, agrupados para permitir cache por configuração."""

    provider: str
    path: str = ""
    labels_path: str = ""
    version: str | None = None
    input_size: int = 224
    input_scale: float = 1.0 / 255.0
    input_mean: str = "0,0,0"
    input_std: str = "1,1,1"
    swap_rb: bool = False
    softmax_mode: str = "auto"


def build_opencv_recognizer(config: ModelConfig) -> FruitRecognizer:
    """Instancia o classificador ONNX executado com OpenCV."""
    try:
        from app.vision.opencv_classifier import OpenCvClassifierRecognizer
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ModelUnavailableError(
            "opencv-python não está instalado; instale as dependências de requirements.txt "
            "para usar VISION_PROVIDER=opencv."
        ) from exc

    return OpenCvClassifierRecognizer(
        model_path=config.path,
        labels_path=config.labels_path,
        input_size=config.input_size,
        input_scale=config.input_scale,
        input_mean=parse_mean(config.input_mean),
        input_std=parse_triplet(config.input_std, "MODEL_INPUT_STD"),
        swap_rb=config.swap_rb,
        softmax_mode=config.softmax_mode,
        model_version=config.version,
    )


def parse_triplet(value: str, variable: str = "MODEL_INPUT_MEAN") -> tuple[float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ModelUnavailableError(
            f"{variable} deve conter três valores separados por vírgula, por exemplo: 0,0,0"
        )
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def parse_mean(value: str) -> tuple[float, float, float]:
    return parse_triplet(value, "MODEL_INPUT_MEAN")


_PROVIDER_FACTORIES: dict[str, Callable[[ModelConfig], FruitRecognizer]] = {
    "opencv": build_opencv_recognizer,
}


def model_config_from_settings(settings: Settings) -> ModelConfig:
    return ModelConfig(
        provider=settings.vision_provider,
        path=settings.model_path or "",
        labels_path=settings.model_labels_path or "",
        version=settings.model_version,
        input_size=settings.model_input_size,
        input_scale=settings.model_input_scale,
        input_mean=settings.model_input_mean,
        input_std=settings.model_input_std,
        swap_rb=settings.model_swap_rb,
        softmax_mode=settings.model_output_softmax,
    )


@lru_cache
def _build_cached(config: ModelConfig) -> FruitRecognizer:
    if config.provider == "disabled":
        logger.warning("Serviço de visão computacional desabilitado por configuração.")
        return DisabledRecognizer()

    if config.provider == "stub":
        logger.warning(
            "VISION_PROVIDER=stub: usando adaptador SIMULADO. "
            "Os resultados NÃO são reconhecimento real e não devem ser usados em produção."
        )
        return DevelopmentStubRecognizer(model_version=config.version or None)

    factory = _PROVIDER_FACTORIES.get(config.provider)
    if factory is None:
        raise ModelUnavailableError("O provedor de visão computacional configurado não está disponível.")
    return factory(config)


def build_recognizer(settings: Settings) -> FruitRecognizer:
    """Cria (ou reaproveita) o adaptador conforme a configuração atual."""
    return _build_cached(model_config_from_settings(settings))


def reset_recognizer_cache() -> None:
    """Limpa o cache da fábrica (útil em testes)."""
    _build_cached.cache_clear()
