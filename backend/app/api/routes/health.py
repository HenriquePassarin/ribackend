"""Verificação de disponibilidade da API.

Não expõe segredos, versões internas de bibliotecas nem estado do banco.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Verifica se a aplicação está respondendo",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
