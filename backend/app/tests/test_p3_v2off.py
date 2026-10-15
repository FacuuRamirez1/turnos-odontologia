"""Tests C-02 §3.3 — P3 (cero `create_all`) + v2-off (cero escrituras, P13)."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.infra.db.models import ListaEspera, NotificacionWhatsapp

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _sin_espacios(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace(" ", "")


def test_cero_create_all_fuera_de_tests() -> None:
    """P3: runtime crea tablas solo vía Alembic; `create_all` solo en tests."""
    hits = [
        str(p)
        for p in BACKEND_ROOT.rglob("*.py")
        if "tests" not in p.parts and ".create_all(" in _sin_espacios(p)
    ]
    assert hits == []


def test_v2_off_sin_escrituras_con_whatsapp_apagado(db_session: Session) -> None:
    """P13: con `WHATSAPP_ENABLED=false`, v2-off existe como DDL y sigue vacía."""
    assert get_settings().whatsapp_enabled is False
    assert db_session.query(ListaEspera).count() == 0
    assert db_session.query(NotificacionWhatsapp).count() == 0


def test_v2_off_sin_repositorio_de_escritura() -> None:
    """P13: ningún módulo de app (fuera de models/migración/tests) toca v2-off."""
    legitimos = {"models", "tests", "versions"}
    hits = [
        str(p)
        for p in BACKEND_ROOT.rglob("*.py")
        if "ListaEspera" in p.read_text(encoding="utf-8")
        or "NotificacionWhatsapp" in p.read_text(encoding="utf-8")
        if not (legitimos & set(p.parts))
    ]
    assert hits == []
