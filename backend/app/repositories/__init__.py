"""Camada de acesso a dados."""

from app.repositories.fruit_repository import FruitRepository
from app.repositories.recognition_repository import RecognitionRepository

__all__ = ["FruitRepository", "RecognitionRepository"]
