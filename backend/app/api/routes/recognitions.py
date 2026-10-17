"""Endpoints de reconhecimento e confirmação do atendente."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Path, UploadFile

from app.api.dependencies import get_recognition_service
from app.api.uploads import read_upload_limited
from app.core.config import Settings, get_settings
from app.schemas.errors import ErrorResponse
from app.schemas.fruit import FruitSummary
from app.schemas.recognition import (
    PredictionOut,
    RecognitionConfirmRequest,
    RecognitionConfirmResponse,
    RecognitionResponse,
)
from app.services.recognition_service import RecognitionOutcome, RecognitionService

router = APIRouter(prefix="/recognitions", tags=["recognitions"])

# Respostas documentadas por rota: cada endpoint anuncia apenas os códigos que pode emitir.
_RECOGNIZE_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "INVALID_IMAGE, EMPTY_IMAGE"},
    413: {"model": ErrorResponse, "description": "IMAGE_TOO_LARGE"},
    415: {"model": ErrorResponse, "description": "UNSUPPORTED_MEDIA_TYPE"},
    422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
    500: {"model": ErrorResponse, "description": "INTERNAL_ERROR"},
    503: {"model": ErrorResponse, "description": "MODEL_UNAVAILABLE"},
    504: {"model": ErrorResponse, "description": "INFERENCE_TIMEOUT"},
}

_CONFIRM_ERROR_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "FRUIT_INACTIVE, INVALID_STATE (tentativa já finalizada ou falha técnica)",
    },
    404: {"model": ErrorResponse, "description": "RECOGNITION_NOT_FOUND, FRUIT_NOT_FOUND"},
    422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
    500: {"model": ErrorResponse, "description": "INTERNAL_ERROR"},
}


def _to_response(outcome: RecognitionOutcome) -> RecognitionResponse:
    recognition = outcome.recognition
    return RecognitionResponse(
        recognition_id=recognition.id,
        status=recognition.status,
        prediction=PredictionOut(
            label=recognition.predicted_label,
            confidence=recognition.confidence,
            model_version=recognition.model_version,
        ),
        fruit=FruitSummary.model_validate(outcome.fruit) if outcome.fruit is not None else None,
        confirmation_required=outcome.confirmation_required,
    )


@router.post(
    "",
    response_model=RecognitionResponse,
    summary="Reconhece uma fruta a partir de uma imagem",
    description=(
        "Recebe uma imagem (multipart/form-data, campo `file`) e sugere uma fruta cadastrada. "
        "A confiança do modelo não é garantia de acerto: quando exigida, a confirmação humana "
        "deve ser registrada em POST /recognitions/{recognition_id}/confirm. "
        "Nome, código e preço sempre vêm do cadastro, nunca da previsão visual."
    ),
    responses=_RECOGNIZE_ERROR_RESPONSES,
)
async def create_recognition(
    file: UploadFile = File(description="Imagem da fruta (PNG ou JPEG)"),
    service: RecognitionService = Depends(get_recognition_service),
    settings: Settings = Depends(get_settings),
) -> RecognitionResponse:
    data = await read_upload_limited(file, settings.max_image_size_bytes)
    outcome = await service.recognize(
        content_type=file.content_type,
        data=data,
        filename=file.filename,
    )
    return _to_response(outcome)


@router.post(
    "/{recognition_id}/confirm",
    response_model=RecognitionConfirmResponse,
    summary="Registra a confirmação ou correção do atendente",
    description=(
        "Registra a fruta escolhida pelo atendente. Se for a fruta sugerida, o status passa a "
        "`confirmed`; se for outra, passa a `corrected`. Não altera o cadastro nem o preço e não "
        "representa a finalização de uma venda."
    ),
    responses=_CONFIRM_ERROR_RESPONSES,
)
def confirm_recognition(
    payload: RecognitionConfirmRequest,
    recognition_id: str = Path(description="Identificador da tentativa de reconhecimento"),
    service: RecognitionService = Depends(get_recognition_service),
) -> RecognitionConfirmResponse:
    recognition, fruit = service.confirm(recognition_id=recognition_id, fruit_id=payload.fruit_id)
    assert recognition.confirmed_at is not None  # garantido pelo serviço
    return RecognitionConfirmResponse(
        recognition_id=recognition.id,
        status=recognition.status,
        fruit=FruitSummary.model_validate(fruit),
        confirmed_at=recognition.confirmed_at,
    )
