"""Tests C-05 §2.1 — tabla TRANSICIONES + transition() (RED primero, task 2.1).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: `confirmado→atendido` por odontólogo propio → 200-equivalente + historial;
- error: `creado→atendido` → TransicionInvalida (→422); `no_show` con fin
  futuro → GuardaTemporalRechazada (→422);
- borde: carrera con `version` vieja → VersionConflict (→409).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session


def _sembrar(db_session: Session, estado: str = "confirmado",
             fin_futuro: bool = True) -> uuid.UUID:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email=f"od-t-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(pac)
    db_session.commit()
    ahora = datetime.now(UTC).replace(microsecond=0)
    if fin_futuro:
        ini = ahora + timedelta(days=30)
    else:
        ini = ahora - timedelta(hours=2)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ini,
                  fin=ini + timedelta(minutes=30), estado=estado,
                  canal="web", idempotency_key=f"key-t-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.commit()
    return uuid.UUID(str(turno.id))


def test_confirmado_a_atendido_propio_feliz(db_session: Session) -> None:
    from app.domain.turnos.estados import transition

    turno_id = _sembrar(db_session, "confirmado")
    turno = transition(db_session, turno_id, "atendido",
                       actor_tipo="odontologo", actor_id="od-1", motivo="asistió")
    assert turno.estado == "atendido"

    from app.infra.db.models import TurnoHistorial
    filas = db_session.query(TurnoHistorial).filter(
        TurnoHistorial.turno_id == turno_id).all()
    assert len(filas) == 1
    assert filas[0].actor_tipo == "odontologo" and filas[0].fecha is not None


def test_creado_a_atendido_rechazado_negocio(db_session: Session) -> None:
    import pytest

    from app.domain.turnos.estados import TransicionInvalida, transition

    turno_id = _sembrar(db_session, "creado")
    with pytest.raises(TransicionInvalida):
        transition(db_session, turno_id, "atendido",
                   actor_tipo="odontologo", actor_id="od-1")


def test_no_show_con_fin_futuro_rechazado_negocio(db_session: Session) -> None:
    import pytest

    from app.domain.turnos.estados import GuardaTemporalRechazada, transition

    turno_id = _sembrar(db_session, "confirmado", fin_futuro=True)
    with pytest.raises(GuardaTemporalRechazada):
        transition(db_session, turno_id, "no_show",
                   actor_tipo="odontologo", actor_id="od-1")


def test_carrera_con_version_vieja_409_borde(db_session: Session) -> None:
    import pytest

    from app.domain.turnos.estados import VersionConflict, transition
    from app.infra.db.models import Turno

    turno_id = _sembrar(db_session, "confirmado")
    # Escritor concurrente avanza version 1→2 (el lector guarda la vieja).
    db_session.query(Turno).filter(Turno.id == turno_id).update({"version": 2})
    db_session.expire_all()
    with pytest.raises(VersionConflict):
        transition(db_session, turno_id, "atendido",
                   actor_tipo="odontologo", actor_id="od-1",
                   version_esperada=1)


def test_confirmado_a_cancelado_sin_pago_no_crea_devolucion_borde(
    db_session: Session,
) -> None:
    """C-08 D1: el hook no rompe el flujo sin pago ni inventa devoluciones."""
    from app.domain.turnos.estados import transition
    from app.infra.db.models import Devolucion

    turno_id = _sembrar(db_session, "confirmado")
    transition(db_session, turno_id, "cancelado",
               actor_tipo="recepcionista", actor_id="rec-1")
    db_session.commit()

    assert db_session.query(Devolucion).count() == 0


def test_confirmado_a_atendido_con_pago_no_crea_devolucion_borde(
    db_session: Session,
) -> None:
    """C-08 D1: el alta de devolución es exclusiva de `confirmado→cancelado`."""
    import uuid as _uuid
    from decimal import Decimal as _Decimal

    from app.domain.turnos.estados import transition
    from app.infra.db.models import Devolucion, Pago, Turno

    turno_id = _sembrar(db_session, "confirmado")
    turno = db_session.get(Turno, turno_id)
    assert turno is not None
    pago = Pago(turno_id=turno_id, odontologo_id=turno.odontologo_id,
                monto=_Decimal("10000.00"), moneda="ARS", proveedor="simulado",
                mp_payment_id=f"sim_pay_{_uuid.uuid4()}", estado="aprobado",
                idempotency_key=f"idem-{_uuid.uuid4().hex[:12]}")
    db_session.add(pago)
    db_session.commit()
    turno.pago_id = pago.id
    db_session.commit()

    transition(db_session, turno_id, "atendido",
               actor_tipo="odontologo", actor_id="od-1")
    db_session.commit()

    assert db_session.query(Devolucion).count() == 0

