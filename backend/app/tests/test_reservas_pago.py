"""Tests C-10 task 1.1 — `pago_id` en `ReservaOut` y query de checkout (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: `POST /api/reservas` devuelve `pago_id` + `checkout_token` y la
  `checkout_url` incluye `pago_id=<id>` para enlazar el sandbox C-10;
- negocio: reserva sin consentimiento → 422 `CONSENTIMIENTO_REQUERIDO` y cero
  filas de pago/turno (P11);
- borde: seña $0 omite el checkout sin fallar (201, sin `checkout_url`).
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
RUTA = "/api/reservas"
CONSENT_AT = "2030-01-01T09:00:00+00:00"


def _sembrar_odonto(db_session: Session, monto_senia: str = "65000") -> uuid.UUID:
    from app.infra.db.models import Disponibilidad, Odontologo, Usuario

    h = "$2b$04$" + "p" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-c10-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"),
                    monto_senia=Decimal(monto_senia))
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


def _payload(od_id: uuid.UUID, dni: str = "99999611") -> dict[str, object]:
    inicio = (datetime.now(CORDOBA) + timedelta(days=35)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    return {
        "odontologo_id": str(od_id),
        "inicio": inicio.isoformat(),
        "dni": dni,
        "nombre": "Ana",
        "apellido": "Ficticia",
        "consentimiento_datos": True,
        "consentimiento_fecha": CONSENT_AT,
    }


def test_reserva_devuelve_pago_id_y_checkout_con_pago_id_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz: pago_id persistido + URL de checkout con `pago_id` y `token`."""
    from app.infra.db.models import Pago

    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999611")

    r = auth_client.post(RUTA, json=_payload(od_id),
                         headers={"Idempotency-Key": f"c10-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    pago = db_session.query(Pago).filter(Pago.id == uuid.UUID(cuerpo["pago_id"])).first()
    assert pago is not None, cuerpo
    assert str(pago.turno_id) == cuerpo["id"]
    assert cuerpo["checkout_token"].startswith("chk_")
    assert f"pago_id={cuerpo['pago_id']}" in cuerpo["checkout_url"]
    assert f"token={cuerpo['checkout_token']}" in cuerpo["checkout_url"]


def test_reserva_sin_consentimiento_sin_pago_id_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Negocio: sin consentimiento → 422 y sin pago persistido."""
    from app.infra.db.models import Pago, Turno

    od_id = _sembrar_odonto(db_session)
    cuerpo = _payload(od_id, dni="99999612")
    cuerpo["consentimiento_datos"] = False
    cuerpo["consentimiento_fecha"] = None

    r = auth_client.post(RUTA, json=cuerpo,
                         headers={"Idempotency-Key": f"c10-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "CONSENTIMIENTO_REQUERIDO"
    assert db_session.query(Pago).count() == 0
    assert db_session.query(Turno).count() == 0


def test_reserva_senia_cero_omite_checkout_sin_fallar_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: seña $0 → 201 con pago_id, sin checkout_url/token (nada que cobrar)."""
    from app.infra.db.models import Pago

    od_id = _sembrar_odonto(db_session, monto_senia="0")
    _sembrar_paciente(db_session, "99999613")

    r = auth_client.post(RUTA, json=_payload(od_id, dni="99999613"),
                         headers={"Idempotency-Key": f"c10-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["pago_id"] is not None
    assert cuerpo["checkout_url"] is None
    assert cuerpo["checkout_token"] is None
    pago = db_session.query(Pago).filter(Pago.id == uuid.UUID(cuerpo["pago_id"])).first()
    assert pago is not None
    assert Decimal(str(pago.monto)) == Decimal("0")
