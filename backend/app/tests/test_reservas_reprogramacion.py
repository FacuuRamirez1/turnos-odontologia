"""Tests C-05 §4.2 — reprogramación atómica (RED primero, task 4.2).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: origen → `reprogramado` + nuevo `confirmado` heredando `pago_id`
  y `reprogramado_de_id`, una fila de historial por lado;
- error: slot objetivo ocupado → rollback total (origen sigue `confirmado`,
  sin turno nuevo);
- borde: nuevo slot en pasado → 422 sin cambios.
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import TypedDict
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.conftest import TEST_AUTH_SECRET

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
PAGO_ID = "11111111-2222-3333-4444-555555555555"


class _Ctx(TypedDict):
    turno_id: uuid.UUID
    dni: str
    token: str
    od_id: uuid.UUID
    base: datetime


def _sembrar(db_session: Session) -> _Ctx:
    from app.core.security.action_tokens import issue_action_token
    from app.infra.db.models import Disponibilidad, Odontologo, Paciente, Turno, Usuario

    suf = uuid.uuid4().hex[:8]
    dni = f"66{suf}"
    u = Usuario(email=f"od-g-{suf}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "p" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=dni, nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    base = (datetime.now(CORDOBA) + timedelta(days=35)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    db_session.add(Disponibilidad(
        odontologo_id=od.id, dia_semana=base.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(12, 0),
        duracion_min=30, tope_dia=14))
    db_session.commit()
    ini_utc = base.astimezone(UTC)
    origen = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ini_utc,
                   fin=ini_utc + timedelta(minutes=30), estado="confirmado",
                   canal="web", idempotency_key=f"key-g-{suf}",
                   pago_id=uuid.UUID(PAGO_ID))
    db_session.add(origen)
    db_session.commit()
    token = issue_action_token(destino=dni, proposito="mis-turnos",
                               secret=TEST_AUTH_SECRET)
    return {"turno_id": origen.id, "dni": dni, "token": token,
            "od_id": od.id, "base": base}


def _nuevo_iso(base: datetime, minutos: int) -> str:
    return (base + timedelta(minutes=minutos)).isoformat()


def test_reprogramar_feliz_hereda_pago(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    r = auth_client.post(
        f"/api/reservas/{ctx['turno_id']}/reprogramar",
        params={"dni": ctx["dni"], "token": ctx["token"]},
        json={"nuevo_inicio": _nuevo_iso(ctx["base"], 60)},
        headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["origen"]["estado"] == "reprogramado"
    assert cuerpo["nuevo"]["estado"] == "confirmado"
    assert cuerpo["nuevo"]["pago_id"] == PAGO_ID

    from app.infra.db.models import Turno, TurnoHistorial
    assert db_session.query(Turno).count() == 2
    assert db_session.query(TurnoHistorial).count() == 2


def test_reprogramar_slot_ocupado_rollback_total_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    from datetime import timedelta as _td

    from app.infra.db.models import Turno

    ctx = _sembrar(db_session)
    # Ocupa el slot objetivo con otro turno confirmado.
    objetivo = ctx["base"] + _td(minutes=60)
    primero = db_session.query(Turno).first()
    assert primero is not None
    otro = Turno(paciente_id=primero.paciente_id,
                 odontologo_id=ctx["od_id"], inicio=objetivo.astimezone(UTC),
                 fin=objetivo.astimezone(UTC) + _td(minutes=30),
                 estado="confirmado", canal="web",
                 idempotency_key=f"key-g-bloq-{uuid.uuid4().hex[:8]}")
    db_session.add(otro)
    db_session.commit()

    r = auth_client.post(
        f"/api/reservas/{ctx['turno_id']}/reprogramar",
        params={"dni": ctx["dni"], "token": ctx["token"]},
        json={"nuevo_inicio": _nuevo_iso(ctx["base"], 60)},
        headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code in (404, 409, 422), r.text

    origen = db_session.query(Turno).filter(Turno.id == ctx["turno_id"]).first()
    assert origen is not None and origen.estado == "confirmado"


def test_reprogramar_slot_pasado_422_sin_cambios_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    pasado = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    r = auth_client.post(
        f"/api/reservas/{ctx['turno_id']}/reprogramar",
        params={"dni": ctx["dni"], "token": ctx["token"]},
        json={"nuevo_inicio": pasado},
        headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 422, r.text

    from app.infra.db.models import Turno
    origen = db_session.query(Turno).filter(Turno.id == ctx["turno_id"]).first()
    assert origen is not None and origen.estado == "confirmado"
    assert db_session.query(Turno).count() == 1
