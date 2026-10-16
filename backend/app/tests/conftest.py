"""Fixtures compartidas C-02 — engine SQLite en memoria por test.

Solo para tests: `create_all` aqui esta permitido por P3 (el veto rige para
runtime en `backend/app` y `backend/alembic` fuera de `tests/`).
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.auth as auth_module
from app.core.security import dependencies
from app.infra.db.base import Base
from app.infra.db.session import get_db
from app.infra.redis.blacklist import TokenBlacklist
from app.main import app


@pytest.fixture()
def db_engine() -> Iterator[Engine]:
    """Engine SQLite en memoria con el DDL registrado en `Base`.

    `StaticPool` + `check_same_thread=False`: una sola conexión compartida
    para que `TestClient` (handlers en otro thread, C-03) vea la misma DB.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Sesion SQLite aislada sobre `db_engine` (misma conexión del thread)."""
    factory = sessionmaker(bind=db_engine, class_=Session, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


TEST_AUTH_SECRET = "secreto-de-test-ficticio"


@pytest.fixture()
def auth_client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """C-03: TestClient contra la app real con DB SQLite y seguridad de test.

    Secreto + blacklist + rate-limit frescos por test (sin estado global
    entre tests); base https para que el jar envíe la cookie `Secure`.
    """
    monkeypatch.setenv("FRONTEND_URL", "https://test.ficticia.example.ar")
    dependencies.configure_security(TEST_AUTH_SECRET, TokenBlacklist(client=None))
    auth_module.reset_rate_limiter()
    from app.api.reservas import reset_reservas_limiter

    reset_reservas_limiter()
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()
