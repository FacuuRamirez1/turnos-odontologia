"""Tests C-02 §1.5 — `Paciente` + consentimiento: feliz / negocio / borde (RED primero).

Escenarios aprobados en tasks.md 1.5:
- feliz: crea con DNI + consentimiento + fecha;
- negocio: DNI duplicado rechazado;
- borde: consentimiento true sin fecha o flag false rechazado.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Paciente

CONSENT_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def test_crea_paciente_con_consentimiento_feliz(db_session: Session) -> None:
    paciente = Paciente(
        dni="99.999.901",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=CONSENT_AT,
    )
    db_session.add(paciente)
    db_session.commit()

    assert paciente.id is not None
    assert paciente.is_active is True
    assert paciente.deleted_at is None


def test_dni_duplicado_rechazado_negocio(db_session: Session) -> None:
    """Negocio: segundo paciente con el mismo DNI viola UNIQUE (habilita A2 por DNI)."""
    db_session.add(
        Paciente(
            dni="99.999.902",
            nombre="Bruno",
            apellido="Ficticio",
            consentimiento_datos=True,
            consentimiento_fecha=CONSENT_AT,
        )
    )
    db_session.commit()
    db_session.add(
        Paciente(
            dni="99.999.902",
            nombre="Otro",
            apellido="Nombre",
            consentimiento_datos=True,
            consentimiento_fecha=CONSENT_AT,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Paciente).count() == 1


def test_consentimiento_true_sin_fecha_rechazado_borde(db_session: Session) -> None:
    """Borde RN-CONSENTIMIENTO: flag true sin timestamp viola el CHECK bloqueante."""
    db_session.add(
        Paciente(
            dni="99.999.903",
            nombre="Carla",
            apellido="Ficticia",
            consentimiento_datos=True,
            consentimiento_fecha=None,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Paciente).count() == 0


def test_consentimiento_false_rechazado_borde(db_session: Session) -> None:
    """Borde RN-CONSENTIMIENTO: sin consentimiento no hay fila (aun con fecha)."""
    db_session.add(
        Paciente(
            dni="99.999.904",
            nombre="Diego",
            apellido="Ficticio",
            consentimiento_datos=False,
            consentimiento_fecha=CONSENT_AT,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Paciente).count() == 0


def test_soft_delete_conserva_fila(db_session: Session) -> None:
    """Soft-delete (1.6): la fila sigue consultable por id, inactiva y fechada."""
    paciente = Paciente(
        dni="99.999.905",
        nombre="Elena",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=CONSENT_AT,
    )
    db_session.add(paciente)
    db_session.commit()

    paciente.soft_delete()
    db_session.commit()

    viva = db_session.get(Paciente, paciente.id)
    assert viva is not None
    assert viva.is_active is False
    assert viva.deleted_at is not None
    assert db_session.query(Paciente).count() == 1
