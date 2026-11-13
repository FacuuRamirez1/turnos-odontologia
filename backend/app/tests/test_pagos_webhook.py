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
