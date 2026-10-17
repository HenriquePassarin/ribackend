"""Modelos de persistência."""

from app.models.base import Base
from app.models.fruit import Fruit
from app.models.recognition import Recognition, RecognitionStatus

__all__ = ["Base", "Fruit", "Recognition", "RecognitionStatus"]
