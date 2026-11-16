"""Tests C-08 task 2.3 — alta de devolución al cancelar (RED primero, design D1).

Escenarios (U2 feliz / negocio / borde):
- feliz: cancelación en término → `devolucion(pendiente, 100 %)` + evento
  `devolucion_solicitada` con actor, en el mismo commit del turno;
- negocio: fuera de término → 60 %; turno sin pago aprobado o `creado→cancelado`
  por sistema → sin devolución;
- borde: límite exacto de anticipación → 100 %; cotización 0 % (post-`inicio`)
  → turno `cancelado` con historial y slot liberado, SIN devolución, evento,
  recibo ni aviso, pago `aprobado` y turno nunca `devuelto`; fallo al insertar
  → rollback y turno sigue `confirmado`; `no_show` no crea devolución y
  `no_show→cancelado` → 422 (`TransicionInvalida`).

Se llama a `transition()` con un `ahora` fijo: la cotización usa el MISMO
instante que la transición (D1), así el borde exacto es determinístico.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.domain.turnos.estados import TransicionInvalida, VersionConflict, transition
from app.domain.turnos.ocupados import hay_solape
from app.infra.db.models import (
    Comprobante,
    Devolucion,
    EventoPago,
    Odontologo,
    Paciente,
    Pago,
    RecordatorioMail,
    Turno,
    TurnoHistorial,
    Usuario,
)

REF = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)


def _sembrar(
    db_session: Session, *, inicio: datetime, estado: str = "confirmado",
    con_pago: bool = True, pago_estado: str = "aprobado", monto: str = "10000.00",
) -> tuple[Turno, Pago | None]:
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-dev-{suf}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "p" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"),
                    monto_senia=Decimal("10000"))
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"55{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=inicio,
                  fin=inicio + timedelta(minutes=30), estado=estado,
                  canal="web", idempotency_key=f"key-dev-{suf}")
    db_session.add(turno)
    db_session.commit()
    pago: Pago | None = None
    if con_pago:
        pago = Pago(
            turno_id=turno.id, odontologo_id=od.id, monto=Decimal(monto),
            moneda="ARS", proveedor="simulado",
            mp_payment_id=f"sim_pay_{uuid.uuid4()}", estado=pago_estado,
            idempotency_key=f"idem-dev-{suf}",
        )
        db_session.add(pago)
        db_session.commit()
        turno.pago_id = pago.id
        db_session.add(turno)
        db_session.commit()
    return turno, pago


def _cancelar(
    db_session: Session, turno: Turno, *, actor_tipo: str = "recepcionista",
    actor_id: str = "u-rec-1",
) -> None:
    transition(db_session, uuid.UUID(str(turno.id)), "cancelado",
               actor_tipo=actor_tipo, actor_id=actor_id, ahora=REF)


def test_cancelacion_en_termino_crea_100_y_evento_con_actor_feliz(
    db_session: Session,
) -> None:
    """Feliz: en término → 100 %, monto del pago, evento con actor y fecha."""
    turno, pago = _sembrar(db_session, inicio=REF + timedelta(days=30))
    assert pago is not None

    _cancelar(db_session, turno)
    db_session.commit()

    dev = db_session.query(Devolucion).filter(Devolucion.pago_id == pago.id).one()
    assert dev.estado == "pendiente"
    assert dev.porcentaje == 100
    assert dev.monto == Decimal("10000.00")
    assert dev.turno_id == turno.id
    assert dev.idempotency_key == f"dev_{pago.id}"

    eventos = db_session.query(EventoPago).filter(
        EventoPago.pago_id == pago.id,
        EventoPago.tipo_evento == "devolucion_solicitada").all()
    assert len(eventos) == 1
    assert eventos[0].actor == "recepcionista"
    assert eventos[0].payload_json["actor_id"] == "u-rec-1"
    assert eventos[0].payload_json["porcentaje"] == 100
    assert eventos[0].payload_json["monto"] == "10000.00"

    db_session.refresh(turno)
    assert str(turno.estado) == "cancelado"
    historial = db_session.query(TurnoHistorial).filter(
        TurnoHistorial.turno_id == turno.id).all()
    assert len(historial) == 1
    assert (historial[0].estado_anterior, historial[0].estado_nuevo) == (
        "confirmado", "cancelado")


def test_cancelacion_fuera_de_termino_crea_60_negocio(db_session: Session) -> None:
    """Negocio: fuera de término (2 h) pero antes del inicio → 60 %."""
    turno, pago = _sembrar(db_session, inicio=REF + timedelta(hours=2))
    assert pago is not None

    _cancelar(db_session, turno)
    db_session.commit()

    dev = db_session.query(Devolucion).filter(Devolucion.pago_id == pago.id).one()
    assert dev.porcentaje == 60
    assert dev.monto == Decimal("6000.00")


def test_cancelacion_en_el_limite_exacto_crea_100_borde(db_session: Session) -> None:
    """Borde: `inicio - ahora == ANTICIPACION_MIN_HS` → 100 % (regla `>=`)."""
    anticipacion = get_settings().anticipacion_min_hs
    turno, pago = _sembrar(db_session, inicio=REF + timedelta(hours=anticipacion))
    assert pago is not None

    _cancelar(db_session, turno)
    db_session.commit()

    dev = db_session.query(Devolucion).filter(Devolucion.pago_id == pago.id).one()
    assert dev.porcentaje == 100


def test_cancelacion_cero_sin_devolucion(db_session: Session) -> None:
    """Borde: cotización 0 % (post-`inicio`) → cancelado, sin devolución."""
    inicio = REF - timedelta(hours=1)
    turno, pago = _sembrar(db_session, inicio=inicio)
    assert pago is not None
    odontologo_id = uuid.UUID(str(turno.odontologo_id))
    assert hay_solape(db_session, odontologo_id, inicio,
                      inicio + timedelta(minutes=30), ahora=REF) is True

    _cancelar(db_session, turno)
    db_session.commit()

    db_session.refresh(turno)
    assert str(turno.estado) == "cancelado"
    historial = db_session.query(TurnoHistorial).filter(
        TurnoHistorial.turno_id == turno.id).all()
    assert [(h.estado_anterior, h.estado_nuevo) for h in historial] == [
        ("confirmado", "cancelado")]
    assert hay_solape(db_session, odontologo_id, inicio,
                      inicio + timedelta(minutes=30), ahora=REF) is False

    assert db_session.query(Devolucion).count() == 0
    assert db_session.query(EventoPago).filter(
        EventoPago.tipo_evento == "devolucion_solicitada").count() == 0
    assert db_session.query(Comprobante).count() == 0
    assert db_session.query(RecordatorioMail).filter(
        RecordatorioMail.tipo == "aviso_devolucion").count() == 0
    db_session.refresh(pago)
    assert str(pago.estado) == "aprobado"
    assert db_session.query(Turno).filter(Turno.estado == "devuelto").count() == 0


def test_turno_sin_pago_aprobado_no_crea_devolucion_negocio(
    db_session: Session,
) -> None:
    """Negocio: pago `pendiente` (no cobrado) → no se devuelve lo no cobrado."""
    turno, _ = _sembrar(db_session, inicio=REF + timedelta(days=30),
                        pago_estado="pendiente")

    _cancelar(db_session, turno)
    db_session.commit()

    assert db_session.query(Devolucion).count() == 0
    assert db_session.query(EventoPago).filter(
        EventoPago.tipo_evento == "devolucion_solicitada").count() == 0


def test_creado_a_cancelado_por_sistema_sin_devolucion_negocio(
    db_session: Session,
) -> None:
    """Negocio: `creado→cancelado` por sistema (pago rechazado/TTL) → sin devolución."""
    turno, pago = _sembrar(db_session, inicio=REF + timedelta(days=30),
                           estado="creado")

    transition(db_session, uuid.UUID(str(turno.id)), "cancelado",
               actor_tipo="sistema", actor_id="job-ttl", ahora=REF)
    db_session.commit()

    assert pago is not None
    assert db_session.query(Devolucion).count() == 0


def test_fallo_al_insertar_devolucion_revierte_cancelacion_borde(
    db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borde: si el INSERT de la devolución viola un CHECK, rollback total."""
    turno, pago = _sembrar(db_session, inicio=REF + timedelta(days=30))
    assert pago is not None
    from app.domain.devoluciones import service as service_module

    monkeypatch.setattr(service_module, "calcular_monto_devolucion",
                        lambda *_: Decimal("-1.00"))

    with pytest.raises(VersionConflict):
        _cancelar(db_session, turno)

    db_session.expire_all()
    recargado = db_session.get(Turno, turno.id)
    assert recargado is not None and str(recargado.estado) == "confirmado"
    assert db_session.query(Devolucion).count() == 0
    assert db_session.query(TurnoHistorial).filter(
        TurnoHistorial.turno_id == turno.id).count() == 0


def test_no_show_no_crea_devolucion_y_no_show_a_cancelado_422_borde(
    db_session: Session,
) -> None:
    """Borde: `no_show` retiene la seña; `no_show→cancelado` no es transición válida."""
    turno, pago = _sembrar(db_session, inicio=REF - timedelta(hours=2))
    assert pago is not None

    transition(db_session, uuid.UUID(str(turno.id)), "no_show",
               actor_tipo="recepcionista", actor_id="u-rec-1", ahora=REF)
    db_session.commit()

    assert db_session.query(Devolucion).count() == 0
    with pytest.raises(TransicionInvalida):
        transition(db_session, uuid.UUID(str(turno.id)), "cancelado",
                   actor_tipo="recepcionista", actor_id="u-rec-1", ahora=REF)
