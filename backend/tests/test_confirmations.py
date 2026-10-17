"""Testes de confirmação e correção feitas pelo atendente."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ModelUnavailableError
from app.models.recognition import Recognition
from app.vision.base import Prediction
from helpers import FakeRecognizer, make_png

RECOGNITIONS_URL = "/api/v1/recognitions"
FRUITS_URL = "/api/v1/fruits"


def apple_recognizer(confidence: float = 0.95) -> FakeRecognizer:
    """Adaptador falso determinístico que prevê ``apple_gala``."""
    return FakeRecognizer(Prediction(label="apple_gala", confidence=confidence, model_version="m1"))


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


def recognize(client) -> dict:
    response = client.post(RECOGNITIONS_URL, files={"file": ("fruta.png", make_png(), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, recognition_id: str, fruit_id: int):
    return client.post(f"{RECOGNITIONS_URL}/{recognition_id}/confirm", json={"fruit_id": fruit_id})


def test_confirming_suggested_fruit(make_client) -> None:
    client = make_client(recognizer=apple_recognizer(), always_require_confirmation=True)
    fruit = create_fruit(client)
    recognition = recognize(client)
    assert recognition["status"] == "recognized"

    response = confirm(client, recognition["recognition_id"], fruit["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["recognition_id"] == recognition["recognition_id"]
    assert body["fruit"]["code"] == "01234"
    assert body["confirmed_at"].endswith("Z")


def test_correcting_to_another_active_fruit(make_client) -> None:
    client = make_client(recognizer=apple_recognizer())
    suggested = create_fruit(client)
    other = create_fruit(
        client, name="Maçã Fuji", code="05678", price_per_kg="9.50", vision_label="apple_fuji"
    )
    recognition = recognize(client)

    response = confirm(client, recognition["recognition_id"], other["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "corrected"
    assert body["fruit"]["id"] == other["id"]
    assert body["fruit"]["code"] == "05678"
    assert body["fruit"]["id"] != suggested["id"]


def test_confirming_after_no_catalog_match_is_a_correction(make_client) -> None:
    recognizer = FakeRecognizer(Prediction(label="kiwi_verde", confidence=0.99, model_version="m1"))
    client = make_client(recognizer=recognizer)
    fruit = create_fruit(client)
    recognition = recognize(client)
    assert recognition["status"] == "no_catalog_match"

    body = confirm(client, recognition["recognition_id"], fruit["id"]).json()

    assert body["status"] == "corrected"


def test_confirming_after_unrecognized_image_is_a_correction(make_client) -> None:
    recognizer = FakeRecognizer(Prediction(label=None, confidence=None, model_version="m1"))
    client = make_client(recognizer=recognizer)
    fruit = create_fruit(client)
    recognition = recognize(client)
    assert recognition["status"] == "unrecognized"

    body = confirm(client, recognition["recognition_id"], fruit["id"]).json()

    assert body["status"] == "corrected"


def test_confirm_unknown_recognition(client) -> None:
    response = confirm(client, "00000000-0000-0000-0000-000000000000", 1)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECOGNITION_NOT_FOUND"


def test_confirm_unknown_fruit(make_client) -> None:
    client = make_client(recognizer=apple_recognizer())
    create_fruit(client)
    recognition = recognize(client)

    response = confirm(client, recognition["recognition_id"], 999)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FRUIT_NOT_FOUND"


def test_confirm_inactive_fruit(make_client) -> None:
    client = make_client(recognizer=apple_recognizer())
    create_fruit(client)
    inactive = create_fruit(
        client, name="Maçã Fuji", code="05678", vision_label=None, active=False
    )
    recognition = recognize(client)

    response = confirm(client, recognition["recognition_id"], inactive["id"])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FRUIT_INACTIVE"


def test_cannot_confirm_twice(make_client) -> None:
    client = make_client(recognizer=apple_recognizer())
    fruit = create_fruit(client)
    recognition = recognize(client)
    assert confirm(client, recognition["recognition_id"], fruit["id"]).status_code == 200

    response = confirm(client, recognition["recognition_id"], fruit["id"])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_STATE"


def test_cannot_confirm_attempt_that_failed_technically(make_client, session: Session) -> None:
    client = make_client(recognizer=FakeRecognizer(error=ModelUnavailableError()))
    fruit = create_fruit(client)

    assert post_failure(client) == 503
    failed = session.query(Recognition).one()
    assert failed.status == "failed"

    response = confirm(client, failed.id, fruit["id"])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_STATE"


def post_failure(client) -> int:
    return client.post(
        RECOGNITIONS_URL, files={"file": ("fruta.png", make_png(), "image/png")}
    ).status_code


def test_confirm_rejects_invalid_payload(client) -> None:
    response = client.post(f"{RECOGNITIONS_URL}/qualquer/confirm", json={"fruit_id": 0})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_confirmation_does_not_change_catalog(make_client, session: Session) -> None:
    client = make_client(recognizer=apple_recognizer())
    fruit = create_fruit(client, price_per_kg="8.99")
    other = create_fruit(
        client, name="Maçã Fuji", code="05678", price_per_kg="9.50", vision_label="apple_fuji"
    )
    recognition = recognize(client)

    before = {
        "suggested": client.get(f"{FRUITS_URL}/{fruit['id']}").json(),
        "chosen": client.get(f"{FRUITS_URL}/{other['id']}").json(),
    }
    confirm(client, recognition["recognition_id"], other["id"])
    after = {
        "suggested": client.get(f"{FRUITS_URL}/{fruit['id']}").json(),
        "chosen": client.get(f"{FRUITS_URL}/{other['id']}").json(),
    }

    assert before == after
    assert after["chosen"]["price_per_kg"] == "9.50"
    assert after["chosen"]["code"] == "05678"

    stored = session.get(Recognition, recognition["recognition_id"])
    assert stored.confirmed_fruit_id == other["id"]
    assert stored.matched_fruit_id == fruit["id"]
    # A confirmação não representa finalização de venda nem altera preços.
    assert stored.confirmed_at is not None
