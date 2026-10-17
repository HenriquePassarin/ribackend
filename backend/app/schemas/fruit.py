"""Contratos HTTP do cadastro de frutas."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def serialize_money(value: Decimal) -> str:
    """Serializa valores monetários como string decimal com 2 casas.

    Usar string evita que clientes convertam o valor para ponto flutuante
    binário e percam precisão.
    """
    return f"{Decimal(value).quantize(Decimal('0.01')):.2f}"


Money = Annotated[Decimal, PlainSerializer(serialize_money, return_type=str)]


class FruitCreate(BaseModel):
    """Dados para cadastrar uma fruta comercial."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Maçã Gala",
                "code": "01234",
                "price_per_kg": "8.99",
                "unit": "kg",
                "active": True,
                "vision_label": "apple_gala",
            }
        }
    )

    name: str = Field(min_length=1, max_length=120, examples=["Maçã Gala"])
    # Código comercial. Mantido como texto para preservar zeros à esquerda.
    code: str = Field(min_length=1, max_length=40, examples=["01234"])
    price_per_kg: Money | None = Field(default=None, ge=0)
    unit: str = Field(default="kg", min_length=1, max_length=16)
    active: bool = True
    # Mapeamento classe do modelo -> fruta cadastrada (opcional).
    vision_label: str | None = Field(default=None, max_length=80, examples=["apple_gala"])

    @field_validator("name", "unit")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("não pode ser vazio")
        return value

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        # Remove espaços nas pontas, mas preserva zeros à esquerda.
        value = value.strip()
        if not value:
            raise ValueError("não pode ser vazio")
        if any(char.isspace() for char in value):
            raise ValueError("não pode conter espaços internos")
        return value

    @field_validator("vision_label")
    @classmethod
    def _normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("não pode ser vazio")
        return value


class FruitRead(BaseModel):
    """Fruta exposta pela API. Valores de exemplo são fictícios."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12,
                "name": "Maçã Gala",
                "code": "01234",
                "price_per_kg": "8.99",
                "unit": "kg",
                "active": True,
                "vision_label": "apple_gala",
            }
        },
    )

    id: int
    name: str
    code: str
    price_per_kg: Money | None
    unit: str
    active: bool
    vision_label: str | None = None


class FruitSummary(BaseModel):
    """Dados comerciais usados nas respostas de reconhecimento."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12,
                "name": "Maçã Gala",
                "code": "01234",
                "price_per_kg": "8.99",
                "unit": "kg",
            }
        },
    )

    id: int
    name: str
    code: str
    price_per_kg: Money | None
    unit: str


class FruitListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 12,
                        "name": "Maçã Gala",
                        "code": "01234",
                        "price_per_kg": "8.99",
                        "unit": "kg",
                        "active": True,
                        "vision_label": "apple_gala",
                    }
                ],
                "limit": 20,
                "offset": 0,
                "total": 1,
            }
        }
    )

    items: list[FruitRead]
    limit: int
    offset: int
    total: int
