"""Testes do cadastro e da consulta de frutas."""

from __future__ import annotations

import pytest

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
    # Dados fictícios de exemplo; nenhum preço/código real é utilizado.
    response = client.post(FRUITS_URL, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_fruit_preserves_leading_zeros_in_code(client) -> None:
    fruit = create_fruit(client)

    assert fruit["code"] == "01234"


def test_create_fruit_keeps_decimal_precision(client) -> None:
    fruit = create_fruit(client, price_per_kg="10.5")

    assert fruit["price_per_kg"] == "10.50"
    assert isinstance(fruit["price_per_kg"], str)


def test_create_fruit_without_price_returns_null(client) -> None:
    fruit = create_fruit(client, price_per_kg=None)

    assert fruit["price_per_kg"] is None


def test_create_fruit_rejects_duplicate_code(client) -> None:
    create_fruit(client)

    response = client.post(FRUITS_URL, json={"name": "Outra", "code": "01234"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_FRUIT"


def test_create_fruit_rejects_invalid_payload(client) -> None:
    response = client.post(FRUITS_URL, json={"name": "", "code": "1"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]


def test_list_fruits_without_filters(client) -> None:
    create_fruit(client, name="Banana Prata", code="00002", vision_label="banana_prata")
    create_fruit(client)

    response = client.get(FRUITS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["name"] for item in body["items"]] == ["Banana Prata", "Maçã Gala"]
    assert body["offset"] == 0
    assert body["limit"] == 20


def test_list_fruits_filters_by_active(client) -> None:
    create_fruit(client)
    create_fruit(client, name="Maçã Fuji", code="05678", vision_label=None, active=False)

    response = client.get(FRUITS_URL, params={"active": False})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Maçã Fuji"


# Busca case-insensitive; a comparação de caracteres acentuados segue a collation do
# banco em uso (limitação registrada no README).
@pytest.mark.parametrize("search", ["maçã", "0123"])
def test_list_fruits_searches_by_name_or_code(client, search: str) -> None:
    create_fruit(client)
    create_fruit(client, name="Banana Prata", code="00002", vision_label=None)

    response = client.get(FRUITS_URL, params={"search": search})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "01234"


def test_list_fruits_pagination(client) -> None:
    for index in range(5):
        create_fruit(client, name=f"Fruta {index}", code=f"0000{index}", vision_label=None)

    first_page = client.get(FRUITS_URL, params={"limit": 2, "offset": 0}).json()
    second_page = client.get(FRUITS_URL, params={"limit": 2, "offset": 2}).json()

    assert first_page["total"] == 5
    assert len(first_page["items"]) == 2
    assert len(second_page["items"]) == 2
    assert {item["id"] for item in first_page["items"]}.isdisjoint(
        {item["id"] for item in second_page["items"]}
    )


def test_list_fruits_clamps_limit_to_configured_maximum(make_client) -> None:
    client = make_client(fruits_default_limit=5, fruits_max_limit=5)
    for index in range(7):
        create_fruit(client, name=f"Fruta {index}", code=f"0000{index}", vision_label=None)

    response = client.get(FRUITS_URL, params={"limit": 999})

    body = response.json()
    assert body["limit"] == 5
    assert len(body["items"]) == 5
    assert body["total"] == 7


def test_list_fruits_validates_pagination_parameters(client) -> None:
    response = client.get(FRUITS_URL, params={"limit": 0})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_fruit_by_id(client) -> None:
    created = create_fruit(client)

    response = client.get(f"{FRUITS_URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_fruit_not_found(client) -> None:
    response = client.get(f"{FRUITS_URL}/999")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "FRUIT_NOT_FOUND"
    assert body["error"]["details"] == {"fruit_id": 999}


def test_get_fruit_with_invalid_id(client) -> None:
    response = client.get(f"{FRUITS_URL}/0")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_route_uses_standard_error_shape(client) -> None:
    response = client.get("/api/v1/inexistente")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_limit_configuration_is_external(make_client) -> None:
    client = make_client(fruits_default_limit=3, fruits_max_limit=3)
    for index in range(4):
        create_fruit(client, name=f"Fruta {index}", code=f"0000{index}", vision_label=None)

    body = client.get(FRUITS_URL).json()

    assert body["limit"] == 3
    assert len(body["items"]) == 3
