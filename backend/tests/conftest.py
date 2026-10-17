"""Fixtures de teste: banco isolado em memória e cliente HTTP."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db, get_recognizer, get_settings
from app.core.config import Settings
from app.main import create_app
from app.models.base import Base
from helpers import FakeRecognizer, build_settings


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Banco de teste isolado (SQLite em memória, por teste)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def make_client(engine: Engine, session_factory: sessionmaker[Session]):
    """Fábrica de clientes HTTP com banco, configuração e adaptador controlados."""

    open_clients: list[TestClient] = []

    def _make(
        *,
        recognizer: object | None = None,
        settings: Settings | None = None,
        **settings_overrides: object,
    ) -> TestClient:
        config = settings or build_settings(**settings_overrides)
        app = create_app(config)

        def override_db() -> Iterator[Session]:
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_settings] = lambda: config
        if recognizer is not None:
            app.dependency_overrides[get_recognizer] = lambda: recognizer

        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()  # executa o lifespan da aplicação
        open_clients.append(client)
        return client

    yield _make

    for client in open_clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    """Cliente com o adaptador configurado padrão (stub, apenas para /health e frutas)."""
    return make_client()


@pytest.fixture
def fake_recognizer() -> FakeRecognizer:
    return FakeRecognizer()
