"""Tests C-02 §4.1 — seed dev idempotente con datos ficticios (RED primero)."""

import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.infra.db.models import Odontologo, Paciente, Usuario
from app.infra.db.seed_dev import seed

DNI_FICTICIO = re.compile(r"^99\.999\.9\d{2}$")
SEED_DATA = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "infra"
    / "db"
    / "seed_data"
    / "feriados_bloqueos_ejemplo.json"
)


def test_seed_idempotente_doble_corrida(db_session: Session) -> None:
    """4.1: dos corridas → mismos conteos, cero duplicados."""
    seed(db_session)
    primera = (
        db_session.query(Usuario).count(),
        db_session.query(Odontologo).count(),
        db_session.query(Paciente).count(),
    )
    assert primera == (4, 2, 5)

    seed(db_session)
    assert (
        db_session.query(Usuario).count(),
        db_session.query(Odontologo).count(),
        db_session.query(Paciente).count(),
    ) == primera


def test_seed_solo_datos_ficticios(db_session: Session) -> None:
    """P11: pacientes con DNI patrón `99.999.9xx` y consentimiento completo."""
    seed(db_session)
    pacientes = db_session.query(Paciente).all()
    assert len(pacientes) == 5
    for paciente in pacientes:
        assert DNI_FICTICIO.match(paciente.dni), paciente.dni
        assert paciente.consentimiento_datos is True
        assert isinstance(paciente.consentimiento_fecha, datetime)


def test_seed_montos_distintos_por_odontologo(db_session: Session) -> None:
    """4.1: los 2 odontólogos tienen montos distintos (seña 65000 vs 70000)."""
    seed(db_session)
    senias = sorted(o.monto_senia for o in db_session.query(Odontologo).all())
    assert len(senias) == 2 and senias[0] != senias[1]


def test_seed_roles_completos(db_session: Session) -> None:
    """4.1: 2 odontólogos + 1 recepcionista + 1 admin, hashes demo no-plaintext."""
    seed(db_session)
    roles = sorted(u.rol for u in db_session.query(Usuario).all())
    assert roles == ["admin", "odontologo", "odontologo", "recepcionista"]
    for usuario in db_session.query(Usuario).all():
        assert len(usuario.password_hash) >= 60


def test_fixture_feriados_bloqueos_valida_para_c04() -> None:
    """4.1: 1 feriado + 1 bloqueo de ejemplo como fixture (tabla `bloqueo` = C-04)."""
    fixture = json.loads(SEED_DATA.read_text(encoding="utf-8"))
    motivos = [b["motivo"] for b in fixture["bloqueos"]]
    assert motivos.count("feriado") == 1 and motivos.count("bloqueo") == 1
    for bloqueo in fixture["bloqueos"]:
        assert bloqueo["motivo"] in ("pausa", "feriado", "bloqueo", "vacaciones")
        assert bloqueo["desde"] < bloqueo["hasta"]
