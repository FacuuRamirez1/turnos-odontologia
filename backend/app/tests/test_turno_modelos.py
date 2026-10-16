"""Tests C-05 §1.2 — modelos Turno/TurnoHistorial + repo scoped (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: turno válido persiste con estado `creado` + version 1;
- negocio: doble inserto mismo (odontologo_id, inicio) → IntegrityError
  (UNIQUE RN-DOBLE); fin<=inicio → IntegrityError (CHECK);
- borde: mismo inicio con distinto profesional sí persiste (aislamiento);
- pin P8: BaseRepository(Turno) sin odontologo_id → ValueError (fail-closed).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

HASH = "$2b$04$" + "h" * 53


def _sembrar(db_session: Session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    from app.infra.db.models import Odontologo, Paciente, Usuario

    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    ua = Usuario(email="od-a-c05@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    ub = Usuario(email="od-b-c05@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db_session.add_all([ua, ub])
    db_session.commit()
    pa = Odontologo(user_id=ua.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    pb = Odontologo(user_id=ub.id, monto_turno=Decimal("80000"), monto_senia=Decimal("65000"))
    db_session.add_all([pa, pb])
    db_session.commit()
    p1 = Paciente(dni="99999401", nombre="Ana", apellido="Ficticia",
                  consentimiento_datos=True, consentimiento_fecha=fecha)
    p2 = Paciente(dni="99999402", nombre="Bruno", apellido="Ficticio",
                  consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add_all([p1, p2])
    db_session.commit()
    return (uuid.UUID(str(pa.id)), uuid.UUID(str(pb.id)),
            uuid.UUID(str(p1.id)), uuid.UUID(str(p2.id)))


def _inicio_futuro(minutos: int = 0) -> datetime:
    return datetime.now(UTC).replace(microsecond=0) + timedelta(days=30, minutes=minutos)


def test_turno_valido_persiste_feliz(db_session: Session) -> None:
    from app.infra.db.models import Turno

    od_a, _, pac, _ = _sembrar(db_session)
    ini = _inicio_futuro()
    fila = Turno(paciente_id=pac, odontologo_id=od_a, inicio=ini,
                 fin=ini + timedelta(minutes=30), estado="creado",
                 canal="web", idempotency_key="key-feliz-001")
    db_session.add(fila)
    db_session.commit()
    assert fila.id is not None
    assert fila.estado == "creado"


def test_doble_inserto_mismo_slot_rechazado_negocio(db_session: Session) -> None:
    from app.infra.db.models import Turno

    od_a, _, pac, _ = _sembrar(db_session)
    ini = _inicio_futuro()
    db_session.add(Turno(paciente_id=pac, odontologo_id=od_a, inicio=ini,
                         fin=ini + timedelta(minutes=30), estado="creado",
                         canal="web", idempotency_key="key-doble-001"))
    db_session.commit()
    db_session.add(Turno(paciente_id=pac, odontologo_id=od_a, inicio=ini,
                         fin=ini + timedelta(minutes=30), estado="creado",
                         canal="web", idempotency_key="key-doble-002"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_fin_no_posterior_a_inicio_rechazado_negocio(db_session: Session) -> None:
    from app.infra.db.models import Turno

    od_a, _, pac, _ = _sembrar(db_session)
    ini = _inicio_futuro()
    db_session.add(Turno(paciente_id=pac, odontologo_id=od_a, inicio=ini,
                         fin=ini, estado="creado",
                         canal="web", idempotency_key="key-orden-001"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_mismo_inicio_distinto_profesional_persiste_borde(db_session: Session) -> None:
    from app.infra.db.models import Turno

    od_a, od_b, pac, _ = _sembrar(db_session)
    ini = _inicio_futuro()
    db_session.add(Turno(paciente_id=pac, odontologo_id=od_a, inicio=ini,
                         fin=ini + timedelta(minutes=30), estado="creado",
                         canal="web", idempotency_key="key-aisla-001"))
    db_session.add(Turno(paciente_id=pac, odontologo_id=od_b, inicio=ini,
                         fin=ini + timedelta(minutes=30), estado="creado",
                         canal="web", idempotency_key="key-aisla-002"))
    db_session.commit()
    assert db_session.query(Turno).count() == 2


def test_repo_turno_sin_scope_falla_cerrado_pin(db_session: Session) -> None:
    from app.infra.db.models import Turno
    from app.infra.db.repository import BaseRepository

    with pytest.raises(ValueError):
        BaseRepository(db_session, Turno)
