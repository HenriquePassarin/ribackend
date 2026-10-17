"""Contrato padronizado de erro."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Formato único de erro: `{"error": {"code", "message", "details"}}`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "INVALID_IMAGE",
                    "message": "O arquivo enviado não é uma imagem válida.",
                    "details": None,
                }
            }
        }
    )

    error: ErrorDetail
