"""Interface e adaptadores de visão computacional.

Este pacote não importa OpenCV: o adaptador ``app.vision.opencv_classifier`` é
carregado apenas quando ``VISION_PROVIDER=opencv``, de modo que os modos
``stub``/``disabled`` continuam funcionando sem a dependência instalada.
"""

from app.vision.adapter import (
    DisabledRecognizer,
    ModelConfig,
    build_recognizer,
    model_config_from_settings,
    parse_mean,
    reset_recognizer_cache,
)
from app.vision.base import FruitRecognizer, Prediction
from app.vision.development_stub import SIMULATED_MODEL_VERSION, DevelopmentStubRecognizer

__all__ = [
    "DisabledRecognizer",
    "DevelopmentStubRecognizer",
    "FruitRecognizer",
    "ModelConfig",
    "Prediction",
    "SIMULATED_MODEL_VERSION",
    "build_recognizer",
    "model_config_from_settings",
    "parse_mean",
    "reset_recognizer_cache",
]
