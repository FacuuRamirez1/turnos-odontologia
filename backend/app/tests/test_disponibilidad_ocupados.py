"""Tests C-05 §5.3 — motor resta turnos activos (RED primero, task 5.3).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: slot con `confirmado` no se ofrece, el resto sí;
- error-negocio: doble-reserva vía API → 409 `SLOT_OCUPADO`;
- borde: `creado` vencido (TTL) cuenta libre por cómputo (se ofrece).
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

CORDOBA = ZoneInfo("America/Argentina/Cordoba")


def _contexto(db_session: Session) -> dict[str, object]:
    from app.infra.db.models import Disponibilidad, Odontologo, Paciente, Turno, Usuario

    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-oc-{suf}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "s" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    base = (datetime.now(CORDOBA) + timedelta(days=35)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    db_session.add(Disponibilidad(
        odontologo_id=od.id, dia_semana=base.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(10, 0),
        duracion_min=30, tope_dia=14))
    dni_nuevo = f"33{uuid.uuid4().int % 900000 + 100000:06d}"
    pac = Paciente(dni=dni_nuevo, nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    ini_utc = base.astimezone(UTC)
    ocupado = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ini_utc,
                    fin=ini_utc + timedelta(minutes=30), estado="confirmado",
                    canal="web", idempotency_key=f"key-oc-{suf}")
    db_session.add(ocupado)
    db_session.commit()
    return {"od_id": od.id, "fecha": base.date().isoformat(),
            "slot_ocupado": ini_utc.isoformat(), "pac_dni": pac.dni}


def test_confirmado_resta_del_motor_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _contexto(db_session)
    r = auth_client.get("/api/disponibilidad",
                        params={"odontologo_id": str(ctx["od_id"]),
                                "fecha": cast(str, ctx["fecha"])})
    assert r.status_code == 200, r.text
    inicios = [s["inicio"] for s in r.json()["slots"]]
    assert ctx["slot_ocupado"] not in inicios
    assert len(inicios) == 1  # 09:30 libre, 09:00 ocupado


def test_doble_reserva_via_api_409_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _contexto(db_session)
    base = datetime.fromisoformat(cast(str, ctx["slot_ocupado"]))
    r = auth_client.post(
        "/api/reservas",
        json={"odontologo_id": str(ctx["od_id"]), "inicio": base.isoformat(),
              "dni": ctx["pac_dni"], "nombre": "Ana", "apellido": "Ficticia",
              "consentimiento_datos": True,
              "consentimiento_fecha": "2030-01-01T09:00:00+00:00"},
        headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "SLOT_OCUPADO"


def test_creado_vencido_cuenta_libre_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    from app.infra.db.models import Turno

    ctx = _contexto(db_session)
    # El ocupado pasa a `creado` vencido (TTL 15): el cómputo lo da libre.
    fila = db_session.query(Turno).first()
    assert fila is not None
    fila.estado = "creado"
    fila.created_at = datetime.now(UTC) - timedelta(minutes=60)
    db_session.commit()

    r = auth_client.get("/api/disponibilidad",
                        params={"odontologo_id": str(ctx["od_id"]),
                                "fecha": cast(str, ctx["fecha"])})
    assert r.status_code == 200, r.text
    assert len(r.json()["slots"]) == 2
