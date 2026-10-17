"""Modelo de persistência da tentativa de reconhecimento."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.fruit import utcnow


class RecognitionStatus(StrEnum):
    """Estados possíveis de uma tentativa de reconhecimento."""

    RECOGNIZED = "recognized"
    CONFIRMATION_REQUIRED = "confirmation_required"
    UNRECOGNIZED = "unrecognized"
    NO_CATALOG_MATCH = "no_catalog_match"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    FAILED = "failed"


# Estados em que o atendente ainda pode confirmar/corrigir a tentativa.
CONFIRMABLE_STATUSES: frozenset[RecognitionStatus] = frozenset(
    {
        RecognitionStatus.RECOGNIZED,
        RecognitionStatus.CONFIRMATION_REQUIRED,
        RecognitionStatus.UNRECOGNIZED,
        RecognitionStatus.NO_CATALOG_MATCH,
    }
)

# Estados terminais: não aceitam nova confirmação.
FINAL_STATUSES: frozenset[RecognitionStatus] = frozenset(
    {RecognitionStatus.CONFIRMED, RecognitionStatus.CORRECTED, RecognitionStatus.FAILED}
)


class Recognition(Base):
    """Tentativa de reconhecimento de uma imagem.

    A imagem não é persistida por padrão.
    """

    __tablename__ = "recognitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    predicted_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_fruit_id: Mapped[int | None] = mapped_column(
        ForeignKey("fruits.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_fruit_id: Mapped[int | None] = mapped_column(
        ForeignKey("fruits.id"), nullable=True, index=True
    )
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
