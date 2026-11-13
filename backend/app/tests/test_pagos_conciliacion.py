"""Tests C-07 task 7 — Job diario de conciliación interna (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: conciliación detecta pago pendiente con evento webhook_recibido aprobado
  → genera evento_pago(conciliado) + alerta;
- negocio: conciliación sin discrepancias → no genera evento conciliado;
- borde: pago sin eventos → no genera evento conciliado (no hay qué comparar).
"""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.workers.conciliacion import conciliar_pagos

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
