"""Agregador das rotas de negócio (prefixo /api/v1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import Settings
from app.api.routes import fruits, recognitions


def build_api_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix=settings.api_v1_prefix)
    router.include_router(fruits.router)
    router.include_router(recognitions.router)
    return router
