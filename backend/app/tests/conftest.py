"""Fixtures compartidas C-02 — engine SQLite en memoria por test.

Solo para tests: `create_all` aqui esta permitido por P3 (el veto rige para
runtime en `backend/app` y `backend/alembic` fuera de `tests/`).
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infra.db.base import Base


@pytest.fixture()
def db_engine() -> Iterator[Engine]:
    """Engine SQLite en memoria con el DDL registrado en `Base`."""
    engine = create_engine("sqlite:///:memory:")
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
