"""Tests C-05 §2.2 — job expiración TTL pre-reservas (RED primero, task 2.2).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: `creado` vencido → `cancelado` (sistema/ttl_expirado) + historial;
- negocio: `confirmado` añejo intacto, sin historial nuevo;
- borde: `creado` vencido cuenta como libre por cómputo aunque el job
  no haya corrido (`slot_libre_por_computo`).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session


def _sembrar(db_session: Session, estado: str, creado_hace_min: int) -> uuid.UUID:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "k" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-ttl-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"88{suf}", nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    ini = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ini,
                  fin=ini + timedelta(minutes=30), estado=estado,
                  canal="web", idempotency_key=f"key-ttl-{suf}")
    db_session.add(turno)
    db_session.commit()
    # Envejece created_at para simular el paso del TTL.
    turno.created_at = datetime.now(UTC) - timedelta(minutes=creado_hace_min)
    db_session.commit()
    return uuid.UUID(str(turno.id))


def test_creado_vencido_expira_a_cancelado_feliz(db_session: Session) -> None:
    from app.domain.turnos.expiracion import expirar_vencidos

    turno_id = _sembrar(db_session, "creado", creado_hace_min=60)

    n = expirar_vencidos(db_session, ttl_min=15)
    assert n == 1

    from app.infra.db.models import Turno, TurnoHistorial
    turno = db_session.query(Turno).filter(Turno.id == turno_id).first()
    assert turno is not None and turno.estado == "cancelado"
    hist = db_session.query(TurnoHistorial).filter(
        TurnoHistorial.turno_id == turno_id).all()
    assert len(hist) == 1
    assert hist[0].actor_tipo == "sistema" and hist[0].motivo == "ttl_expirado"


def test_confirmado_anejo_intacto_negocio(db_session: Session) -> None:
    from app.domain.turnos.expiracion import expirar_vencidos

    turno_id = _sembrar(db_session, "confirmado", creado_hace_min=600)

    assert expirar_vencidos(db_session, ttl_min=15) == 0

    from app.infra.db.models import Turno, TurnoHistorial
    turno = db_session.query(Turno).filter(Turno.id == turno_id).first()
    assert turno is not None and turno.estado == "confirmado"
    assert db_session.query(TurnoHistorial).filter(
        TurnoHistorial.turno_id == turno_id).count() == 0


def test_creado_vencido_libre_por_computo_borde(db_session: Session) -> None:
    from app.domain.turnos.expiracion import slot_libre_por_computo

    turno_id = _sembrar(db_session, "creado", creado_hace_min=60)

    from app.infra.db.models import Turno
    turno = db_session.query(Turno).filter(Turno.id == turno_id).first()
    assert turno is not None
    # El job aún no corrió (sigue `creado`) pero el cómputo ya lo da libre.
    assert slot_libre_por_computo(turno, ttl_min=15) is True
    assert turno.estado == "creado"
