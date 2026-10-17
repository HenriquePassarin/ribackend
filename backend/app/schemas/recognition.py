"""Contratos HTTP de reconhecimento e confirmação."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.fruit import FruitSummary


class PredictionOut(BaseModel):
    """Saída do modelo de visão, quando disponível."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"label": "apple_gala", "confidence": 0.82, "model_version": "example-model-v1"}
        }
    )

    label: str | None
    confidence: float | None
    model_version: str | None


class RecognitionResponse(BaseModel):
    """Resposta de POST /recognitions. O exemplo abaixo é ilustrativo."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recognition_id": "4c3f40e1-7ad0-4c28-9c2e-44f1e52df9f0",
                "status": "confirmation_required",
                "prediction": {
                    "label": "apple_gala",
                    "confidence": 0.82,
                    "model_version": "example-model-v1",
                },
                "fruit": {
                    "id": 12,
                    "name": "Maçã Gala",
                    "code": "01234",
                    "price_per_kg": "8.99",
                    "unit": "kg",
                },
                "confirmation_required": True,
            }
        }
    )

    recognition_id: str
    status: str
    prediction: PredictionOut
    # None quando não há fruta correspondente no cadastro.
    fruit: FruitSummary | None
    confirmation_required: bool


class RecognitionConfirmRequest(BaseModel):
    """Corpo de POST /recognitions/{recognition_id}/confirm."""

    model_config = ConfigDict(json_schema_extra={"example": {"fruit_id": 12}})

    fruit_id: int = Field(gt=0)


class RecognitionConfirmResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recognition_id": "4c3f40e1-7ad0-4c28-9c2e-44f1e52df9f0",
                "status": "confirmed",
                "fruit": {
                    "id": 12,
                    "name": "Maçã Gala",
                    "code": "01234",
                    "price_per_kg": "8.99",
                    "unit": "kg",
                },
                "confirmed_at": "2026-10-16T20:00:00Z",
            }
        }
    )

    recognition_id: str
    status: str
    fruit: FruitSummary
    confirmed_at: datetime

    @field_serializer("confirmed_at")
    def _serialize_confirmed_at(self, value: datetime) -> str:
        # SQLite devolve datetimes sem timezone; normalizamos para UTC em formato ISO-8601.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
