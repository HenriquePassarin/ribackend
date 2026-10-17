"""Testes do endpoint de reconhecimento.

Todos os testes usam adaptadores falsos determinísticos: nenhum modelo real,
rede ou dataset é necessário.
"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ModelUnavailableError
from app.models.recognition import Recognition, RecognitionStatus
from app.vision.base import Prediction
from helpers import FakeRecognizer, PNG_CONTENT_TYPE, gif_bytes, make_png

RECOGNITIONS_URL = "/api/v1/recognitions"
FRUITS_URL = "/api/v1/fruits"


def create_fruit(client, **overrides) -> dict:
    payload = {
        "name": "Maçã Gala",
        "code": "01234",
        "price_per_kg": "8.99",
        "unit": "kg",
        "active": True,
        "vision_label": "apple_gala",
    }
    payload.update(overrides)
    response = client.post(FRUITS_URL, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def post_image(client, content: bytes, *, filename: str = "fruta.png", content_type: str = PNG_CONTENT_TYPE):
    return client.post(RECOGNITIONS_URL, files={"file": (filename, content, content_type)})


def test_recognized_class_mapped_to_catalog_fruit(make_client) -> None:
    recognizer = FakeRecognizer(
        Prediction(label="apple_gala", confidence=0.95, model_version="fake-model-v1")
    )
    client = make_client(recognizer=recognizer, always_require_confirmation=False)
    fruit = create_fruit(client)

    response = post_image(client, make_png())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "recognized"
    assert body["confirmation_required"] is False
    assert body["prediction"] == {
        "label": "apple_gala",
        "confidence": 0.95,
        "model_version": "fake-model-v1",
    }
    # Código e preço vêm do cadastro, não da previsão visual.
    assert body["fruit"] == {
        "id": fruit["id"],
        "name": fruit["name"],
        "code": "01234",
        "price_per_kg": "8.99",
        "unit": "kg",
    }
    assert len(recognizer.calls) == 1


def test_recognized_still_requires_confirmation_when_policy_demands(make_client) -> None:
    recognizer = FakeRecognizer(
        Prediction(label="apple_gala", confidence=0.95, model_version="m1")
    )
    client = make_client(recognizer=recognizer, always_require_confirmation=True)
    create_fruit(client)

    body = post_image(client, make_png()).json()

    # Confiança alta não é tratada como prova de acerto.
    assert body["status"] == "recognized"
    assert body["confirmation_required"] is True


def test_confidence_below_threshold_requires_confirmation(make_client) -> None:
    recognizer = FakeRecognizer(Prediction(label="apple_gala", confidence=0.42, model_version="m1"))
    client = make_client(recognizer=recognizer, min_recognition_confidence=0.85)
    create_fruit(client)

    body = post_image(client, make_png()).json()

    assert body["status"] == "confirmation_required"
    assert body["confirmation_required"] is True
    assert body["fruit"]["code"] == "01234"


def test_prediction_without_catalog_match_does_not_invent_data(make_client) -> None:
    recognizer = FakeRecognizer(Prediction(label="kiwi_verde", confidence=0.99, model_version="m1"))
    client = make_client(recognizer=recognizer)
    create_fruit(client)

    body = post_image(client, make_png()).json()

    assert body["status"] == "no_catalog_match"
    assert body["fruit"] is None
    assert body["confirmation_required"] is True


def test_prediction_matching_inactive_fruit_is_not_offered(make_client) -> None:
    client = make_client()
    create_fruit(client, active=False)

    body = post_image(client, make_png()).json()

    assert body["status"] == "no_catalog_match"
    assert body["fruit"] is None


def test_unrecognized_image(make_client) -> None:
    recognizer = FakeRecognizer(Prediction(label=None, confidence=None, model_version="m1"))
    client = make_client(recognizer=recognizer)
    create_fruit(client)

    body = post_image(client, make_png()).json()

    assert body["status"] == "unrecognized"
    assert body["prediction"]["label"] is None
    assert body["fruit"] is None


def test_empty_file_is_rejected(client) -> None:
    response = post_image(client, b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_IMAGE"


def test_content_that_is_not_an_image_is_rejected_even_with_jpg_name(client) -> None:
    response = post_image(client, b"isto nao e uma imagem", filename="fruta.jpg")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_unsupported_declared_media_type_is_rejected(client) -> None:
    response = post_image(client, gif_bytes(), filename="fruta.gif", content_type="image/gif")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_real_image_of_unsupported_format_is_rejected_based_on_content(client) -> None:
    # O tipo declarado é permitido, mas o conteúdo real é um GIF: rejeitamos pelo
    # conteúdo, não pelo cabeçalho enviado pelo cliente.
    response = post_image(client, gif_bytes(), filename="fruta.png", content_type=PNG_CONTENT_TYPE)

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert body["error"]["details"]["detected_format"] == "gif"


def test_format_supported_by_catalog_but_not_by_adapter_is_rejected(make_client) -> None:
    recognizer = FakeRecognizer(
        Prediction(label="apple_gala", confidence=0.95, model_version="m1"), formats=("jpeg",)
    )
    client = make_client(recognizer=recognizer)

    response = post_image(client, make_png(), content_type=PNG_CONTENT_TYPE)

    assert response.status_code == 415
    assert response.json()["error"]["details"]["supported_formats"] == ["jpeg"]
    assert recognizer.calls == []


def test_image_above_size_limit_is_rejected(make_client) -> None:
    client = make_client(max_image_size_mb=1)
    too_large = make_png() + b"\x00" * (1024 * 1024)

    response = post_image(client, too_large)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_missing_file_field_is_a_validation_error(client) -> None:
    response = client.post(RECOGNITIONS_URL)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_model_unavailable_returns_503(make_client, session: Session) -> None:
    recognizer = FakeRecognizer(error=ModelUnavailableError("caminho interno C:/modelo/model.pt"))
    client = make_client(recognizer=recognizer)

    response = post_image(client, make_png())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    # A causa técnica não é exposta ao cliente.
    assert "model.pt" not in response.text

    # A falha técnica é auditada sem expor detalhes internos na resposta.
    records = session.query(Recognition).all()
    assert len(records) == 1
    assert records[0].status == RecognitionStatus.FAILED.value
    assert records[0].predicted_label is None


def test_inference_timeout_returns_504(make_client, session: Session) -> None:
    recognizer = FakeRecognizer(delay=0.5)
    client = make_client(recognizer=recognizer, inference_timeout_seconds=0.05)

    response = post_image(client, make_png())

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "INFERENCE_TIMEOUT"
    assert session.query(Recognition).count() == 1


def test_unexpected_failure_does_not_leak_stack_trace(make_client) -> None:
    recognizer = FakeRecognizer(error=RuntimeError("detalhe interno sensível"))
    client = make_client(recognizer=recognizer)

    response = post_image(client, make_png())

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "Erro interno.",
        "details": None,
    }
    assert "Traceback" not in response.text
    assert "sensível" not in response.text


def test_vision_disabled_configuration_returns_503(make_client) -> None:
    client = make_client(vision_provider="disabled")

    response = post_image(client, make_png())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"


def test_inference_runs_outside_the_event_loop_thread(make_client) -> None:
    recognizer = FakeRecognizer()
    client = make_client(recognizer=recognizer)

    post_image(client, make_png())

    assert recognizer.thread_ids
    assert recognizer.thread_ids[0] != threading.main_thread().ident


class MinimalRecognizer:
    """Adaptador que implementa apenas o contrato mínimo da especificação (``predict``)."""

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, image_bytes: bytes) -> Prediction:
        self.calls += 1
        return Prediction(label="apple_gala", confidence=0.95, model_version="minimal-v1")


def test_recognizer_with_minimal_contract_is_supported(make_client) -> None:
    recognizer = MinimalRecognizer()
    client = make_client(recognizer=recognizer, always_require_confirmation=False)
    create_fruit(client)

    response = post_image(client, make_png())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "recognized"
    assert body["prediction"]["model_version"] == "minimal-v1"
    assert recognizer.calls == 1


def test_image_bytes_are_not_persisted(client, session: Session) -> None:
    post_image(client, make_png())

    columns = {column.name for column in Recognition.__table__.columns}
    assert not any("image" in name or "blob" in name for name in columns)
    record = session.query(Recognition).one()
    assert all(not isinstance(value, (bytes, bytearray)) for value in vars(record).values())


@pytest.mark.parametrize(
    ("status_expected", "confidence"),
    [("recognized", 0.9), ("confirmation_required", 0.2)],
)
def test_status_transitions_depend_on_configured_threshold(
    make_client, status_expected: str, confidence: float
) -> None:
    recognizer = FakeRecognizer(
        Prediction(label="apple_gala", confidence=confidence, model_version="m1")
    )
    client = make_client(
        recognizer=recognizer, min_recognition_confidence=0.85, always_require_confirmation=False
    )
    create_fruit(client)

    body = post_image(client, make_png()).json()

    assert body["status"] == status_expected
