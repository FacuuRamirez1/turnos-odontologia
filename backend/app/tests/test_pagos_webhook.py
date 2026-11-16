"""Tests C-07 task 6 — POST /webhooks/mercadopago (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: webhook válido confirma turno con actor sistema;
- negocio: webhook rechazado cancela + libera slot; replay idempotente no duplica;
- borde: firma inválida → 401 sin persistir.
"""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.settings import get_settings

RUTA_WEBHOOK = "/api/webhooks/mercadopago"
CORDOBA = ZoneInfo("America/Argentina/Cordoba")


def _firmar(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _sembrar_turno_con_pago(
    db_session: Session, dni: str = "99999801",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Crea odontólogo, paciente, turno, pago y evento directamente en DB."""
    from app.infra.db.models import Disponibilidad, Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "w" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-wh-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))

    objetivo = datetime.now(CORDOBA) + timedelta(days=35)
    objetivo = objetivo.replace(hour=9, minute=0, second=0, microsecond=0)
    db_session.add(Disponibilidad(
        odontologo_id=od_id, dia_semana=objetivo.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(12, 0),
        duracion_min=30, tope_dia=14))
    db_session.commit()

    db_session.add(Paciente(dni=dni, nombre="Ana", apellido="Ficticia",
                            consentimiento_datos=True,
                            consentimiento_fecha=datetime(2026, 1, 1, 9, 0, tzinfo=UTC)))
    db_session.commit()

    from app.infra.db.models.pago import EventoPago, Pago

    turno_id = uuid.uuid4()
    turno = Turno(
        id=turno_id, paciente_id=uuid.uuid4(), odontologo_id=od_id,
        inicio=objetivo, fin=objetivo + timedelta(minutes=30),
        estado="creado", canal="web",
        idempotency_key=f"key-wh-{uuid.uuid4().hex[:12]}",
    )
    db_session.add(turno)
    db_session.flush()

    pago_id = uuid.uuid4()
    pago = Pago(
        id=pago_id, turno_id=turno_id, odontologo_id=od_id,
        monto=65000, moneda="ARS", proveedor="simulado",
        mp_payment_id=f"sim_pay_{pago_id}",
        mp_preference_id=None, estado="pendiente",
        idempotency_key=f"idem-wh-{uuid.uuid4().hex[:12]}",
    )
    db_session.add(pago)
    db_session.flush()

    ev = EventoPago(
        pago_id=pago_id, tipo_evento="creado",
        payload_json={"monto": 65000}, actor="sistema",
    )
    db_session.add(ev)
    db_session.commit()

    return turno_id, pago_id, od_id


def test_webhook_valido_confirma_turno_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz C-07: webhook válido con approved → turno confirmado (actor sistema)."""
    turno_id, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999801")

    from app.infra.db.models import Pago
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    mp_id = pago.mp_payment_id

    payload = f'{{"mp_payment_id": "{mp_id}", "status": "approved"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(RUTA_WEBHOOK,
                         content=payload,
                         headers={"x-signature": firma, "content-type": "application/json"})
    assert r.status_code == 200, r.text

    db_session.expire_all()
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "aprobado"

    from app.infra.db.models import EventoPago, Turno, TurnoHistorial
    turno = db_session.query(Turno).get(uuid.UUID(str(turno_id)))
    assert turno is not None
    assert turno.estado == "confirmado"
    historial = db_session.query(TurnoHistorial).filter_by(turno_id=uuid.UUID(str(turno_id))).all()
    assert any(h.estado_nuevo == "confirmado" and h.actor_tipo == "sistema" for h in historial)
    eventos = db_session.query(EventoPago).filter_by(pago_id=uuid.UUID(str(pago_id))).all()
    assert any(e.tipo_evento == "webhook_recibido" for e in eventos)


def test_webhook_rechazado_cancela_turno_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Negocio: webhook rejected → turno cancelado + slot liberado."""
    turno_id, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999802")

    from app.infra.db.models import Pago
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    mp_id = pago.mp_payment_id

    payload = f'{{"mp_payment_id": "{mp_id}", "status": "rejected"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(RUTA_WEBHOOK,
                         content=payload,
                         headers={"x-signature": firma, "content-type": "application/json"})
    assert r.status_code == 200, r.text

    db_session.expire_all()
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "rechazado"

    from app.infra.db.models import Turno, TurnoHistorial
    turno = db_session.query(Turno).get(uuid.UUID(str(turno_id)))
    assert turno is not None
    assert turno.estado == "cancelado"
    historial = db_session.query(TurnoHistorial).filter_by(turno_id=uuid.UUID(str(turno_id))).all()
    assert any(h.estado_nuevo == "cancelado" and h.actor_tipo == "sistema" for h in historial)


def test_webhook_replay_idempotente_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: replay mismo mp_payment_id no duplica transición (idempotencia, P4)."""
    turno_id, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999803")

    from app.infra.db.models import EventoPago, Pago
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    mp_id = pago.mp_payment_id

    payload = f'{{"mp_payment_id": "{mp_id}", "status": "approved"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)

    # Primera vez: confirma
    r1 = auth_client.post(RUTA_WEBHOOK,
                          content=payload,
                          headers={"x-signature": firma, "content-type": "application/json"})
    assert r1.status_code == 200, r1.text

    # Segunda vez: idempotente, no duplica
    r2 = auth_client.post(RUTA_WEBHOOK,
                          content=payload,
                          headers={"x-signature": firma, "content-type": "application/json"})
    assert r2.status_code == 200, r2.text

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=uuid.UUID(str(pago_id))).all()
    webhook_events = [e for e in eventos if e.tipo_evento == "webhook_recibido"]
    assert len(webhook_events) == 1  # no duplicado


