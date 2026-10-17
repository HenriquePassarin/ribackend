"""Schemas (contratos HTTP) da API."""

from app.schemas.errors import ErrorDetail, ErrorResponse
from app.schemas.fruit import (
    FruitCreate,
    FruitListResponse,
    FruitRead,
    FruitSummary,
    serialize_money,
)
from app.schemas.recognition import (
    PredictionOut,
    RecognitionConfirmRequest,
    RecognitionConfirmResponse,
    RecognitionResponse,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "FruitCreate",
    "FruitListResponse",
    "FruitRead",
    "FruitSummary",
    "PredictionOut",
    "RecognitionConfirmRequest",
    "RecognitionConfirmResponse",
    "RecognitionResponse",
    "serialize_money",
]
