"""Repositório do cadastro de frutas.

Toda a persistência passa por aqui, de modo que a escolha do banco/ORM possa ser
trocada sem alterar as regras de negócio.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.fruit import Fruit


class FruitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _filtered(self, *, active: bool | None, search: str | None):
        statement = select(Fruit)
        if active is not None:
            statement = statement.where(Fruit.active.is_(active))
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(or_(Fruit.name.ilike(pattern), Fruit.code.ilike(pattern)))
        return statement

    def list(self, *, active: bool | None, search: str | None, limit: int, offset: int) -> list[Fruit]:
        statement = (
            self._filtered(active=active, search=search)
            .order_by(Fruit.name.asc(), Fruit.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    def count(self, *, active: bool | None, search: str | None) -> int:
        statement = select(func.count()).select_from(self._filtered(active=active, search=search).subquery())
        return int(self.session.execute(statement).scalar_one())

    def get(self, fruit_id: int) -> Fruit | None:
        return self.session.get(Fruit, fruit_id)

    def get_by_code(self, code: str) -> Fruit | None:
        statement = select(Fruit).where(Fruit.code == code)
        return self.session.execute(statement).scalars().first()

    def get_by_vision_label(self, label: str) -> Fruit | None:
        """Mapeia a classe prevista pelo modelo para uma fruta cadastrada."""
        statement = select(Fruit).where(Fruit.vision_label == label)
        return self.session.execute(statement).scalars().first()

    def add(self, fruit: Fruit) -> Fruit:
        self.session.add(fruit)
        self.session.commit()
        self.session.refresh(fruit)
        return fruit

    def commit(self) -> None:
        self.session.commit()
