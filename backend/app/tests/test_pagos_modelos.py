"""Tests C-07 task 1.2 — modelos Pago/EventoPago + repositorios (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: Pago pendiente con mp_payment_id sintético sim_pay_<uuid>, proveedor='simulado';
- negocio: idempotency_key duplicada y mp_payment_id duplicada → IntegrityError;
- borde: EventoPago append-only (sin is_active/soft_delete, sin update/delete del rol app, P9).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models.pago import EventoPago, Pago


def _sembrar_turno(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "p" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-p-{suf}@clinica-ficticia.example.ar",
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
    t = Turno(paciente_id=pac.id, odontologo_id=od_id,
              inicio=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
              fin=datetime(2026, 10, 5, 9, 30, tzinfo=UTC),
              estado="creado", canal="web",
              idempotency_key=f"key-p-{uuid.uuid4().hex[:12]}")
    db_session.add(t)
    db_session.commit()
    return uuid.UUID(str(t.id)), od_id


def test_pago_pendiente_simulado_feliz(db_session: Session) -> None:
    """Feliz: Pago con estado='pendiente', proveedor='simulado', mp_payment_id='sim_pay_<uuid>'."""
    import uuid

    turno_id, od_id = _sembrar_turno(db_session)
    mp_id = f"sim_pay_{uuid.uuid4()}"
    pago = Pago(
        turno_id=turno_id,
        odontologo_id=od_id,
        monto=65000,
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=mp_id,
        estado="pendiente",
        idempotency_key=f"idem-{uuid.uuid4().hex[:12]}",
    )
    db_session.add(pago)
    db_session.flush()
    assert pago.id is not None
    assert pago.estado == "pendiente"
    assert pago.proveedor == "simulado"
    assert pago.mp_payment_id == mp_id
    assert pago.mp_payment_id.startswith("sim_pay_")


def test_idempotency_key_duplicada_rechazada_negocio(db_session: Session) -> None:
    """Negocio: idempotency_key duplicada → IntegrityError (P4)."""
    import uuid

    turno_id, od_id = _sembrar_turno(db_session)
    key = f"idem-{uuid.uuid4().hex[:12]}"
    p1 = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
              proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
              estado="pendiente", idempotency_key=key)
    db_session.add(p1)
    db_session.flush()
    p2 = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
              proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
              estado="pendiente", idempotency_key=key)
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_mp_payment_id_duplicada_rechazada_negocio(db_session: Session) -> None:
    """Negocio: mp_payment_id duplicada → IntegrityError (P4/P6)."""
    import uuid

    turno_id, od_id = _sembrar_turno(db_session)
    mp_id = f"sim_pay_{uuid.uuid4()}"
    key_base = f"idem-{uuid.uuid4().hex[:12]}"
    p1 = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
              proveedor="simulado", mp_payment_id=mp_id,
              estado="pendiente", idempotency_key=key_base)
    db_session.add(p1)
    db_session.flush()
    p2 = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
              proveedor="simulado", mp_payment_id=mp_id,
              estado="pendiente", idempotency_key=f"{key_base}-2")
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_evento_pago_append_only_borde(db_session: Session) -> None:
    """Borde: EventoPago se inserta; sin is_active/soft_delete (append-only, P9)."""
    import uuid

    turno_id, od_id = _sembrar_turno(db_session)
    pago = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
                proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
                estado="pendiente", idempotency_key=f"idem-{uuid.uuid4().hex[:12]}")
    db_session.add(pago)
    db_session.flush()
    ev = EventoPago(
        pago_id=pago.id,
        tipo_evento="creado",
        payload_json={"monto": 65000},
        actor="sistema",
    )
    db_session.add(ev)
    db_session.flush()
    assert ev.id is not None
    assert ev.tipo_evento == "creado"
    assert ev.actor == "sistema"
    assert not hasattr(ev, "is_active")
    assert not hasattr(ev, "soft_delete")


def test_pago_proveedor_mercadopago_triangulate(db_session: Session) -> None:
    """Triangulate: Pago con proveedor='mercadopago' y mp_preference_id seteado."""
    import uuid

    turno_id, od_id = _sembrar_turno(db_session)
    pago = Pago(turno_id=turno_id, odontologo_id=od_id, monto=70000,
                moneda="ARS", proveedor="mercadopago",
                mp_payment_id=f"mp_pay_{uuid.uuid4()}",
                mp_preference_id=f"pref_{uuid.uuid4()}",
                estado="pendiente",
                idempotency_key=f"idem-{uuid.uuid4().hex[:12]}")
    db_session.add(pago)
    db_session.flush()
    assert pago.proveedor == "mercadopago"
    assert pago.mp_preference_id is not None
    assert pago.mp_preference_id.startswith("pref_")


def test_evento_pago_tipo_webhook_recibido_triangulate(db_session: Session) -> None:
    """Triangulate: EventoPago con tipo_evento='webhook_recibido' y actor='sistema'."""
    import uuid

    turno_id, od_id = _sembrar_turno(db_session)
    pago = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
                proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
                estado="pendiente", idempotency_key=f"idem-{uuid.uuid4().hex[:12]}")
    db_session.add(pago)
    db_session.flush()
    ev = EventoPago(
        pago_id=pago.id,
        tipo_evento="webhook_recibido",
        payload_json={"mp_payment_id": pago.mp_payment_id, "status": "approved"},
        actor="sistema",
    )
    db_session.add(ev)
    db_session.flush()
    assert ev.tipo_evento == "webhook_recibido"
    assert ev.payload_json["status"] == "approved"
    assert ev.actor == "sistema"
