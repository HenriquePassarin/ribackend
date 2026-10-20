"""Adaptador de visão computacional real usando OpenCV (``cv2.dnn``).

Executa um classificador de imagens em formato ONNX com três etapas:

1. Decodificação real da imagem com ``cv2.imdecode`` (um arquivo que não é imagem
   válida falha aqui, e não apenas por assinatura de bytes).
2. Pré-processamento com ``cv2.dnn.blobFromImage`` (redimensionamento, escala e
   troca de canais) seguido de normalização ``(blob - mean) / std`` por canal.
3. Inferência com ``cv2.dnn`` e conversão da saída em probabilidades.

O adaptador é agnóstico ao modelo: qualquer classificador ONNX de uma única
entrada com vetor de saída por classe funciona, desde que acompanhado de um
arquivo de rótulos com uma classe por linha (na mesma ordem dos índices de
saída). O modelo é carregado uma única vez e protegido por ``threading.Lock``,
porque a inferência roda em threads de trabalho e ``cv2.dnn.Net`` não é seguro
para uso concorrente na mesma instância.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from app.core.errors import InvalidImageError, ModelUnavailableError
from app.core.images import BMP, JPEG, PNG, TIFF, WEBP
from app.vision.base import Prediction

logger = logging.getLogger(__name__)

# Formatos que o OpenCV consegue decodificar e que este projeto aceita receber.
SUPPORTED_FORMATS: frozenset[str] = frozenset({PNG, JPEG, WEBP, BMP, TIFF})

SOFTMAX_MODES = ("auto", "true", "false")


def load_labels(labels_path: str | Path) -> list[str]:
    """Lê um rótulo por linha, ignorando linhas vazias e comentários com ``#``."""
    path = Path(labels_path)
    if not path.is_file():
        raise ModelUnavailableError(
            f"Arquivo de rótulos não encontrado em MODEL_LABELS_PATH ({path.name})."
        )
    labels = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not labels:
        raise ModelUnavailableError("O arquivo de rótulos do modelo está vazio.")
    return labels


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exponentials = np.exp(shifted)
    total = exponentials.sum()
    if total <= 0:
        raise ModelUnavailableError("Saída inválida do modelo (soma das probabilidades é zero).")
    return exponentials / total


class OpenCvClassifierRecognizer:
    """Classificador ONNX executado com OpenCV DNN."""

    def __init__(
        self,
        *,
        model_path: str,
        labels_path: str,
        input_size: int = 224,
        input_scale: float = 1.0 / 255.0,
        input_mean: tuple[float, float, float] = (0.0, 0.0, 0.0),
        input_std: tuple[float, float, float] = (1.0, 1.0, 1.0),
        swap_rb: bool = False,
        softmax_mode: str = "auto",
        model_version: str | None = None,
        net_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if softmax_mode not in SOFTMAX_MODES:
            raise ValueError(f"modo de softmax inválido: {softmax_mode!r}; use {SOFTMAX_MODES}")
        if any(float(value) <= 0.0 for value in input_std):
            raise ValueError("input_std deve conter três valores maiores que zero")

        self._labels = load_labels(labels_path)
        factory = net_factory or cv2.dnn.readNetFromONNX
        try:
            self._net = factory(model_path)
        except ModelUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - falha ao carregar o artefato do modelo
            raise ModelUnavailableError(
                "Não foi possível carregar o modelo de visão configurado em MODEL_PATH."
            ) from exc

        self._model_path = Path(model_path)
        self._model_version = model_version or self._derive_model_version()
        self._input_size = input_size
        self._input_scale = input_scale
        self._input_mean = tuple(float(value) for value in input_mean)
        self._input_std = tuple(float(value) for value in input_std)
        self._swap_rb = swap_rb
        self._softmax_mode = softmax_mode
        self._lock = threading.Lock()

        logger.info(
            "Modelo ONNX carregado via cv2.dnn: arquivo=%s rótulos=%s versão=%s entrada=%sx%s escala=%s",
            self._model_path.name,
            len(self._labels),
            self._model_version,
            input_size,
            input_size,
            input_scale,
        )

    @property
    def supported_formats(self) -> frozenset[str]:
        return SUPPORTED_FORMATS

    @property
    def is_simulated(self) -> bool:
        return False

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(self._labels)

    def _derive_model_version(self) -> str:
        """Identifica a versão pelo nome do arquivo + hash, para auditoria."""
        digest = hashlib.sha256()
        try:
            with self._model_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return self._model_path.stem
        return f"{self._model_path.stem}-{digest.hexdigest()[:12]}"

    def _decode(self, image_bytes: bytes) -> np.ndarray:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise InvalidImageError()
        return image

    def _preprocess(self, image: np.ndarray) -> Any:
        """Redimensiona, escala, troca canais e normaliza o blob.

        A média e o desvio padrão são aplicados **depois** da escala, na ordem de
        canais resultante de ``swap_rb`` (por exemplo, RGB quando ``swap_rb=True``).
        Isso permite expressar a normalização do ImageNet diretamente:
        escala ``1/255``, média ``0.485,0.456,0.406`` e desvio
        ``0.229,0.224,0.225``. Com média zero e desvio um, o resultado é idêntico
        ao de apenas escalar a imagem.
        """
        blob = cv2.dnn.blobFromImage(
            image,
            scalefactor=self._input_scale,
            size=(self._input_size, self._input_size),
            mean=(0.0, 0.0, 0.0),
            swapRB=self._swap_rb,
            crop=False,
        )
        if self._input_mean != (0.0, 0.0, 0.0) or self._input_std != (1.0, 1.0, 1.0):
            mean = np.asarray(self._input_mean, dtype=np.float32).reshape(1, 3, 1, 1)
            std = np.asarray(self._input_std, dtype=np.float32).reshape(1, 3, 1, 1)
            blob = (blob - mean) / std
        return blob

    def _probabilities(self, outputs: np.ndarray) -> np.ndarray:
        if self._softmax_mode == "true":
            return _softmax(outputs)
        if self._softmax_mode == "false":
            return outputs
        # "auto": modelos da ONNX Model Zoo costumam devolver logits (soma != 1).
        if float(outputs.min()) >= 0.0 and 0.9 <= float(outputs.sum()) <= 1.1:
            return outputs
        return _softmax(outputs)

    def predict(self, image_bytes: bytes) -> Prediction:
        image = self._decode(image_bytes)
        blob = self._preprocess(image)
        try:
            with self._lock:
                self._net.setInput(blob)
                outputs = np.array(self._net.forward(), dtype=np.float64).flatten()
        except cv2.error as exc:
            raise ModelUnavailableError(
                "Falha ao executar a inferência com o modelo configurado."
            ) from exc

        if outputs.size == 0:
            raise ModelUnavailableError("O modelo não devolveu nenhuma classe.")

        if outputs.size > len(self._labels):
            raise ModelUnavailableError(
                "A quantidade de rótulos em MODEL_LABELS_PATH não corresponde à saída do modelo."
            )

        probabilities = self._probabilities(outputs)
        index = int(np.argmax(probabilities))
        return Prediction(
            label=self._labels[index],
            confidence=round(float(probabilities[index]), 4),
            model_version=self._model_version,
        )
