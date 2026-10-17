"""Modelo de persistência da fruta comercial."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Fruit(Base):
    """Fruta (ou variedade comercial) cadastrada.

    ``code`` e ``price_per_kg`` são dados comerciais: vêm do cadastro oficial e
    nunca da previsão visual.
    """

    __tablename__ = "fruits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Código comercial/POS. String para preservar zeros à esquerda.
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    # Decimal, não float: valores monetários não podem depender de binário.
    price_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Rótulo previsto pelo modelo associado a esta fruta (mapeamento explícito
    # classe -> cadastro). Ver decisão registrada no README.
    vision_label: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
