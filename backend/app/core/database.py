"""Criação de engine/sessão do banco de dados.

A escolha do banco é uma decisão pendente de infraestrutura; o projeto usa
SQLAlchemy atrás de uma camada de repositórios e lê a URL de DATABASE_URL.
O valor padrão (SQLite local) serve apenas para protótipo e testes.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.base import Base


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # Permite uso da mesma conexão em threads diferentes (TestClient/Uvicorn).
        connect_args["check_same_thread"] = False
    return create_engine(database_url, echo=echo, future=True, connect_args=connect_args)


@lru_cache
def _engine_for(database_url: str, echo: bool) -> Engine:
    return build_engine(database_url, echo=echo)


def get_engine(settings: Settings) -> Engine:
    return _engine_for(settings.database_url, settings.db_echo)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@lru_cache
def _session_factory_for(database_url: str, echo: bool) -> sessionmaker[Session]:
    return build_session_factory(_engine_for(database_url, echo))


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    return _session_factory_for(settings.database_url, settings.db_echo)


def init_schema(settings: Settings) -> None:
    """Cria o esquema a partir dos modelos (uso de protótipo/desenvolvimento)."""
    Base.metadata.create_all(bind=get_engine(settings))