def _sembrar_devolucion(
    db_session: Session, *, estado: str = "aprobada", porcentaje: int = 60,
    pago_estado: str = "aprobado",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
    """Turno cancelado + pago aprobado + devolución en `estado` (D3/D4)."""
    from decimal import Decimal

    from app.infra.db.models import (
        Devolucion,
        Odontologo,
        Paciente,
        Pago,
        Turno,
        Usuario,
    )

    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        email=f"od-webref-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "w" * 53, rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"),
                    monto_senia=Decimal("10000"))
    db_session.add(od)
    db_session.commit()

    pac = Paciente(
        dni=f"88{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana", apellido="Ficticia", consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()

    inicio = datetime.now(CORDOBA) + timedelta(days=30)
    turno = Turno(
        paciente_id=pac.id, odontologo_id=od.id, inicio=inicio,
        fin=inicio + timedelta(minutes=30), estado="cancelado", canal="web",
        idempotency_key=f"key-webref-{suf}",
    )
    db_session.add(turno)
    db_session.commit()

    pago = Pago(
        turno_id=turno.id, odontologo_id=od.id, monto=Decimal("10000.00"),
        moneda="ARS", proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}", estado=pago_estado,
        idempotency_key=f"idem-webref-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    turno.pago_id = pago.id
    db_session.add(turno)
    db_session.commit()

    actor = Usuario(
        email=f"staff-webref-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "s" * 53, rol="recepcionista",
    )
    db_session.add(actor)
    db_session.commit()

    monto = Decimal("10000.00") if porcentaje == 100 else Decimal("6000.00")
    dev = Devolucion(
        pago_id=pago.id, turno_id=turno.id, monto=monto, porcentaje=porcentaje,
        motivo="cancelación", estado=estado, idempotency_key=f"dev_{pago.id}",
        aprobada_por=actor.id, aprobada_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        ejecutada_por=actor.id, ejecutada_at=datetime(2026, 11, 1, 10, 5, tzinfo=UTC),
    )
    db_session.add(dev)
    db_session.commit()
    db_session.refresh(dev)

    return turno.id, pago.id, dev.id, str(pago.mp_payment_id)


def _payload_devolucion(mp_payment_id: str, mp_refund_id: str) -> str:
    return (
        f'{{"kind": "devolucion", "mp_payment_id": "{mp_payment_id}", '
        f'"mp_refund_id": "{mp_refund_id}", "status": "refunded"}}'
    )


def test_webhook_devolucion_sobre_pago_aprobado_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz: devolución aprobada → ejecutada + pago parcial + turno devuelto."""
    turno_id, pago_id, dev_id, mp_payment_id = _sembrar_devolucion(db_session)
    refund_id = "sim_refund_" + uuid.uuid4().hex

    payload = _payload_devolucion(mp_payment_id, refund_id)
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text

    from decimal import Decimal

    from app.infra.db.models import Devolucion, EventoPago, Pago, Turno
    db_session.expire_all()
    dev = db_session.query(Devolucion).get(uuid.UUID(str(dev_id)))
    assert dev is not None
    assert dev.estado == "ejecutada"
    assert dev.mp_refund_id == refund_id

    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "reembolsado_parcial"
    assert pago.monto == Decimal("10000.00")

    turno = db_session.query(Turno).get(uuid.UUID(str(turno_id)))
    assert turno is not None
    assert turno.estado == "devuelto"

    eventos = db_session.query(EventoPago).filter_by(
        pago_id=uuid.UUID(str(pago_id))).all()
    ejecutados = [e for e in eventos if e.tipo_evento == "devolucion_ejecutada"]
    assert len(ejecutados) == 1
    assert ejecutados[0].actor == "sistema"
    assert ejecutados[0].payload_json["mp_refund_id"] == refund_id
    assert ejecutados[0].payload_json["solicitado_por"]


def test_webhook_devolucion_100_marca_reembolso_total_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz: devolución del 100 % → pago `reembolsado_total`."""
    turno_id, pago_id, dev_id, mp_payment_id = _sembrar_devolucion(
        db_session, porcentaje=100)

    payload = _payload_devolucion(mp_payment_id, "sim_refund_total_100")
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text

    from app.infra.db.models import Pago
    db_session.expire_all()
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "reembolsado_total"


def test_devolucion_de_turno_reprogramado_solo_el_cancelado_vuelve_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde F3: tras reprogramar, solo el turno cancelado (nuevo) pasa a devuelto."""
    turno_id, pago_id, dev_id, mp_payment_id = _sembrar_devolucion(db_session)

    from app.infra.db.models import Pago, Turno
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    nuevo = db_session.query(Turno).get(uuid.UUID(str(turno_id)))
    assert pago is not None and nuevo is not None
    original = Turno(
        paciente_id=nuevo.paciente_id, odontologo_id=nuevo.odontologo_id,
        inicio=nuevo.inicio + timedelta(days=1),
        fin=nuevo.fin + timedelta(days=1), estado="reprogramado", canal="web",
        idempotency_key=f"key-reprog-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(original)
    db_session.commit()
    pago.turno_id = original.id
    nuevo.pago_id = pago.id
    db_session.add_all([pago, nuevo])
    db_session.commit()
    original_id = original.id

    payload = _payload_devolucion(mp_payment_id, "sim_refund_reprog")
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text

    from app.infra.db.models import TurnoHistorial
    db_session.expire_all()
    nuevo_final = db_session.query(Turno).get(uuid.UUID(str(turno_id)))
    original_final = db_session.query(Turno).get(uuid.UUID(str(original_id)))
    assert nuevo_final is not None and original_final is not None
    assert nuevo_final.estado == "devuelto"
    assert original_final.estado == "reprogramado"
    assert not db_session.query(TurnoHistorial).filter_by(
        turno_id=uuid.UUID(str(original_id)), estado_nuevo="devuelto").all()


def test_replay_webhook_devolucion_no_duplica_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde P4: replay por mp_refund_id no crea segundo evento ni transición."""
    turno_id, pago_id, dev_id, mp_payment_id = _sembrar_devolucion(db_session)
    refund_id = "sim_refund_replay_" + uuid.uuid4().hex

    payload = _payload_devolucion(mp_payment_id, refund_id)
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    headers = {"x-signature": firma, "content-type": "application/json"}

    r1 = auth_client.post(RUTA_WEBHOOK, content=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    r2 = auth_client.post(RUTA_WEBHOOK, content=payload, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["idempotente"] is True

    from app.infra.db.models import EventoPago, TurnoHistorial
    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(
        pago_id=uuid.UUID(str(pago_id))).all()
    assert len([e for e in eventos if e.tipo_evento == "devolucion_ejecutada"]) == 1
    assert len([
        e for e in eventos
        if e.tipo_evento == "webhook_recibido"
        and e.payload_json.get("kind") == "devolucion"
    ]) == 1

    devueltos = db_session.query(TurnoHistorial).filter_by(
        turno_id=uuid.UUID(str(turno_id)), estado_nuevo="devuelto").all()
    assert len(devueltos) == 1


def test_webhook_devolucion_no_aprobada_error_sin_efectos_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: devolución pendiente → error explícito, payload crudo, sin efectos."""
    turno_id, pago_id, dev_id, mp_payment_id = _sembrar_devolucion(
        db_session, estado="pendiente")

    payload = _payload_devolucion(mp_payment_id, "sim_refund_no_aprobada")
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "DEVOLUCION_NO_APROBADA"

    from app.infra.db.models import Devolucion, EventoPago, Pago, Turno
    db_session.expire_all()
    dev = db_session.query(Devolucion).get(uuid.UUID(str(dev_id)))
    assert dev is not None
    assert dev.estado == "pendiente"
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "aprobado"
    turno = db_session.query(Turno).get(uuid.UUID(str(turno_id)))
    assert turno is not None
    assert turno.estado == "cancelado"

    eventos = db_session.query(EventoPago).filter_by(
        pago_id=uuid.UUID(str(pago_id))).all()
    assert not any(e.tipo_evento == "devolucion_ejecutada" for e in eventos)
    crudos = [
        e for e in eventos
        if e.tipo_evento == "webhook_recibido"
        and e.payload_json.get("kind") == "devolucion"
    ]
    assert len(crudos) == 1
    assert crudos[0].payload_json["payload_crudo"] == payload


def test_webhook_sin_kind_sigue_siendo_pago_compatibilidad(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Backward compat D5: un webhook_recibido de C-07 sin `kind` cuenta como pago."""
    turno_id, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999805")

    from app.infra.db.models import EventoPago, Pago
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    mp_id = str(pago.mp_payment_id)

    db_session.add(EventoPago(
        pago_id=uuid.UUID(str(pago_id)), tipo_evento="webhook_recibido",
        payload_json={"mp_payment_id": mp_id, "status": "aprobado",
                      "payload_crudo": "legacy"},
        actor="sistema",
    ))
    db_session.commit()

    payload = f'{{"mp_payment_id": "{mp_id}", "status": "approved"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["idempotente"] is True

    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(
        pago_id=uuid.UUID(str(pago_id))).all()
    assert len([e for e in eventos if e.tipo_evento == "webhook_recibido"]) == 1


def test_webhook_firma_invalida_401_sin_persistir_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: firma inválida → 401, sin persistir evento ni mutar pago."""
    turno_id, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999804")

    from app.infra.db.models import EventoPago, Pago
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None

    payload = f'{{"mp_payment_id": "sim_pay_{pago_id}", "status": "approved"}}'
    firma = "firma_invalida_que_no_coincide"
    r = auth_client.post(RUTA_WEBHOOK,
                         content=payload,
                         headers={"x-signature": firma, "content-type": "application/json"})
    assert r.status_code == 401, r.text

    db_session.expire_all()
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "pendiente"  # no mutado

    eventos = db_session.query(EventoPago).filter_by(pago_id=uuid.UUID(str(pago_id))).all()
    webhook_events = [e for e in eventos if e.tipo_evento == "webhook_recibido"]
    assert len(webhook_events) == 0  # no persistido
