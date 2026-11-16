"""Tests C-07 task 7 — Job diario de conciliación interna (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: conciliación detecta pago pendiente con evento webhook_recibido aprobado
  → genera evento_pago(conciliado) + alerta;
- negocio: conciliación sin discrepancias → no genera evento conciliado;
- borde: pago sin eventos → no genera evento conciliado (no hay qué comparar).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.workers.conciliacion import conciliar_devoluciones, conciliar_pagos

CORDOBA = ZoneInfo("America/Argentina/Cordoba")


def _sembrar_pago_con_evento(db_session: Session, estado_pago: str,
                             ultimo_evento: str) -> uuid.UUID:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario
    from app.infra.db.models.pago import EventoPago, Pago

    h = "$2b$04$" + "c" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-c-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    pac = Paciente(dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()

    turno_id = uuid.uuid4()
    turno = Turno(id=turno_id, paciente_id=pac.id, odontologo_id=od_id,
                  inicio=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
                  fin=datetime(2026, 10, 5, 9, 30, tzinfo=UTC),
                  estado="creado", canal="web",
                  idempotency_key=f"key-c-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.flush()

    pago_id = uuid.uuid4()
    pago = Pago(id=pago_id, turno_id=turno_id, odontologo_id=od_id,
                monto=65000, moneda="ARS", proveedor="simulado",
                mp_payment_id=f"sim_pay_{pago_id}", estado=estado_pago,
                idempotency_key=f"idem-c-{uuid.uuid4().hex[:12]}")
    db_session.add(pago)
    db_session.flush()

    ev = EventoPago(pago_id=pago_id, tipo_evento=ultimo_evento,
                    payload_json={"status": ultimo_evento}, actor="sistema")
    db_session.add(ev)
    db_session.commit()
    return pago_id


def test_conciliacion_detecta_discrepancia_feliz(db_session: Session) -> None:
    """Feliz: pago pendiente pero evento dice aprobado → evento conciliado + alerta."""
    from app.infra.db.models.pago import EventoPago

    pago_id = _sembrar_pago_con_evento(db_session, "pendiente", "webhook_recibido")

    alertas = conciliar_pagos(db_session)
    assert len(alertas) >= 1

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    conciliados = [e for e in eventos if e.tipo_evento == "conciliado"]
    assert len(conciliados) == 1
    assert conciliados[0].actor == "sistema"


def test_conciliacion_sin_discrepancia_negocio(db_session: Session) -> None:
    """Negocio: pago aprobado con evento aprobado → sin evento conciliado."""
    from app.infra.db.models.pago import EventoPago

    pago_id = _sembrar_pago_con_evento(db_session, "aprobado", "webhook_recibido")

    alertas = conciliar_pagos(db_session)
    assert len(alertas) == 0

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    conciliados = [e for e in eventos if e.tipo_evento == "conciliado"]
    assert len(conciliados) == 0


def test_conciliacion_pago_sin_eventos_borde(db_session: Session) -> None:
    """Borde: pago sin eventos → no genera evento conciliado (no hay qué comparar)."""
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario
    from app.infra.db.models.pago import EventoPago, Pago

    h = "$2b$04$" + "d" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-c2-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    pac = Paciente(dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()

    turno_id = uuid.uuid4()
    turno = Turno(id=turno_id, paciente_id=pac.id, odontologo_id=od_id,
                  inicio=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
                  fin=datetime(2026, 10, 5, 9, 30, tzinfo=UTC),
                  estado="creado", canal="web",
                  idempotency_key=f"key-c2-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.flush()

    pago_id = uuid.uuid4()
    pago = Pago(id=pago_id, turno_id=turno_id, odontologo_id=od_id,
                monto=65000, moneda="ARS", proveedor="simulado",
                mp_payment_id=f"sim_pay_{pago_id}", estado="pendiente",
                idempotency_key=f"idem-c2-{uuid.uuid4().hex[:12]}")
    db_session.add(pago)
    db_session.commit()

    alertas = conciliar_pagos(db_session)
    assert len(alertas) == 0

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    conciliados = [e for e in eventos if e.tipo_evento == "conciliado"]
    assert len(conciliados) == 0


def _sembrar_contexto(
    db_session: Session,
    *,
    estado_pago: str,
    estado_turno: str,
    con_devolucion: bool = False,
    con_evento_ejecutada: bool = False,
) -> tuple[uuid.UUID | None, uuid.UUID, uuid.UUID]:
    """Odontologo + turno + pago (+ devolucion ejecutada) con eventos base."""
    from app.infra.db.models import (
        Devolucion,
        Odontologo,
        Paciente,
        Turno,
        Usuario,
    )
    from app.infra.db.models.pago import EventoPago, Pago

    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        email=f"od-reemb-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "r" * 53,
        rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=10000)
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    pac = Paciente(
        dni=f"88{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()

    inicio = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(
        minutes=(uuid.uuid4().int % 5000) * 30
    )
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od_id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado_turno,
        canal="web",
        idempotency_key=f"key-reemb-{suf}",
    )
    db_session.add(turno)
    db_session.commit()

    pago = Pago(
        turno_id=turno.id,
        odontologo_id=od_id,
        monto=Decimal("10000.00"),
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado=estado_pago,
        idempotency_key=f"idem-reemb-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    pago_id = uuid.UUID(str(pago.id))
    turno_id = uuid.UUID(str(turno.id))

    base = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    db_session.add(
        EventoPago(
            pago_id=pago_id,
            tipo_evento="creado",
            payload_json={},
            actor="paciente",
            created_at=base,
        )
    )
    if estado_pago in ("aprobado", "reembolsado_parcial", "reembolsado_total"):
        db_session.add(
            EventoPago(
                pago_id=pago_id,
                tipo_evento="webhook_recibido",
                payload_json={"kind": "pago", "status": "aprobado"},
                actor="sistema",
                created_at=base + timedelta(minutes=1),
            )
        )

    dev_id: uuid.UUID | None = None
    if con_devolucion:
        actor = Usuario(
            email=f"staff-reemb-{suf}@clinica-ficticia.example.ar",
            password_hash="$2b$04$" + "u" * 53,
            rol="recepcionista",
        )
        db_session.add(actor)
        db_session.commit()
        dev = Devolucion(
            pago_id=pago_id,
            turno_id=turno_id,
            monto=Decimal("6000.00"),
            porcentaje=60,
            motivo="cancelacion",
            estado="ejecutada",
            idempotency_key=f"dev_{pago_id}",
            mp_refund_id=f"sim_refund_{uuid.uuid4()}",
            aprobada_por=actor.id,
            aprobada_at=datetime(2026, 11, 1, 9, 2, tzinfo=UTC),
            ejecutada_por=actor.id,
            ejecutada_at=datetime(2026, 11, 1, 9, 3, tzinfo=UTC),
        )
        db_session.add(dev)
        db_session.commit()
        dev_id = uuid.UUID(str(dev.id))

    if con_evento_ejecutada:
        db_session.add(
            EventoPago(
                pago_id=pago_id,
                tipo_evento="devolucion_ejecutada",
                payload_json={
                    "monto": "6000.00",
                    "porcentaje": 60,
                    "mp_refund_id": f"sim_refund_{uuid.uuid4()}",
                },
                actor="sistema",
                created_at=base + timedelta(minutes=2),
            )
        )
    db_session.commit()
    return dev_id, pago_id, turno_id


def test_conciliacion_reembolso_consistente_sin_alerta_feliz(
    db_session: Session,
) -> None:
    """Feliz (D9): devolucion ejecutada + pago reembolsado + turno devuelto."""
    from app.infra.db.models.pago import EventoPago

    _, pago_id, _ = _sembrar_contexto(
        db_session,
        estado_pago="reembolsado_parcial",
        estado_turno="devuelto",
        con_devolucion=True,
        con_evento_ejecutada=True,
    )

    assert conciliar_pagos(db_session) == []
    assert conciliar_devoluciones(db_session) == []

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    assert [e for e in eventos if e.tipo_evento == "conciliado"] == []


def test_conciliacion_pago_aprobado_cancelado_cero_negocio(
    db_session: Session,
) -> None:
    """Negocio (D9): aprobado + turno cancelado sin devolucion no es discrepancia."""
    from app.infra.db.models.pago import EventoPago

    _, pago_id, _ = _sembrar_contexto(
        db_session, estado_pago="aprobado", estado_turno="cancelado"
    )

    assert conciliar_pagos(db_session) == []
    assert conciliar_devoluciones(db_session) == []

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    assert [e for e in eventos if e.tipo_evento == "conciliado"] == []


def test_conciliacion_discrepancia_pago_sigue_conciliando_error(
    db_session: Session,
) -> None:
    """Error: la discrepancia de pago previa sigue generando `conciliado`."""
    from app.infra.db.models.pago import EventoPago

    pago_id = _sembrar_pago_con_evento(db_session, "pendiente", "webhook_recibido")

    alertas = conciliar_pagos(db_session)
    assert any(
        a["pago_id"] == str(pago_id) and a["discrepancia"] is True for a in alertas
    )

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    conciliados = [e for e in eventos if e.tipo_evento == "conciliado"]
    assert len(conciliados) == 1
    assert conciliados[0].payload_json["discrepancia"] is True


@pytest.mark.parametrize(
    ("estado_pago", "estado_turno", "detalle"),
    [
        ("aprobado", "devuelto", "pago_no_reembolsado"),
        ("reembolsado_parcial", "cancelado", "turno_no_devuelto"),
    ],
)
def test_conciliacion_devolucion_ejecutada_inconsistente_alerta_borde(
    db_session: Session,
    estado_pago: str,
    estado_turno: str,
    detalle: str,
) -> None:
    """Borde (D9): devolucion ejecutada sin pago reembolsado o turno devuelto."""
    from app.infra.db.models.pago import EventoPago

    dev_id, pago_id, _ = _sembrar_contexto(
        db_session,
        estado_pago=estado_pago,
        estado_turno=estado_turno,
        con_devolucion=True,
        con_evento_ejecutada=True,
    )

    alertas = conciliar_devoluciones(db_session)
    assert len(alertas) == 1
    assert alertas[0]["tipo"] == "devolucion"
    assert alertas[0]["detalle"] == detalle
    assert alertas[0]["devolucion_id"] == str(dev_id)

    db_session.expire_all()
    eventos = (
        db_session.query(EventoPago)
        .filter_by(pago_id=pago_id, tipo_evento="conciliado")
        .all()
    )
    assert len(eventos) == 1
    payload = eventos[0].payload_json
    assert payload["discrepancia"] is True
    assert payload["tipo"] == "devolucion"
    assert payload["devolucion_id"] == str(dev_id)
    assert eventos[0].actor == "sistema"

    assert conciliar_devoluciones(db_session) == []
    db_session.expire_all()
    repetidos = (
        db_session.query(EventoPago)
        .filter_by(pago_id=pago_id, tipo_evento="conciliado")
        .all()
    )
    assert len(repetidos) == 1
