"""Testes do endpoint de saúde."""

from __future__ import annotations


def test_health_returns_ok(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_expose_internal_details(client) -> None:
    response = client.get("/health")

    assert set(response.json().keys()) == {"status"}


def test_swagger_ui_is_available(client) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "swagger" in response.text.lower()


def test_redoc_is_available(client) -> None:
    response = client.get("/redoc")

    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_openapi_is_available(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/fruits" in paths
    assert "/api/v1/recognitions" in paths
    assert "/api/v1/recognitions/{recognition_id}/confirm" in paths


def test_openapi_documents_endpoints_and_errors(client) -> None:
    document = client.get("/openapi.json").json()

    for path in ("/health", "/api/v1/fruits", "/api/v1/recognitions"):
        assert document["paths"][path], f"{path} sem operações documentadas"

    # Cada tag tem descrição, e os códigos de erro específicos aparecem no documento.
    assert {tag["name"] for tag in document["tags"]} == {"health", "fruits", "recognitions"}
    assert all(tag.get("description") for tag in document["tags"])
    for code in ("INVALID_IMAGE", "IMAGE_TOO_LARGE", "MODEL_UNAVAILABLE", "FRUIT_INACTIVE"):
        assert code in document["info"]["description"]

    recognition = document["paths"]["/api/v1/recognitions"]["post"]
    assert "503" in recognition["responses"]
    assert "504" in recognition["responses"]
    assert recognition["requestBody"]["content"]["multipart/form-data"]


def test_openapi_documents_only_the_error_codes_each_route_emits(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    recognize = paths["/api/v1/recognitions"]["post"]
    assert {"413", "415", "503", "504"} <= set(recognize["responses"])

    confirm = paths["/api/v1/recognitions/{recognition_id}/confirm"]["post"]
    assert set(confirm["responses"]) == {"200", "400", "404", "422", "500"}

    create = paths["/api/v1/fruits"]["post"]
    assert set(create["responses"]) == {"201", "409", "422"}

    get_fruit = paths["/api/v1/fruits/{fruit_id}"]["get"]
    assert set(get_fruit["responses"]) == {"200", "404", "422"}


def test_openapi_includes_response_examples(client) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]

    assert schemas["HealthResponse"]["example"] == {"status": "ok"}
    assert schemas["RecognitionConfirmRequest"]["example"] == {"fruit_id": 12}
    assert schemas["RecognitionResponse"]["example"]["status"] == "confirmation_required"
    assert schemas["FruitRead"]["example"]["code"] == "01234"
