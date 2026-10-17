"""Casos de uso do cadastro de frutas."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.errors import DuplicateFruitError, FruitNotFoundError
from app.models.fruit import Fruit
from app.repositories.fruit_repository import FruitRepository
from app.schemas.fruit import FruitCreate

logger = logging.getLogger(__name__)


class FruitService:
    def __init__(self, repository: FruitRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def list_fruits(
        self,
        *,
        active: bool | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Fruit], int]:
        limit = min(limit, self.settings.fruits_max_limit)
        items = self.repository.list(active=active, search=search, limit=limit, offset=offset)
        total = self.repository.count(active=active, search=search)
        return items, total

    def get_fruit(self, fruit_id: int) -> Fruit:
        fruit = self.repository.get(fruit_id)
        if fruit is None:
            raise FruitNotFoundError(details={"fruit_id": fruit_id})
        return fruit

    def create_fruit(self, payload: FruitCreate) -> Fruit:
        if self.repository.get_by_code(payload.code) is not None:
            raise DuplicateFruitError(details={"code": payload.code})
        if payload.vision_label and self.repository.get_by_vision_label(payload.vision_label) is not None:
            raise DuplicateFruitError(
                details={"vision_label": payload.vision_label},
                message="Já existe uma fruta associada a este rótulo do modelo.",
            )

        fruit = Fruit(
            name=payload.name,
            code=payload.code,
            price_per_kg=payload.price_per_kg,
            unit=payload.unit,
            active=payload.active,
            vision_label=payload.vision_label,
        )
        created = self.repository.add(fruit)
        logger.info("Fruta cadastrada id=%s code=%s active=%s", created.id, created.code, created.active)
        return created
