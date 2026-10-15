"""Tests C-02 §1.3 — `Odontologo`: feliz / negocio / borde (U2: RED primero).

Escenarios aprobados en tasks.md 1.3:
- feliz: crea con montos válidos;
- negocio: monto negativo rechazado;
- borde: segundo perfil con mismo `user_id` rechazado.
"""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Odontologo, Usuario

HASH = "$2b$04$" + "c" * 53
assert len(HASH) == 60


def _usuario(db_session: Session, email: str) -> Usuario:
    usuario = Usuario(email=email, password_hash=HASH, rol="odontologo")
    db_session.add(usuario)
    db_session.commit()
    return usuario


def test_crea_odontologo_montos_validos_feliz(db_session: Session) -> None:
    usuario = _usuario(db_session, "odonto1@clinica-ficticia.example.ar")
    perfil = Odontologo(
        user_id=usuario.id,
        monto_turno=Decimal("65000.00"),
        monto_senia=Decimal("65000.00"),
    )
    db_session.add(perfil)
    db_session.commit()

    assert perfil.id is not None
    assert perfil.is_active is True
    assert perfil.monto_turno == Decimal("65000.00")


def test_monto_negativo_rechazado_negocio(db_session: Session) -> None:
    """Negocio: `monto_turno` bajo cero viola el CHECK de montos no negativos."""
    usuario = _usuario(db_session, "odonto2@clinica-ficticia.example.ar")
    db_session.add(
        Odontologo(
            user_id=usuario.id,
            monto_turno=Decimal("-1.00"),
            monto_senia=Decimal("0.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Odontologo).count() == 0


def test_senia_negativa_rechazada(db_session: Session) -> None:
    """Triangulación: el CHECK de `monto_senia` existe, no solo el de turno."""
    usuario = _usuario(db_session, "odonto4@clinica-ficticia.example.ar")
    db_session.add(
        Odontologo(
            user_id=usuario.id,
            monto_turno=Decimal("65000.00"),
            monto_senia=Decimal("-100.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Odontologo).count() == 0


def test_segundo_perfil_mismo_user_rechazado_borde(db_session: Session) -> None:
    """Borde: un `user_id` vincula como máximo un perfil (UNIQUE)."""
    usuario = _usuario(db_session, "odonto3@clinica-ficticia.example.ar")
    db_session.add(
        Odontologo(
            user_id=usuario.id,
            monto_turno=Decimal("70000.00"),
            monto_senia=Decimal("70000.00"),
        )
    )
    db_session.commit()
    db_session.add(
        Odontologo(
            user_id=usuario.id,
            monto_turno=Decimal("70000.00"),
            monto_senia=Decimal("70000.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Odontologo).count() == 1
