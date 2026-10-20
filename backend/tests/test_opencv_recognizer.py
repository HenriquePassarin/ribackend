"""Testes do adaptador OpenCV (cv2.dnn).

A maior parte dos testes usa uma rede falsa injetada, então não dependem do
arquivo do modelo nem de rede. Os testes marcados com ``requires_model`` só rodam
quando o modelo real está presente em ``models/`` (`python scripts/fetch_model.py
--model mobilenetv2-7`).

Nenhum teste aqui mede acurácia: verificar que o modelo executa não é avaliar se
ele acerta.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from app.core.errors import InvalidImageError, ModelUnavailableError
from app.vision.adapter import (
    build_recognizer,
    model_config_from_settings,
    parse_mean,
    parse_triplet,
    reset_recognizer_cache,
)
from app.vision.opencv_classifier import OpenCvClassifierRecognizer, load_labels
from helpers import build_settings, make_png

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
REAL_MODEL = MODELS_DIR / "mobilenetv2-7.onnx"
REAL_LABELS = MODELS_DIR / "ilsvrc2012_labels.txt"

requires_model = pytest.mark.skipif(
    not (REAL_MODEL.is_file() and REAL_LABELS.is_file()),
    reason="modelo ONNX ausente; rode: python scripts/fetch_model.py --model mobilenetv2-7",
)


class FakeNet:
    """Rede falsa: registra o blob de entrada e devolve a saída configurada."""

    def __init__(self, outputs: list[float]) -> None:
        self._outputs = np.array(outputs, dtype=np.float32)
        self.blobs: list[np.ndarray] = []

    def setInput(self, blob: np.ndarray) -> None:  # noqa: N802 - API do cv2.dnn
        self.blobs.append(blob)

    def forward(self) -> np.ndarray:
        return self._outputs


def make_recognizer(
    tmp_path: Path,
    outputs: list[float],
    labels: tuple[str, ...] = ("apple_gala", "banana_prata", "orange_pera"),
    **kwargs: object,
) -> tuple[OpenCvClassifierRecognizer, FakeNet]:
    labels_path = tmp_path / "labels.txt"
    labels_path.write_text("\n".join(labels) + "\n", encoding="utf-8")
    net = FakeNet(outputs)
    recognizer = OpenCvClassifierRecognizer(
        model_path=str(tmp_path / "fake.onnx"),
        labels_path=str(labels_path),
        net_factory=lambda _path: net,
        **kwargs,  # type: ignore[arg-type]
    )
    return recognizer, net


def test_recognizer_is_not_simulated_and_accepts_common_formats(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [1.0, 1.0, 1.0])

    assert recognizer.is_simulated is False
    assert {"png", "jpeg", "webp", "bmp", "tiff"} <= recognizer.supported_formats


def test_decoding_failure_raises_invalid_image(tmp_path: Path) -> None:
    recognizer, net = make_recognizer(tmp_path, [1.0, 1.0, 1.0])

    with pytest.raises(InvalidImageError):
        recognizer.predict(b"isto nao e uma imagem")

    assert net.blobs == []


def test_png_is_decoded_and_scaled_into_the_expected_blob(tmp_path: Path) -> None:
    recognizer, net = make_recognizer(tmp_path, [1.0, 1.0, 1.0], input_size=64)

    recognizer.predict(make_png(32, 32, fill=255))

    blob = net.blobs[0]
    assert blob.shape == (1, 3, 64, 64)
    assert 0.0 <= float(blob.min()) and float(blob.max()) <= 1.0
    # Preenchimento 255 com escala 1/255 deve gerar 1.0 no blob.
    assert float(blob.max()) == pytest.approx(1.0)


def test_input_scale_and_mean_are_configurable(tmp_path: Path) -> None:
    recognizer, net = make_recognizer(
        tmp_path, [1.0, 1.0, 1.0], input_scale=1.0, input_mean=(10.0, 10.0, 10.0)
    )

    recognizer.predict(make_png(16, 16, fill=60))

    blob = net.blobs[0]
    assert float(blob.max()) == pytest.approx(50.0)


def test_input_std_normalizes_the_blob_after_scaling(tmp_path: Path) -> None:
    """Normalização ImageNet: (pixel/255 - mean) / std."""
    recognizer, net = make_recognizer(
        tmp_path,
        [1.0, 1.0, 1.0],
        input_scale=1.0 / 255.0,
        input_mean=(0.5, 0.5, 0.5),
        input_std=(0.5, 0.5, 0.5),
    )

    recognizer.predict(make_png(16, 16, fill=255))

    blob = net.blobs[0]
    # (255/255 - 0.5) / 0.5 == 1.0
    assert float(blob.min()) == pytest.approx(1.0)
    assert float(blob.max()) == pytest.approx(1.0)


def test_input_std_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_recognizer(tmp_path, [1.0], input_std=(1.0, 0.0, 1.0))


def test_logits_are_converted_to_probabilities(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [2.0, 1.0, 0.5])

    prediction = recognizer.predict(make_png(16, 16))

    assert prediction.label == "apple_gala"
    assert prediction.confidence == pytest.approx(0.6285, abs=1e-4)
    assert prediction.model_version


def test_probability_output_is_kept_when_auto_detects_distribution(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [0.7, 0.2, 0.1])

    prediction = recognizer.predict(make_png(16, 16))

    assert prediction.confidence == pytest.approx(0.7, abs=1e-6)


def test_softmax_can_be_forced(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [0.7, 0.2, 0.1], softmax_mode="true")

    prediction = recognizer.predict(make_png(16, 16))

    assert prediction.label == "apple_gala"
    # Aplicar softmax sobre valores já normalizados muda a confiança, não o rótulo.
    assert prediction.confidence < 0.7


def test_softmax_can_be_disabled(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [2.0, 1.0, 0.5], softmax_mode="false")

    prediction = recognizer.predict(make_png(16, 16))

    assert prediction.confidence == pytest.approx(2.0)


def test_mismatched_label_count_raises_model_unavailable(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [1.0, 1.0, 1.0], labels=("apple_gala",))

    with pytest.raises(ModelUnavailableError):
        recognizer.predict(make_png(16, 16))


def test_empty_model_output_raises_model_unavailable(tmp_path: Path) -> None:
    recognizer, _ = make_recognizer(tmp_path, [])

    with pytest.raises(ModelUnavailableError):
        recognizer.predict(make_png(16, 16))


def test_labels_file_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "labels.txt"
    path.write_text("# comentário\napple_gala\n\n  banana_prata  \n", encoding="utf-8")

    assert load_labels(path) == ["apple_gala", "banana_prata"]


def test_missing_labels_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ModelUnavailableError) as excinfo:
        load_labels(tmp_path / "inexistente.txt")

    assert "MODEL_LABELS_PATH" in str(excinfo.value)


def test_model_version_is_derived_from_file_hash(tmp_path: Path) -> None:
    model_file = tmp_path / "meu_modelo.onnx"
    model_file.write_bytes(b"conteudo do modelo")

    recognizer, _ = make_recognizer(tmp_path, [1.0, 1.0, 1.0])
    explicit = OpenCvClassifierRecognizer(
        model_path=str(model_file),
        labels_path=str(tmp_path / "labels.txt"),
        net_factory=lambda _path: FakeNet([1.0, 1.0, 1.0]),
    )

    assert recognizer.model_version == "fake"  # arquivo inexistente -> só o nome
    assert explicit.model_version.startswith("meu_modelo-")
    assert len(explicit.model_version.split("-")[-1]) == 12


def test_model_load_failure_is_reported_as_unavailable(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.txt"
    labels_path.write_text("apple_gala\n", encoding="utf-8")

    def broken_factory(_path: str) -> object:
        raise RuntimeError("arquivo corrompido")

    with pytest.raises(ModelUnavailableError):
        OpenCvClassifierRecognizer(
            model_path=str(tmp_path / "broken.onnx"),
            labels_path=str(labels_path),
            net_factory=broken_factory,
        )


def test_invalid_softmax_mode_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_recognizer(tmp_path, [1.0], softmax_mode="talvez")


@pytest.mark.parametrize("mean", ["0,0", "0,0,0,0", "a,b,c", "300,0,0"])
def test_invalid_mean_configuration_is_rejected(mean: str) -> None:
    with pytest.raises(ValidationError):
        build_settings(model_input_mean=mean)


@pytest.mark.parametrize("std", ["0,0", "1,1,1,1", "a,b,c", "0,1,1", "300,1,1"])
def test_invalid_std_configuration_is_rejected(std: str) -> None:
    with pytest.raises(ValidationError):
        build_settings(model_input_std=std)


def test_mean_parsing() -> None:
    assert parse_mean("127.5, 127.5, 127.5") == (127.5, 127.5, 127.5)


def test_opencv_provider_requires_model_path() -> None:
    with pytest.raises(ValidationError) as excinfo:
        build_settings(vision_provider="opencv")

    assert "MODEL_PATH" in str(excinfo.value)


def test_opencv_provider_requires_existing_model_file(tmp_path: Path) -> None:
    labels = tmp_path / "labels.txt"
    labels.write_text("apple_gala\n", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        build_settings(
            vision_provider="opencv",
            model_path=str(tmp_path / "nao_existe.onnx"),
            model_labels_path=str(labels),
        )

    assert "não aponta para um arquivo existente" in str(excinfo.value)


def test_opencv_provider_requires_labels_path(tmp_path: Path) -> None:
    model = tmp_path / "modelo.onnx"
    model.write_bytes(b"x")

    with pytest.raises(ValidationError) as excinfo:
        build_settings(vision_provider="opencv", model_path=str(model))

    assert "MODEL_LABELS_PATH" in str(excinfo.value)


def test_factory_reports_invalid_model_artifact_clearly(tmp_path: Path) -> None:
    reset_recognizer_cache()
    model_file = tmp_path / "modelo.onnx"
    model_file.write_bytes(b"isto nao e um modelo onnx")
    labels = tmp_path / "labels.txt"
    labels.write_text("apple_gala\n", encoding="utf-8")
    settings = build_settings(
        vision_provider="opencv", model_path=str(model_file), model_labels_path=str(labels)
    )

    with pytest.raises(ModelUnavailableError) as excinfo:
        build_recognizer(settings)

    assert "MODEL_PATH" in str(excinfo.value)


def test_model_config_carries_the_opencv_parameters() -> None:
    config = model_config_from_settings(
        build_settings(
            model_input_size=256,
            model_input_scale=1.0,
            model_input_mean="1,2,3",
            model_input_std="4,5,6",
            model_swap_rb=True,
            model_output_softmax="true",
        )
    )

    assert config.input_size == 256
    assert config.input_scale == 1.0
    assert config.input_mean == "1,2,3"
    assert config.input_std == "4,5,6"
    assert config.swap_rb is True
    assert config.softmax_mode == "true"
    assert parse_mean(config.input_mean) == (1.0, 2.0, 3.0)
    assert parse_triplet(config.input_std, "MODEL_INPUT_STD") == (4.0, 5.0, 6.0)


@requires_model
def test_real_model_is_loaded_once_per_configuration() -> None:
    reset_recognizer_cache()
    settings = build_settings(
        vision_provider="opencv",
        model_path=str(REAL_MODEL),
        model_labels_path=str(REAL_LABELS),
    )

    recognizer = build_recognizer(settings)

    assert isinstance(recognizer, OpenCvClassifierRecognizer)
    assert recognizer.is_simulated is False
    assert build_recognizer(settings) is recognizer


@requires_model
def test_real_model_runs_and_returns_a_known_label() -> None:
    """Verifica a integração real (não avalia acurácia)."""
    recognizer = build_recognizer(
        build_settings(
            vision_provider="opencv",
            model_path=str(REAL_MODEL),
            model_labels_path=str(REAL_LABELS),
        )
    )

    prediction = recognizer.predict(make_png(96, 96, fill=40))

    assert prediction.label in set(recognizer.labels)  # type: ignore[attr-defined]
    assert prediction.confidence is not None
    assert 0.0 <= prediction.confidence <= 1.0
    assert "mobilenetv2" in (prediction.model_version or "")


@requires_model
def test_real_model_flows_through_the_api(make_client) -> None:
    settings = build_settings(
        vision_provider="opencv",
        model_path=str(REAL_MODEL),
        model_labels_path=str(REAL_LABELS),
    )
    image = make_png(96, 96, fill=40)
    predicted = build_recognizer(settings).predict(image)
    client = make_client(settings=settings)
    created = client.post(
        "/api/v1/fruits",
        json={
            "name": "Fruta de teste (exemplo)",
            "code": "00001",
            "price_per_kg": "1.00",
            "vision_label": predicted.label,
        },
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/api/v1/recognitions", files={"file": ("fruta.png", image, "image/png")}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prediction"]["label"] == predicted.label
    assert body["status"] in {"recognized", "confirmation_required"}
    assert body["fruit"]["code"] == "00001"
    assert body["prediction"]["model_version"] == predicted.model_version
