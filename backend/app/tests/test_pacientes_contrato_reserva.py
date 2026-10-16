"""Tests C-06 §4.1 — contrato `PacienteService.resolve_or_create()` hacia C-05.

- feliz: con consentimiento crea (o reutiliza por DNI) y el flujo continúa;
- negocio: sin consentimiento levanta `ConsentimientoRequerido` y no persiste
  nada (ni paciente ni turno — turno mockeado, cero código C-05);
- borde: DNI con puntos/espacios reutiliza la misma fila.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.domain.pacientes.service import (
    ConsentimientoRequerido,
    PacienteService,
)
from app.infra.db.models import Paciente

CONSENT_AT = "2026-10-01T09:00:00+00:00"


def _fecha() -> datetime:
    return datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def test_reserva_con_consentimiento_crea_y_continua(db_session: Session) -> None:
    """Feliz: C-05 crea paciente y el flujo de reserva continúa (mock turno)."""
    turnos_mock: list[dict[str, str]] = []
    paciente, creado = PacienteService(db_session).resolve_or_create(
        dni="99.999.941",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=_fecha(),
    )
    assert creado is True
    turnos_mock.append({"paciente_id": str(paciente.id)})  # C-05 continuaría aquí
    assert len(turnos_mock) == 1
    assert db_session.query(Paciente).count() == 1


def test_reserva_sin_consentimiento_aborta_todo(db_session: Session) -> None:
    """Negocio/contrato: sin consentimiento → `ConsentimientoRequerido`, cero filas."""
    turnos_mock: list[dict[str, str]] = []
    with pytest.raises(ConsentimientoRequerido):
        PacienteService(db_session).resolve_or_create(
            dni="99.999.942",
            nombre="Bruno",
            apellido="Ficticio",
            consentimiento_datos=False,
            consentimiento_fecha=None,
        )
    # La UoW de C-05 aborta: ni paciente ni turno.
    assert turnos_mock == []
    assert db_session.query(Paciente).count() == 0


def test_reserva_reutiliza_por_dni_normalizado(db_session: Session) -> None:
    """Borde: segundo `resolve_or_create` con `99.999.943` ≡ `99999943` reutiliza."""
    svc = PacienteService(db_session)
    p1, c1 = svc.resolve_or_create(
        dni="99.999.943",
        nombre="Carla",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=_fecha(),
    )
    p2, c2 = svc.resolve_or_create(
        dni=" 99999943 ",
        nombre="Otro",
        apellido="Nombre",
        consentimiento_datos=True,
        consentimiento_fecha=_fecha(),
    )
    assert c1 is True and c2 is False
    assert str(p1.id) == str(p2.id)
    assert db_session.query(Paciente).count() == 1
    assert p2.nombre == "Carla"  # no sobrescribe la ficha existente
    _ = CONSENT_AT
