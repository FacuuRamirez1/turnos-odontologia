"""Sesion SQLAlchemy por request — sin create_all en runtime (P3: solo Alembic)."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.infra.db.base import Base  # noqa: F401  (registra metadata para Alembic)

_settings = get_settings()
_engine = create_engine(_settings.database_url, future=True)
SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: una sesion por request, siempre cerrada al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
