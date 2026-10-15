"""Tests C-01 §3 — base SQLAlchemy + sesion por request, cero create_all (U2)."""

from pathlib import Path

from sqlalchemy.orm import DeclarativeBase


def test_base_declarativa_feliz() -> None:
    """Feliz: Base importable como DeclarativeBase con las tablas core C-02+."""
    from app.infra.db import models as _models  # noqa: F401 (registra tablas)
    from app.infra.db.base import Base

    assert issubclass(Base, DeclarativeBase)
    assert {"usuario", "odontologo", "paciente"} <= set(Base.metadata.tables)


def test_get_db_es_dependencia_por_request() -> None:
    """Error de negocio: get_db debe ser generador que entrega y cierra sesion."""
    import inspect

    from app.infra.db.session import get_db

    assert inspect.isgeneratorfunction(get_db)


def test_sin_create_all_en_backend_borde() -> None:
    """Borde/P3: ninguna llamada a create_all en backend/ (migraciones Alembic mandan)."""
    root = Path(__file__).resolve().parents[2]
    hits = [
        str(p)
        for p in root.rglob("*.py")
        if "tests" not in p.parts
        and ".create_all(" in p.read_text(encoding="utf-8").replace(" ", "")
    ]
    assert hits == []
