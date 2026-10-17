"""Base declarativa do SQLAlchemy."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base para os modelos de persistência."""
