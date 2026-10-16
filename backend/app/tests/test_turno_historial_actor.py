"""Tests C-05 §1.3 — historial sin actor rechazado (RED primero, task 1.3).

Escenarios (U2 feliz / negocio / borde):
- feliz: historial con actor persiste junto a la transición;
- negocio: insert sin `actor_tipo` → IntegrityError (NOT NULL/CHECK);
- borde: `actor_tipo` fuera del cerrado ('fantasma') → IntegrityError.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

HASH = "$2b$04$" + "i" * 53


def _sembrar(db_session: Session) -> uuid.UUID:
    from decimal import Decimal

    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email="od-hist@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni="99999501", nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(pac)
    db_session.commit()
    ini = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ini,
                  fin=ini + timedelta(minutes=30), estado="confirmado",
                  canal="web", idempotency_key="key-hist-001")
    db_session.add(turno)
    db_session.commit()
    return uuid.UUID(str(turno.id))


def test_historial_con_actor_persiste_feliz(db_session: Session) -> None:
    from app.infra.db.models import TurnoHistorial

    turno_id = _sembrar(db_session)
    db_session.add(TurnoHistorial(
        turno_id=turno_id, estado_anterior="creado", estado_nuevo="confirmado",
        actor_tipo="sistema", actor_id="mp-webhook",
        fecha=datetime.now(UTC), motivo="pago aprobado",
    ))
    db_session.commit()
    assert db_session.query(TurnoHistorial).count() == 1


def test_historial_sin_actor_rechazado_negocio(db_session: Session) -> None:
    from app.infra.db.models import TurnoHistorial

    turno_id = _sembrar(db_session)
    db_session.add(TurnoHistorial(
        turno_id=turno_id, estado_anterior="creado", estado_nuevo="confirmado",
        actor_tipo=None, actor_id=None,
        fecha=datetime.now(UTC), motivo="sin actor",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_historial_actor_fuera_de_lista_rechazado_borde(db_session: Session) -> None:
    from app.infra.db.models import TurnoHistorial

    turno_id = _sembrar(db_session)
    db_session.add(TurnoHistorial(
        turno_id=turno_id, estado_anterior="creado", estado_nuevo="confirmado",
        actor_tipo="fantasma", actor_id="x",
        fecha=datetime.now(UTC), motivo="actor inválido",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
