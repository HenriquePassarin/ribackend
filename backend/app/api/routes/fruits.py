"""Endpoints de consulta e cadastro de frutas.

Código comercial e preço vêm deste cadastro; nunca da previsão visual.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies import get_fruit_service
from app.core.config import Settings, get_settings
from app.schemas.errors import ErrorResponse
from app.schemas.fruit import FruitCreate, FruitListResponse, FruitRead
from app.services.fruit_service import FruitService

router = APIRouter(prefix="/fruits", tags=["fruits"])

# Respostas documentadas por rota: cada endpoint anuncia apenas os códigos que pode emitir.
_CREATE_ERROR_RESPONSES = {
    409: {"model": ErrorResponse, "description": "DUPLICATE_FRUIT"},
    422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
}

_GET_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "FRUIT_NOT_FOUND"},
    422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
}


@router.get(
    "",
    response_model=FruitListResponse,
    summary="Lista frutas cadastradas",
    responses={422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"}},
)
def list_fruits(
    active: bool | None = Query(default=None, description="Filtra por frutas ativas/inativas"),
    search: str | None = Query(
        default=None, max_length=80, description="Busca por nome ou código comercial"
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        description="Limite de resultados. Valores acima do máximo configurado são reduzidos ao máximo.",
    ),
    offset: int = Query(default=0, ge=0, description="Deslocamento para paginação"),
    service: FruitService = Depends(get_fruit_service),
    settings: Settings = Depends(get_settings),
) -> FruitListResponse:
    effective_limit = min(limit or settings.fruits_default_limit, settings.fruits_max_limit)
    items, total = service.list_fruits(
        active=active, search=search, limit=effective_limit, offset=offset
    )
    return FruitListResponse(
        items=[FruitRead.model_validate(item) for item in items],
        limit=effective_limit,
        offset=offset,
        total=total,
    )


@router.post(
    "",
    response_model=FruitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra uma fruta comercial",
    description=(
        "Extensão ao contrato ilustrado na especificação (que define apenas consulta), "
        "necessária porque o escopo inicial inclui o cadastro de frutas. "
        "Código e preço são dados comerciais informados pelo mercado; a API não os infere."
    ),
    responses=_CREATE_ERROR_RESPONSES,
)
def create_fruit(
    payload: FruitCreate,
    service: FruitService = Depends(get_fruit_service),
) -> FruitRead:
    fruit = service.create_fruit(payload)
    return FruitRead.model_validate(fruit)


@router.get(
    "/{fruit_id}",
    response_model=FruitRead,
    summary="Busca uma fruta pelo identificador interno",
    responses=_GET_ERROR_RESPONSES,
)
def get_fruit(
    fruit_id: int = Path(ge=1, description="Identificador interno da fruta"),
    service: FruitService = Depends(get_fruit_service),
) -> FruitRead:
    return FruitRead.model_validate(service.get_fruit(fruit_id))
