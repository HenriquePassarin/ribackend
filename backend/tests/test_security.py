"""Testes de limites de segurança observáveis via HTTP."""

from __future__ import annotations

from helpers import make_png


def test_request_id_is_generated_and_echoed(make_client) -> None:
    client = make_client()

    response = client.get("/health")

    assert response.headers["X-Request-ID"]


def test_provided_request_id_is_preserved(make_client) -> None:
    client = make_client()

    response = client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


def test_error_responses_do_not_expose_internals(client) -> None:
    response = client.get("/api/v1/fruits/999")

    assert response.status_code == 404
    body = response.text
    assert "Traceback" not in body
    assert "site-packages" not in body
    assert "app/main.py" not in body


def test_cors_disabled_when_no_origin_configured(make_client) -> None:
    client = make_client(cors_origins="")

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_restricted_to_configured_origin(make_client) -> None:
    client = make_client(cors_origins="http://localhost:3000")

    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    blocked = client.get("/health", headers={"Origin": "http://ataque.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in blocked.headers


def test_upload_size_limit_applies_to_read(client) -> None:
    # MAX_IMAGE_SIZE_MB=10 por padrão nos testes; o limite é configurável.
    response = client.post(
        "/api/v1/recognitions",
        files={"file": ("fruta.png", make_png() + b"\x00" * (11 * 1024 * 1024), "image/png")},
    )

    assert response.status_code == 413
