"""Tests C-04 §1.1 — modelos Disponibilidad/Bloqueo + constraints (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: fila válida de cada modelo persiste;
- negocio: hora_fin<=hora_inicio / duracion<=0 / tope<=0 / motivo inválido /
  dia_semana fuera de 0..6 rechazados;
- borde: vigente_desde > vigente_hasta rechazado.
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Bloqueo, Disponibilidad, Odontologo, Usuario

HASH = "$2b$04$" + "e" * 53
assert len(HASH) == 60


def _odontologo_id(db_session: Session) -> uuid.UUID:
    usuario = Usuario(
        email="odonto-c04@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo"
    )
    db_session.add(usuario)
    db_session.commit()
    perfil = Odontologo(
        user_id=usuario.id, monto_turno=Decimal("70000.00"), monto_senia=Decimal("65000.00")
    )
    db_session.add(perfil)
    db_session.commit()
    return uuid.UUID(str(perfil.id))


def test_disponibilidad_valida_persiste_feliz(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    fila = Disponibilidad(
        odontologo_id=od_id,
        dia_semana=0,
        hora_inicio=time(9, 0),
        hora_fin=time(17, 0),
        duracion_min=30,
        tope_dia=14,
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
    )
    db_session.add(fila)
    db_session.commit()
    assert fila.id is not None
    assert db_session.query(Disponibilidad).count() == 1


def test_bloqueo_valido_persiste_feliz(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    fila = Bloqueo(
        odontologo_id=od_id,
        desde=datetime(2026, 11, 2, 13, 0, tzinfo=UTC),
        hasta=datetime(2026, 11, 2, 14, 0, tzinfo=UTC),
        motivo="bloqueo",
    )
    db_session.add(fila)
    db_session.commit()
    assert fila.id is not None


def test_rango_horario_invertido_rechazado_negocio(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Disponibilidad(
            odontologo_id=od_id,
            dia_semana=1,
            hora_inicio=time(17, 0),
            hora_fin=time(9, 0),
            duracion_min=30,
            tope_dia=14,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duracion_no_positiva_rechazada_negocio(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Disponibilidad(
            odontologo_id=od_id,
            dia_semana=1,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            duracion_min=0,
            tope_dia=14,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tope_no_positivo_rechazado_negocio(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Disponibilidad(
            odontologo_id=od_id,
            dia_semana=1,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            duracion_min=30,
            tope_dia=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_dia_semana_fuera_de_rango_rechazado_negocio(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Disponibilidad(
            odontologo_id=od_id,
            dia_semana=7,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            duracion_min=30,
            tope_dia=14,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_motivo_invalido_rechazado_negocio(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Bloqueo(
            odontologo_id=od_id,
            desde=datetime(2026, 11, 2, 13, 0, tzinfo=UTC),
            hasta=datetime(2026, 11, 2, 14, 0, tzinfo=UTC),
            motivo="siesta",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_bloqueo_invertido_rechazado_negocio(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Bloqueo(
            odontologo_id=od_id,
            desde=datetime(2026, 11, 2, 14, 0, tzinfo=UTC),
            hasta=datetime(2026, 11, 2, 13, 0, tzinfo=UTC),
            motivo="pausa",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_vigencia_invertida_rechazada_borde(db_session: Session) -> None:
    od_id = _odontologo_id(db_session)
    db_session.add(
        Disponibilidad(
            odontologo_id=od_id,
            dia_semana=2,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            duracion_min=30,
            tope_dia=14,
            vigente_desde=date(2026, 12, 31),
            vigente_hasta=date(2026, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
