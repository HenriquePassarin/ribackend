"""Injeção de dependências do FastAPI.

Permite substituir banco, repositórios e o adaptador de visão em testes via
``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.repositories.fruit_repository import FruitRepository
from app.repositories.recognition_repository import RecognitionRepository
from app.services.fruit_service import FruitService
from app.services.recognition_service import RecognitionService
from app.vision.adapter import build_recognizer
from app.vision.base import FruitRecognizer


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[Session]:
    session = get_session_factory(settings)()
    try:
        yield session
    finally:
        session.close()


def get_fruit_repository(session: Session = Depends(get_db)) -> FruitRepository:
    return FruitRepository(session)


def get_recognition_repository(session: Session = Depends(get_db)) -> RecognitionRepository:
    return RecognitionRepository(session)


def get_recognizer(settings: Settings = Depends(get_settings)) -> FruitRecognizer:
    return build_recognizer(settings)


def get_fruit_service(
    repository: FruitRepository = Depends(get_fruit_repository),
    settings: Settings = Depends(get_settings),
) -> FruitService:
    return FruitService(repository=repository, settings=settings)


def get_recognition_service(
    fruit_repository: FruitRepository = Depends(get_fruit_repository),
    recognition_repository: RecognitionRepository = Depends(get_recognition_repository),
    recognizer: FruitRecognizer = Depends(get_recognizer),
    settings: Settings = Depends(get_settings),
) -> RecognitionService:
    return RecognitionService(
        fruit_repository=fruit_repository,
        recognition_repository=recognition_repository,
        recognizer=recognizer,
        settings=settings,
    )
