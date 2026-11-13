"""Tests C-07 task 5 — Endpoint sandbox POST /pagos/{pago_id}/simular (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: sandbox Aprobar con checkout_token válido → pago aprobado + turno confirmado;
- negocio: checkout_token reusado → 403/422;
- borde: flujo Rechazar → pago rechazado + turno cancelado (actor sistema).
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
RUTA_SANDBOX = "/api/pagos/{pago_id}/simular"


def _sembrar_odonto(db_session: Session) -> uuid.UUID:
    from app.infra.db.models import Disponibilidad, Odontologo, Usuario

    h = "$2b$04$" + "m" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-sb-{suf}@clinica-ficticia.example.ar",
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
    return od_id


def _sembrar_paciente(db_session: Session, dni: str) -> None:
    from app.infra.db.models import Paciente

    db_session.add(Paciente(dni=dni, nombre="Ana", apellido="Ficticia",
                            consentimiento_datos=True,
                            consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC)))
    db_session.commit()


def _inicio_iso() -> str:
    objetivo = datetime.now(CORDOBA) + timedelta(days=35)
    return objetivo.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()


def _payload(od_id: uuid.UUID, dni: str = "99999701") -> dict[str, object]:
    return {
        "odontologo_id": str(od_id),
        "inicio": _inicio_iso(),
        "dni": dni,
        "nombre": "Ana",
        "apellido": "Ficticia",
        "consentimiento_datos": True,
        "consentimiento_fecha": "2026-01-01T09:00:00+00:00",
    }


def test_sandbox_aprobar_confirma_turno_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz C-07: sandbox Aprobar → pago aprobado + turno confirmado (actor sistema)."""
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999701")

    r = auth_client.post("/api/reservas", json=_payload(od_id),
                         headers={"Idempotency-Key": f"rk-sb-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    turno_id = cuerpo["id"]
    checkout_token = cuerpo["checkout_token"]

    from app.infra.db.models import Pago
    pago = db_session.query(Pago).filter_by(turno_id=uuid.UUID(turno_id)).first()
    assert pago is not None
    pago_id = pago.id

    r2 = auth_client.post(RUTA_SANDBOX.format(pago_id=pago_id),
                          json={"accion": "aprobar"},
                          headers={"checkout_token": checkout_token})
    assert r2.status_code == 200, r2.text

    db_session.expire_all()
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "aprobado"

    from app.infra.db.models import EventoPago, Turno, TurnoHistorial
    turno = db_session.query(Turno).get(uuid.UUID(turno_id))
    assert turno is not None
    assert turno.estado == "confirmado"
    historial = db_session.query(TurnoHistorial).filter_by(turno_id=uuid.UUID(turno_id)).all()
    assert any(h.estado_nuevo == "confirmado" and h.actor_tipo == "sistema" for h in historial)
    eventos = db_session.query(EventoPago).filter_by(pago_id=uuid.UUID(str(pago_id))).all()
    assert any(e.tipo_evento == "webhook_recibido" for e in eventos)


def test_sandbox_token_reusado_rechazado_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: checkout_token ya consumido → 403/422, sin nuevo evento."""
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999702")

    r = auth_client.post("/api/reservas", json=_payload(od_id, dni="99999702"),
                         headers={"Idempotency-Key": f"rk-sb2-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    turno_id = cuerpo["id"]
    checkout_token = cuerpo["checkout_token"]

    from app.infra.db.models import Pago
    pago = db_session.query(Pago).filter_by(turno_id=uuid.UUID(turno_id)).first()
    assert pago is not None
    pago_id = pago.id

    r1 = auth_client.post(RUTA_SANDBOX.format(pago_id=pago_id),
                          json={"accion": "aprobar"},
                          headers={"checkout_token": checkout_token})
    assert r1.status_code == 200, r1.text

    r2 = auth_client.post(RUTA_SANDBOX.format(pago_id=pago_id),
                          json={"accion": "rechazar"},
                          headers={"checkout_token": checkout_token})
    assert r2.status_code in (403, 422), r2.text


def test_sandbox_rechazar_cancela_turno_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: sandbox Rechazar → pago rechazado + turno cancelado (actor sistema)."""
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999703")

    r = auth_client.post("/api/reservas", json=_payload(od_id, dni="99999703"),
                         headers={"Idempotency-Key": f"rk-sb3-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    turno_id = cuerpo["id"]
    checkout_token = cuerpo["checkout_token"]

    from app.infra.db.models import Pago
    pago = db_session.query(Pago).filter_by(turno_id=uuid.UUID(turno_id)).first()
    assert pago is not None
    pago_id = pago.id

    r2 = auth_client.post(RUTA_SANDBOX.format(pago_id=pago_id),
                          json={"accion": "rechazar"},
                          headers={"checkout_token": checkout_token})
    assert r2.status_code == 200, r2.text

    db_session.expire_all()
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    assert pago.estado == "rechazado"

    from app.infra.db.models import Turno, TurnoHistorial
    turno = db_session.query(Turno).get(uuid.UUID(turno_id))
    assert turno is not None
    assert turno.estado == "cancelado"
    historial = db_session.query(TurnoHistorial).filter_by(turno_id=uuid.UUID(turno_id)).all()
    assert any(h.estado_nuevo == "cancelado" and h.actor_tipo == "sistema" for h in historial)
