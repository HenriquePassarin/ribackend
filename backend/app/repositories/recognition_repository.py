"""Repositório das tentativas de reconhecimento."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.recognition import Recognition


class RecognitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, recognition: Recognition) -> Recognition:
        self.session.add(recognition)
        self.session.commit()
        self.session.refresh(recognition)
        return recognition

    def get(self, recognition_id: str) -> Recognition | None:
        return self.session.get(Recognition, recognition_id)

    def commit(self) -> None:
        self.session.commit()

    def refresh(self, recognition: Recognition) -> Recognition:
        self.session.refresh(recognition)
        return recognition
